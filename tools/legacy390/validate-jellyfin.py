import os,json,time,urllib.request,urllib.parse,uuid,subprocess,re
from pathlib import Path
b=Path('/srv/ifro-nvidia-390/ffmpeg-full')
key=Path(os.environ.get('JELLYFIN_API_KEY_FILE','/run/secrets/jellyfin-api-key')).read_text().strip()
base='http://127.0.0.1:18096'
headers={'Authorization':'MediaBrowser Client="Legacy390Validation",Device="IfroTest",DeviceId="legacy390-validation",Version="1",Token="'+key+'"'}
selected=set(os.environ.get('VALIDATION_CASES','').split(','))- {''}
report=json.loads((b/'validation.json').read_text()) if selected and (b/'validation.json').exists() else {}
report.pop('failure',None)
def req(path,method='GET',body=None,timeout=90):
 url=path if path.startswith('http') else base+path
 h=dict(headers)
 if body is not None:h['Content-Type']='application/json'
 try:
  r=urllib.request.urlopen(urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=h,method=method),timeout=timeout)
 except urllib.error.HTTPError as e:
  message=e.read().decode(errors='replace').replace(key,'<redacted>')
  safe={'status':e.code,'path':urllib.parse.urlsplit(url).path,'body':message}
  (b/'last-http-error.json').write_text(json.dumps(safe,indent=2))
  raise RuntimeError('HTTP '+str(e.code)+' '+message[-1000:]) from None
 return r.read(),dict(r.headers)
def api(path,method='GET',body=None):
 raw,_=req(path,method,body);return json.loads(raw) if raw else None
def save(step,value):
 report[step]=value
 (b/'validation.json').write_text(json.dumps(report,indent=2))
 print(step,json.dumps(value),flush=True)
try:
 info=api('/System/Info')
 save('server',{'version':info.get('Version')})
 users=api('/Users')
 uid=next(u['Id'] for u in users if u.get('Policy',{}).get('IsAdministrator'))
 # Stop only jobs in the isolated copy before starting measurements.
 for task in api('/ScheduledTasks'):
  if task.get('State')=='Running':
   req('/ScheduledTasks/Running/'+task['Id'],'DELETE')
 folders=api('/Library/VirtualFolders')
 if not any(x.get('Name')=='Legacy390 Validation' for x in folders):
  api('/Library/VirtualFolders?'+urllib.parse.urlencode({'name':'Legacy390 Validation','collectionType':'movies','paths':'/probe-media','refreshLibrary':'true'}),'POST',{'LibraryOptions':{'EnableRealtimeMonitor':False,'EnableTrickplayImageExtraction':False,'EnableChapterImageExtraction':False,'TypeOptions':[{'Type':'Movie','MetadataFetchers':[],'ImageFetchers':[]}],'PathInfos':[{'Path':'/probe-media'}]}})
 items=[]
 for _ in range(60):
  data=api('/Items?Recursive=true&IncludeItemTypes=Movie&Fields=Path,MediaStreams&Limit=10000')
  items=[x for x in data['Items'] if x.get('Path','').startswith('/probe-media/')]
  if len(items)>=2 and all(any(m.get('Type')=='Video' and m.get('Codec') for m in x.get('MediaStreams',[])) and any(m.get('Type')=='Audio' for m in x.get('MediaStreams',[])) for x in items) and any(m.get('Type')=='Subtitle' for x in items if 'HEVC' not in x['Path'] for m in x.get('MediaStreams',[])):break
  time.sleep(1)
 assert len(items)>=2,'Test fixtures not indexed'
 profile={'Name':'Legacy390 Validation','MaxStreamingBitrate':2000000,'DirectPlayProfiles':[],'TranscodingProfiles':[{'Container':'ts','Type':'Video','AudioCodec':'aac','VideoCodec':'h264','Context':'Streaming','Protocol':'hls','MaxAudioChannels':'2','MinSegments':1,'SegmentLength':3,'BreakOnNonKeyFrames':False}],'CodecProfiles':[{'Type':'Video','Codec':'h264','Conditions':[{'Condition':'LessThanEqual','Property':'Width','Value':'1280','IsRequired':True},{'Condition':'LessThanEqual','Property':'Height','Value':'720','IsRequired':True}]}],'SubtitleProfiles':[{'Format':f,'Method':'Encode'} for f in ['srt','subrip','ass']]}
 cases=[('h264_gpu',False,False,0),('h264_subtitles',False,True,0),('h264_seek',False,False,10),('hevc_cpu_fallback',True,False,0)]
 out=b/'test-cache/validation-output';out.mkdir(parents=True,exist_ok=True)
 for name,hevc,subs,seek in cases:
  if selected and name not in selected:continue
  item=next(x for x in items if ('HEVC' in x['Path'])==hevc)
  subidx=next((s['Index'] for s in item.get('MediaStreams',[]) if s.get('Type')=='Subtitle'),None) if subs else -1
  assert subidx is not None,'Missing subtitle stream'
  params={'userId':uid,'enableDirectPlay':'false','enableDirectStream':'false','allowVideoStreamCopy':'false','allowAudioStreamCopy':'false','maxStreamingBitrate':2000000,'startTimeTicks':seek*10000000,'subtitleStreamIndex':subidx,'maxAudioChannels':2}
  known_logs=set((b/"test-config/log").glob("FFmpeg.Transcode*"))
  start=time.monotonic()
  playback=api('/Items/'+item['Id']+'/PlaybackInfo?'+urllib.parse.urlencode(params),'POST',{'DeviceProfile':profile,'UserId':uid,'MaxStreamingBitrate':2000000,'StartTimeTicks':seek*10000000,'SubtitleStreamIndex':subidx,'EnableDirectPlay':False,'EnableDirectStream':False,'AllowVideoStreamCopy':False,'AllowAudioStreamCopy':False,'EnableTranscoding':True,'MaxAudioChannels':2})
  sources=playback.get('MediaSources',[])
  source=next((s for s in sources if s.get('TranscodingUrl')),None)
  assert source is not None,'No transcoding URL: '+str(playback.get('ErrorCode'))
  url=urllib.parse.urljoin(base,source['TranscodingUrl'])
  parts=urllib.parse.urlsplit(url)
  query=urllib.parse.parse_qs(parts.query)
  query['SubtitleStreamIndex']=[str(subidx)]
  query.pop('StartTimeTicks',None)  # HLS seeks by segment index, not StartTimeTicks.
  if subs:query['SubtitleMethod']=['Encode']
  url=urllib.parse.urlunsplit((parts.scheme,parts.netloc,parts.path,urllib.parse.urlencode(query,doseq=True),parts.fragment))
  raw,h=req(url)
  # Follow master->media playlists, or accept a progressive transport stream.
  playlist_url=url
  depth=0
  while raw.lstrip().startswith(b'#EXTM3U') and b'#EXT-X-STREAM-INF' in raw:
   links=[x.strip() for x in raw.decode().splitlines() if x.strip() and not x.startswith('#')]
   assert links,'Empty master playlist'
   playlist_url=urllib.parse.urljoin(playlist_url,links[0]);raw,h=req(playlist_url)
   depth+=1;assert depth<4
  is_hls=raw.lstrip().startswith(b'#EXTM3U')
  if is_hls:
   text=raw.decode()
   links=[x.strip() for x in text.splitlines() if x.strip() and not x.startswith('#')]
   assert links,'No media segments'
   start_segment=min(len(links)-1,int(seek/3)) if seek else 0
   content=b''.join(req(urllib.parse.urljoin(playlist_url,s))[0] for s in links[start_segment:start_segment+3])
  else:content=raw
  output=out/(name+'.ts');output.write_bytes(content)
  r=subprocess.run(['docker','exec','jellyfin-legacy390-test','/opt/ifro-ffmpeg/bin/ffprobe','-v','error','-show_entries','stream=codec_type,codec_name,width,height,channels','-of','json','/cache/validation-output/'+output.name],capture_output=True,text=True,timeout=30)
  assert r.returncode==0,'ffprobe failed: '+r.stderr[-500:]
  streams=json.loads(r.stdout)['streams']
  assert any(s.get('codec_type')=='video' and s.get('codec_name')=='h264' and s.get('width',9999)<=1280 for s in streams)
  assert any(s.get('codec_type')=='audio' and s.get('codec_name')=='aac' for s in streams)
  result={'ok':True,'hls':is_hls,'seconds_to_fetch':round(time.monotonic()-start,3),'bytes':len(content),'streams':streams,'subtitle_index':subidx,'seek_seconds':seek}
  try:req('/Videos/ActiveEncodings?'+urllib.parse.urlencode({'deviceId':'legacy390-validation','playSessionId':playback.get('PlaySessionId','')}),'DELETE',timeout=10)
  except Exception:pass
  subprocess.run(['docker','exec','jellyfin-legacy390-test','sh','-c','pkill -INT -x ffmpeg || true'],capture_output=True,timeout=10)
  time.sleep(1)
  fresh=set((b/"test-config/log").glob("FFmpeg.Transcode*"))-known_logs
  logs='\n'.join(p.read_text(errors='replace') for p in fresh)
  result['gpu_used']='LEGACY390_BRIDGE' in logs and 'cuvidDecodePicture' in logs
  result['subtitle_filter']='subtitles=' in logs or 'ass=' in logs
  result['seek_in_command']=bool(re.search(r' -ss (?:00:00:0[89]|00:00:1[0-9]|[89]\.|1[0-9]\.)',logs))
  if name in ['h264_gpu','h264_seek']:assert result['gpu_used'],'GPU was not used'
  if hevc:assert not result['gpu_used'],'HEVC must use CPU'
  if subs:assert result['subtitle_filter'],'Subtitle filter not found'
  if seek:assert result['seek_in_command'],'Seek not found in command'
  save(name,result)
 save('complete',True)
except Exception as e:
 save('failure',{'type':type(e).__name__,'message':str(e).replace(key,'<redacted>')[-1200:]})
 raise

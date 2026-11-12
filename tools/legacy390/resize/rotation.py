from pathlib import Path
import subprocess,json
b=Path('/srv/ifro-nvidia-390/resize-profile')
ns={};exec((b/'launcher-transcode.py').read_text().split('report={}')[0],ns)
run=ns['run'];run=run[:-3]+['-e','LEGACY390_CUVID_RESIZE=1']+run[-3:]
args=['-hide_banner','-loglevel','error','-display_rotation','90','-i','/probe-media/Teste IFRO.mkv','-map','0:v:0','-map','0:a:0','-c','copy','-t','3','-y','/out/rotated.mp4']
r=subprocess.run(run+args,capture_output=True,text=True,timeout=30)
assert r.returncode==0,r.stderr
probe=['docker','exec','jellyfin','/opt/ifro-ffmpeg/bin/ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height:stream_side_data=rotation','-of','json']
r=subprocess.run(probe+['/cache/resize-profile/rotated.mp4'],capture_output=True,text=True,timeout=15)
info=json.loads(r.stdout)
assert any(abs(x.get('rotation',0))==90 for s in info['streams'] for x in s.get('side_data_list',[]))
args=ns['original'][1:];args[0:0]=['-t','2']
i=args.index('-i')
for j in range(i):
 if args[j]=='-f' and args[j+1]=='matroska':
  del args[j:j+2];break
args[args.index('-i')+1]='file:/out/rotated.mp4'
args[args.index('-hls_segment_filename')+1]='/out/rotation%d.ts';args[-1]='/out/rotation.m3u8'
r=subprocess.run(run+args,capture_output=True,text=True,timeout=45)
text=r.stdout+r.stderr;(b/'rotation.log').write_text(text)
assert r.returncode==0 and 'LEGACY390_BRIDGE' not in text
r=subprocess.run(probe+['/cache/resize-profile/rotation.m3u8'],capture_output=True,text=True,timeout=15)
video=json.loads(r.stdout)['streams'][0]
assert video['height']==720 and video['width']==404
result={'input':info['streams'][0],'output':video,'bridge':False,'ok':True}
(b/'rotation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))

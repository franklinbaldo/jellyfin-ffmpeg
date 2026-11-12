from pathlib import Path
import subprocess,json,os
b=Path('/srv/ifro-nvidia-390/resize-profile')
ns={};exec((b/'launcher-transcode.py').read_text().split('report={}')[0],ns)
run=ns['run'];run=run[:-3]+['-e','LEGACY390_CUVID_RESIZE=1']+run[-3:]
original=ns['original'];report={}
for name,w,h in [('keep1080',1920,1080),('request360',640,360)]:
 args=original[1:];args[0:0]=['-t','2']
 fi=args.index('-vf')+1
 args[fi]=args[fi].replace('1280',str(w)).replace('720',str(h))
 args[args.index('-hls_segment_filename')+1]='/out/'+name+'%d.ts';args[-1]='/out/'+name+'.m3u8'
 r=subprocess.run(run+args,capture_output=True,text=True,timeout=60)
 text=r.stdout+r.stderr;(b/(name+'.log')).write_text(text)
 assert r.returncode==0 and 'LEGACY390_RESIZE' not in text and 'LEGACY390_BRIDGE' in text
 probe=subprocess.run(['docker','exec','jellyfin','/opt/ifro-ffmpeg/bin/ffprobe','-v','error','-show_entries','stream=width,height,codec_type','-of','json','/cache/resize-profile/'+name+'.m3u8'],capture_output=True,text=True,timeout=15)
 streams=json.loads(probe.stdout)['streams'];video=next(x for x in streams if x.get('codec_type')=='video')
 assert video['width']==w and video['height']==h
 report[name]={'exit':r.returncode,'video':video,'resize':False}
 print(name,json.dumps(report[name]),flush=True)
# Stream copy must remain a copy, without opening a CUDA context.
args=['-hide_banner','-loglevel','info','-i','/probe-media/Teste IFRO.mkv','-map','0:v:0','-an','-c:v','copy','-t','2','-f','hls','-hls_time','1','-hls_segment_filename','/out/copy%d.ts','-y','/out/copy.m3u8']
r=subprocess.run(run+args,capture_output=True,text=True,timeout=30)
text=r.stdout+r.stderr;(b/'copy.log').write_text(text)
assert r.returncode==0 and 'LEGACY390_BRIDGE' not in text
report['copy']={'exit':r.returncode,'bridge':False}
(b/'fallbacks.json').write_text(json.dumps(report,indent=2));print('copy OK',flush=True)

import subprocess,time,json,re,shlex,os
from pathlib import Path
b=Path('/srv/ifro-nvidia-390/resize-profile')
e=Path('/srv/ifro-nvidia-390/ffmpeg-full/evidence')
for p in sorted(e.glob('FFmpeg.Transcode*'),key=lambda p:p.stat().st_mtime,reverse=True):
 s=p.read_text(errors='replace')
 commands=[l for l in s.splitlines() if l.startswith('/opt/ifro-ffmpeg/bin/ffmpeg-jellyfin ')]
 if commands and 'filter_copyback' in s and ' -ss ' not in commands[0] and 'subtitles=' not in commands[0] and '/probe-media/Teste IFRO.mkv' in commands[0]:
  original=shlex.split(commands[0]);break
else:raise RuntimeError('No matching validated command')
image=subprocess.check_output(['docker','inspect','jellyfin','--format','{{.Image}}'],text=True).strip()
out=Path('/srv/media-stack/cache/jellyfin/resize-profile');(out/'cuda-cache').mkdir(exist_ok=True);os.chown(out/'cuda-cache',1000,1000)
run=['docker','run','--rm','--network','none','--memory=768m','--cpus=2','--user','1000:1000',
 '--device','/dev/nvidia0','--device','/dev/nvidiactl','--device','/dev/nvidia-uvm','--device','/dev/nvidia-uvm-tools',
 '-e','HOME=/tmp','-e','CUDA_CACHE_PATH=/out/cuda-cache','-e','LEGACY390_PINNED_DOWNLOAD=1','-e','LEGACY390_PINNED_POOL=1','-e','LEGACY390_PROFILE=1',
 '-e','LD_LIBRARY_PATH=/opt/ifro-ffmpeg/lib:/usr/lib/jellyfin-ffmpeg/lib:/opt/nvidia390',
 '-v','/srv/ifro-nvidia-390/ffmpeg-full/install/opt/ifro-ffmpeg:/opt/ifro-ffmpeg:ro',
 '-v','/srv/ifro-nvidia-390/ffmpeg-full/test-media:/probe-media:ro',
 '-v',str(out)+':/out',
 '-v','/usr/lib/x86_64-linux-gnu/nvidia/legacy-390xx:/opt/nvidia390:ro',
 '-v','/lib/x86_64-linux-gnu/libnvidia-fatbinaryloader.so.390.157:/usr/lib/x86_64-linux-gnu/libnvidia-fatbinaryloader.so.390.157:ro',
 '-v','/lib/x86_64-linux-gnu/libnvidia-ptxjitcompiler.so.1:/usr/lib/x86_64-linux-gnu/libnvidia-ptxjitcompiler.so.1:ro',
 '-e','LEGACY390_JELLYFIN_BRIDGE=1','--entrypoint','/opt/ifro-ffmpeg/bin/ffmpeg-jellyfin-resize',image]
report={}
for name,resize in [('native',False),('cuvid_resize',True)]:
 args=original[1:]
 args[0:0]=['-benchmark','-nostats']
 args[args.index('-hls_segment_filename')+1]='/out/'+name+'%d.ts';args[-1]='/out/'+name+'.m3u8'
 start=time.monotonic()
 with (b/(name+'-launcher.log')).open('w') as log:
  r=subprocess.run((run[:-3]+['-e','LEGACY390_CUVID_RESIZE=1']+run[-3:] if resize else run)+args,stdout=log,stderr=subprocess.STDOUT,timeout=150)
 text=(b/(name+'-launcher.log')).read_text()
 m=re.search(r'bench: utime=([\d.]+)s stime=([\d.]+)s rtime=([\d.]+)s',text)
 report[name]={'exit':r.returncode,'wall_seconds':round(time.monotonic()-start,3),'bench':list(map(float,m.groups())) if m else None,'gpu_resize':'LEGACY390_RESIZE' in text,'errors':[x for x in text.splitlines() if any(t in x for t in ['Error','error','Failed'])][-5:]}
 (b/'launcher-transcode.json').write_text(json.dumps(report,indent=2))
 assert report[name]['exit']==0 and report[name]['gpu_resize']==resize
 print(name,json.dumps(report[name]),flush=True)

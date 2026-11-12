import subprocess,json,re,time,shlex,os
from pathlib import Path
b=Path('/srv/ifro-nvidia-390/resize-profile');full=Path('/srv/ifro-nvidia-390/ffmpeg-full')
v=json.loads((b/'resize-validation.json').read_text());assert v.get('complete')
for p in sorted((full/'test-config/log').glob('FFmpeg.Transcode*'),key=lambda p:p.stat().st_mtime,reverse=True):
 s=p.read_text(errors='replace')
 lines=[l for l in s.splitlines() if l.startswith('/opt/ifro-ffmpeg/bin/ffmpeg-jellyfin-resize ')]
 if lines and 'LEGACY390_RESIZE' in s and ' -ss ' not in lines[0] and 'subtitles=' not in lines[0] and '/probe-media/Teste IFRO.mkv' in lines[0]:
  original=shlex.split(lines[0]);break
else:raise RuntimeError('Missing verified API command')
out=full/'test-cache/resize-benchmark';out.mkdir(exist_ok=True);os.chown(out,1000,1000)
report={}
for name,on in [('native_1',False),('resize_1',True),('resize_2',True),('native_2',False)]:
 args=original.copy();args[1:1]=['-benchmark','-nostats']
 args[args.index('-hls_segment_filename')+1]='/cache/resize-benchmark/'+name+'%d.ts'
 args[-1]='/cache/resize-benchmark/'+name+'.m3u8'
 cmd=['docker','exec','--user','1000:1000','-e','HOME=/config','-e','LEGACY390_CUVID_RESIZE='+str(int(on)),'jellyfin-legacy390-test',*args]
 t=time.monotonic()
 with (b/(name+'-api-benchmark.log')).open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=120)
 s=(b/(name+'-api-benchmark.log')).read_text()
 m=re.search(r'bench: utime=([\d.]+)s stime=([\d.]+)s rtime=([\d.]+)s',s)
 assert r.returncode==0 and ('LEGACY390_RESIZE' in s)==on
 report[name]={'exit':r.returncode,'seconds':round(time.monotonic()-t,3),'bench':list(map(float,m.groups())),'resize':on}
 (b/'matched-benchmark.json').write_text(json.dumps(report,indent=2))
 print(name,json.dumps(report[name]),flush=True)

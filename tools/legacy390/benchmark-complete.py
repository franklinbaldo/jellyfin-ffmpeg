import json,re,shlex,subprocess,time,os
from pathlib import Path
b=Path('/srv/ifro-nvidia-390/ffmpeg-full')
v=json.loads((b/'validation.json').read_text())
assert v.get('complete') and all(v.get(n,{}).get('ok') for n in ['h264_gpu','h264_subtitles','h264_seek','hevc_cpu_fallback'])
logs=sorted((b/'test-config/log').glob('FFmpeg.Transcode*'),key=lambda p:p.stat().st_mtime,reverse=True)
for p in logs:
 s=p.read_text(errors='replace')
 lines=[l for l in s.splitlines() if l.startswith('/opt/ifro-ffmpeg/bin/ffmpeg-jellyfin ')]
 if lines and 'filter_copyback' in s and ' -ss ' not in lines[0] and 'subtitles=' not in lines[0] and '/probe-media/Teste IFRO.mkv' in lines[0]:
  original=shlex.split(lines[0]);break
else:raise RuntimeError('No verified GPU command found')
out=b/'test-cache/benchmark';out.mkdir(exist_ok=True);os.chown(out,1000,1000)
report={}
for name,force in [('cpu',True),('gpu',False)]:
 args=original.copy()
 args[args.index('-hls_segment_filename')+1]='/cache/benchmark/'+name+'%d.ts'
 args[-1]='/cache/benchmark/'+name+'.m3u8'
 args[1:1]=['-benchmark','-nostats']
 cmd=['docker','exec','--user','1000:1000','-e','HOME=/config']
 if force:cmd+=['-e','LEGACY390_FORCE_CPU=1']
 cmd+=['jellyfin-legacy390-test',*args]
 start=time.monotonic()
 with (b/('complete-'+name+'.log')).open('w') as f:
  r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=120)
 text=(b/('complete-'+name+'.log')).read_text()
 m=re.search(r'bench: utime=([\d.]+)s stime=([\d.]+)s rtime=([\d.]+)s',text)
 report[name]={'exit':r.returncode,'wall_seconds':round(time.monotonic()-start,3),'gpu_used':'LEGACY390_BRIDGE' in text,'cpu_user_seconds':float(m[1]) if m else None,'cpu_system_seconds':float(m[2]) if m else None,'ffmpeg_wall_seconds':float(m[3]) if m else None,'errors':[l for l in text.splitlines() if 'Error' in l or 'error' in l][-5:]}
 assert r.returncode==0 and report[name]['gpu_used']!=force
 (b/'complete-benchmark.json').write_text(json.dumps(report,indent=2))
 print(name,json.dumps(report[name]),flush=True)

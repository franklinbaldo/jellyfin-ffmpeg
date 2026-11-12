import subprocess,time,json,re
from pathlib import Path
b=Path('/srv/ifro-nvidia-390/resize-profile')
common=['docker','exec','--user','1000:1000','-e','HOME=/config','-e','LEGACY390_PROFILE=1','jellyfin','nice','-n','10','/opt/ifro-ffmpeg/bin/ffmpeg','-hide_banner','-loglevel','info','-nostats','-benchmark']
cases=[
 ('native_cpu_scale',['-hwaccel','cuda','-hwaccel_output_format','cuda','-hwaccel_flags','+unsafe_output','-c:v','h264'],['hwdownload,format=nv12,scale=1280:720:flags=bicubic,format=yuv420p']),
 ('cuvid_gpu_scale',['-hwaccel','cuda','-hwaccel_output_format','cuda','-c:v','h264_cuvid','-resize','1280x720'],['hwdownload,format=nv12,format=yuv420p'])]
report={}
for name,flags,vf in cases:
 cmd=common+flags+['-threads','2','-i','/probe-media/Teste IFRO.mkv','-frames:v','600','-map','0:v:0','-vf',vf[0],'-an','-sn','-c:v','rawvideo','-f','null','-']
 # Fixture is mounted only in this one exec via existing host files below;
 # use the main server media path for its first real stream instead.
 samples=json.loads(Path('/srv/ifro-nvidia-390/ffmpeg-full/samples.json').read_text())
 cmd[cmd.index('/probe-media/Teste IFRO.mkv')]=samples['h264']['Path']
 start=time.monotonic()
 with (b/(name+'.log')).open('w') as out:
  try:code=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,timeout=120).returncode
  except subprocess.TimeoutExpired:code=124
 text=(b/(name+'.log')).read_text()
 m=re.search(r'bench: utime=([\d.]+)s stime=([\d.]+)s rtime=([\d.]+)s',text)
 report[name]={'exit':code,'seconds':round(time.monotonic()-start,3),'bench':m.groups() if m else None,'errors':[x for x in text.splitlines() if any(t in x for t in ['Error','error','Failed','Invalid'])][-8:]}
 (b/'probe.json').write_text(json.dumps(report,indent=2))
 print(name,json.dumps(report[name]),flush=True)

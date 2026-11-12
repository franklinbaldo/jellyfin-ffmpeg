import os,subprocess,json,time,re
from pathlib import Path
b=Path('/srv/ifro-nvidia-390/ffmpeg-legacy');os.chdir(b)
out=b/'results/bridge';out.mkdir(exist_ok=True)
cases=[
 ('cpu',[],[],False),
 ('cuvid_pageable',['-hwaccel','cuda','-c:v','h264_cuvid'],[],False),
 ('cuvid_pinned',['-hwaccel','cuda','-c:v','h264_cuvid'],[],True),
 ('nvdec_pageable',['-hwaccel','cuda','-hwaccel_output_format','cuda','-c:v','h264'],['-vf','hwdownload,format=nv12'],False),
 ('nvdec_pinned',['-hwaccel','cuda','-hwaccel_output_format','cuda','-c:v','h264'],['-vf','hwdownload,format=nv12'],True)]
report={}
for name,flags,filters,pinned in cases:
 env=dict(os.environ,LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu/nvidia/legacy-390xx',LEGACY390_PROFILE='1')
 if pinned:env['LEGACY390_PINNED_DOWNLOAD']='1'
 cmd=[str(b/'prefix/bin/ffmpeg'),'-hide_banner','-loglevel','info','-benchmark',*flags,'-i','motion.h264','-frames:v','120',*filters,'-pix_fmt','yuv420p','-c:v','rawvideo','-f','framehash','-y',str(out/(name+'.hash'))]
 start=time.monotonic()
 with (out/(name+'.log')).open('w') as f:
  try:r=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=100);code=r.returncode
  except subprocess.TimeoutExpired:code=124
 log=(out/(name+'.log')).read_text()
 metrics=[{'unit':m[0],'call':m[1],'calls':int(m[2]),'total_ms':float(m[3]),'max_ms':float(m[4])} for m in re.findall(r'LEGACY390_PROFILE ([^|]+) \| ([^|]+) \| calls=(\d+) total_ms=([\d.]+) max_ms=([\d.]+)',log)]
 p=out/(name+'.hash')
 hashes=[x.rsplit(',',1)[-1].strip() for x in p.read_text().splitlines() if x and not x.startswith('#')] if p.exists() else []
 report[name]={'exit':code,'wall_seconds':round(time.monotonic()-start,3),'frames':len(hashes),'unique_hashes':len(set(hashes)),'hashes':hashes,'matches_cpu':code==0 and len(hashes)==120 and (name=='cpu' or hashes==report['cpu']['hashes']),'metrics':metrics,'bench':re.findall(r'bench:.*',log)}
 (out/'summary.json').write_text(json.dumps(report,indent=2))
 print(name,code,report[name]['wall_seconds'],report[name]['matches_cpu'],flush=True)

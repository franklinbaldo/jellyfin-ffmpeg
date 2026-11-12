import os,subprocess,time,json,re
from pathlib import Path
b=Path('/srv/ifro-nvidia-390/ffmpeg-legacy');os.chdir(b)
out=b/'results/pool-integrity';out.mkdir(exist_ok=True)
cases=[('cpu',False,False),('nvdec_pool',True,True),('cuvid_pool',True,True)]
report={}
for name,gpu,pin in cases:
 env=dict(os.environ,LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu/nvidia/legacy-390xx',LEGACY390_PROFILE='1')
 if pin:env.update(LEGACY390_PINNED_DOWNLOAD='1',LEGACY390_PINNED_POOL='1')
 flags=(['-hwaccel','cuda','-c:v','h264_cuvid'] if name=='cuvid_pool' else ['-hwaccel','cuda','-hwaccel_output_format','cuda','-c:v','h264']) if gpu else []
 vf=['-vf','hwdownload,format=nv12'] if gpu and name!='cuvid_pool' else []
 cmd=[str(b/'prefix/bin/ffmpeg'),'-hide_banner','-loglevel','info','-benchmark',*flags,'-i','motion.h264','-frames:v','180',*vf,'-pix_fmt','yuv420p','-c:v','rawvideo','-f','framehash','-y',str(out/(name+'.hash'))]
 start=time.monotonic()
 with (out/(name+'.log')).open('w') as f:
  try:code=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=90).returncode
  except subprocess.TimeoutExpired:code=124
 log=(out/(name+'.log')).read_text()
 p=out/(name+'.hash')
 hashes=[x.rsplit(',',1)[-1].strip() for x in p.read_text().splitlines() if x and not x.startswith('#')] if p.exists() else []
 profile=[x for x in log.splitlines() if x.startswith('LEGACY390_PROFILE')]
 report[name]={'exit':code,'seconds':round(time.monotonic()-start,3),'frames':len(hashes),'unique_frames':len(set(hashes)),'hashes':hashes,'matches_cpu':code==0 and len(hashes)==180 and (name=='cpu' or hashes==report['cpu']['hashes']),'profile':profile,'bench':re.findall(r'bench:.*',log)}
 (out/'summary.json').write_text(json.dumps(report,indent=2))
 print(name,code,report[name]['seconds'],report[name]['matches_cpu'],flush=True)

assert all(x['matches_cpu'] for x in report.values())

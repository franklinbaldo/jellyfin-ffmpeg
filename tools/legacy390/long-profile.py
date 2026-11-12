import os,subprocess,time,json,re,bisect
from pathlib import Path
b=Path('/srv/ifro-nvidia-390/ffmpeg-legacy');os.chdir(b)
out=b/'results/long';out.mkdir(exist_ok=True)
cases=[('cpu_300',False,300),('gpu_300',True,300),('gpu_3000',True,3000),('cpu_3000',False,3000),('cpu_9000',False,9000),('gpu_9000',True,9000)]
report={}
for name,gpu,count in cases:
 env=dict(os.environ,LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu/nvidia/legacy-390xx',LEGACY390_PROFILE='1')
 if gpu:env['LEGACY390_PINNED_DOWNLOAD']='1'
 flags=['-hwaccel','cuda','-hwaccel_output_format','cuda','-c:v','h264'] if gpu else []
 filters=['-vf','hwdownload,format=nv12'] if gpu else []
 cmd=[str(b/'prefix/bin/ffmpeg'),'-hide_banner','-loglevel','info','-nostats','-stats_period','0.25','-progress','/dev/stdout','-benchmark',*flags,'-threads','2','-i','long.h264','-frames:v',str(count),*filters,'-pix_fmt','yuv420p','-c:v','rawvideo','-threads','2','-f','null','-']
 start=time.monotonic();events=[{'frame':0,'seconds':0.0}];pending={}
 with (out/(name+'.log')).open('w') as log:
  p=subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=log,text=True)
  for line in p.stdout:
   key,_,value=line.strip().partition('=')
   pending[key]=value
   if key=='progress':
    events.append({'frame':int(pending.get('frame',0)),'seconds':round(time.monotonic()-start,6)})
    pending={}
  code=p.wait()
 elapsed=time.monotonic()-start
 log=(out/(name+'.log')).read_text()
 # Interpolate the progress events to estimate the beginning and end of ranges.
 def at(frame):
  for a,z in zip(events,events[1:]):
   if a['frame']<=frame<=z['frame'] and z['frame']>a['frame']:
    return a['seconds']+(z['seconds']-a['seconds'])*(frame-a['frame'])/(z['frame']-a['frame'])
  return None
 windows=[]
 for lo,hi in [(0,min(count,300)),(300,min(count,1000)),(1000,min(count,3000)),(3000,count),(max(0,count-1000),count)]:
  if hi<=lo:continue
  a,z=at(lo),at(hi)
  if a is not None and z is not None and z>a:windows.append({'from':lo,'to':hi,'seconds':round(z-a,3),'fps':round((hi-lo)/(z-a),2)})
 report[name]={'exit':code,'seconds':round(elapsed,3),'requested_frames':count,'frames':events[-1]['frame'],'fps':round(events[-1]['frame']/elapsed,2),'windows':windows,'events':events,'profile':[l for l in log.splitlines() if l.startswith('LEGACY390_PROFILE')],'bench':re.findall(r'bench:.*',log),'command':cmd}
 (out/'summary.json').write_text(json.dumps(report,indent=2))
 print(name,code,report[name]['seconds'],report[name]['frames'],report[name]['fps'],flush=True)

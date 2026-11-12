import os,subprocess,json,re
from pathlib import Path
b=Path('/srv/ifro-nvidia-390/resize-profile')
position=os.environ.get('QUALITY_START','180')
source=json.loads(Path('/srv/ifro-nvidia-390/ffmpeg-full/samples.json').read_text())['h264']['Path']
graph='[0:v:0]hwdownload,format=nv12,format=yuv420p,setpts=PTS-STARTPTS,split=2[g1][g2];[1:v:0]scale=1280:720:flags=bicubic,format=yuv420p,setpts=PTS-STARTPTS,split=2[c1][c2];[g1][c1]psnr=stats_file=/cache/resize-profile/psnr.log[p];[g2][c2]ssim=stats_file=/cache/resize-profile/ssim.log[s]'
cmd=['docker','exec','--user','1000:1000','-e','HOME=/config','jellyfin','nice','-n','10','/opt/ifro-ffmpeg/bin/ffmpeg','-hide_banner','-loglevel','info','-nostats','-hwaccel','cuda','-hwaccel_output_format','cuda','-c:v','h264_cuvid','-resize','1280x720','-threads','2','-ss',position,'-i',source,'-threads','2','-c:v','h264','-ss',position,'-i',source,'-filter_complex',graph,'-map','[p]','-map','[s]','-frames:v:0','180','-frames:v:1','180','-an','-c:v','rawvideo','-f','null','-']
r=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
text=r.stdout+r.stderr
(b/('quality-'+position+'.log')).write_text(text)
ssim=re.findall(r'SSIM Y:[^\n]+',text)
psnr=re.findall(r'PSNR y:[^\n]+',text)
report={'exit':r.returncode,'ssim':ssim[-1:] or None,'psnr':psnr[-1:] or None,'errors':[x for x in text.splitlines() if any(t in x for t in ['Error','error','Failed'])][-5:]}
(b/('quality-'+position+'.json')).write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))

assert report['exit']==0 and report['ssim'] and report['psnr']

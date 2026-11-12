import ctypes as C,time,json
from pathlib import Path
cu=C.CDLL('libcuda.so.1')
def call(name,*args):
 r=getattr(cu,name)(*args)
 if r:raise RuntimeError((name,r))
call('cuInit',0)
dev=C.c_int();call('cuDeviceGet',C.byref(dev),0)
ctx=C.c_void_p();call('cuCtxCreate_v2',C.byref(ctx),0,dev)
size=1920*1080*3//2
gpu=C.c_uint64();call('cuMemAlloc_v2',C.byref(gpu),C.c_size_t(size))
call('cuMemsetD8_v2',gpu,0,C.c_size_t(size))
pageable=C.create_string_buffer(size)
pinned=C.c_void_p();call('cuMemHostAlloc',C.byref(pinned),C.c_size_t(size),0)
report={}
for name,host in [('pageable',C.cast(pageable,C.c_void_p)),('pinned',pinned)]:
 times=[]
 for i in range(100):
  t=time.perf_counter()
  call('cuMemcpyDtoH_v2',host,gpu,C.c_size_t(size))
  times.append(time.perf_counter()-t)
 report[name]={'bytes_per_copy':size,'first_copy_ms':times[0]*1000,'first10_mean_ms':sum(times[:10])*100,'last90_mean_ms':sum(times[10:])/90*1000,'last90_MBps':size/(sum(times[10:])/90)/1e6}
call('cuMemFreeHost',pinned);call('cuMemFree_v2',gpu);call('cuCtxDestroy_v2',ctx)
p=Path('/srv/ifro-nvidia-390/ffmpeg-legacy/results/dma.json')
p.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))

# Legacy NVIDIA 390 bridge prototype

Base: jellyfin-ffmpeg v8.1.3-2, nv-codec-headers n13.0.19.1.
Apply nv-codec-headers.patch before building headers. This makes five newer,
unused API functions optional; it does not emulate their behavior.

The C bridge in libavutil/hwcontext_cuda.c is opt-in:
LEGACY390_PINNED_DOWNLOAD=1 enables pinned-host staging for device-to-host
frame transfers. Each transfer gets its own staging allocation; no shared
scratch buffer or new concurrency assumptions. Allocation failure returns an
error. Ordinary transfers retain their existing path when the variable is unset.

LEGACY390_PROFILE=1 records driver-call wall time, count, maximum and first
10/50 call totals. Measurements from different decoder/filter threads overlap
and must not be added together as independent elapsed-time stages.

Pinned staging waits for GPU copies before copying rows to the caller's frame
buffers. It uses the existing CUDA driver ABI, without the CUDA Toolkit.
GPU-to-GPU and host-to-device transfers are unchanged.

The binary is deliberately reduced for H.264 decoding and frame verification;
it is not a complete replacement for production Jellyfin FFmpeg.
The supplied operational probes target the private IFRO build directory and
expect an existing motion.h264 sample. No media sample is included in git.

## Long-run profile, 2026-11-12
Matched 1080p H.264 prefixes; same binary, decoder threads=2,
rawvideo YUV420P output to null, pinned staging enabled only for GPU.
No per-frame SHA256 in these throughput tests. Progress sampled every
250 ms; interval speeds interpolate progress and are approximate.
CPU/GPU elapsed: 300 frames 4.153/3.762 s; 3000 frames 36.633/29.469 s;
9000 frames 110.718/89.025 s. All requested frames completed successfully.
GPU steady intervals approximately 98–104 fps after the initial section;
CPU approximately 80–84 fps. Source content varies, so differences between
early/late intervals cannot all be attributed to warm-up.
Full long-run aggregate results in long-profile-results.json.

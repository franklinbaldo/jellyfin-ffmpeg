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

#!/bin/bash
cd /srv/ifro-nvidia-390/ffmpeg-legacy
export LEGACY390_PROFILE=1 LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/nvidia/legacy-390xx
for mode in pageable pinned; do
 if [ "$mode" = pinned ]; then export LEGACY390_PINNED_DOWNLOAD=1; else unset LEGACY390_PINNED_DOWNLOAD; fi
 ./prefix/bin/ffmpeg -hide_banner -loglevel info -benchmark -hwaccel cuda -hwaccel_output_format cuda -c:v h264 -i motion.h264 -frames:v 180 -vf hwdownload,format=nv12 -pix_fmt nv12 -c:v rawvideo -f null - >results/warmup-$mode.log 2>&1
 echo "$mode exit=$?"
done

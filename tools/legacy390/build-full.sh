#!/bin/bash
set -euo pipefail
exec > /work/build.log 2>&1
trap 'echo BUILD_FAILED; date -Is' ERR
date -Is
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends build-essential pkg-config nasm \
 libgnutls28-dev libgmp-dev libass-dev libfreetype-dev libfribidi-dev \
 libfontconfig-dev libharfbuzz-dev libbluray-dev libmp3lame-dev libopus-dev \
 libtheora-dev libvorbis-dev libopenmpt-dev libdav1d-dev libwebp-dev \
 libvpx-dev libx264-dev libx265-dev libzvbi-dev libzimg-dev libdrm-dev \
 libva-dev zlib1g-dev libxml2-dev
rm -rf /var/lib/apt/lists/*
mkdir -p /work/headers /work/build /work/install
cp -a /headers/. /work/headers/
make -C /work/headers PREFIX=/work/header-prefix install
cd /work/build
PKG_CONFIG_PATH=/work/header-prefix/lib/pkgconfig /src/configure \
 --prefix=/opt/ifro-ffmpeg --target-os=linux --extra-version=Jellyfin-legacy390 \
 --disable-unstable --disable-doc --disable-ffplay --disable-debug \
 --disable-static --enable-shared --enable-gpl --enable-version3 \
 --disable-autodetect --enable-zlib --enable-gmp --enable-gnutls \
 --enable-libxml2 --enable-libass --enable-libfreetype --enable-libfribidi \
 --enable-libfontconfig --enable-libharfbuzz --enable-libbluray \
 --enable-libmp3lame --enable-libopus --enable-libtheora --enable-libvorbis \
 --enable-libopenmpt --enable-libdav1d --enable-libwebp --enable-libvpx \
 --enable-libx264 --enable-libx265 --enable-libzvbi --enable-libzimg \
 --enable-libdrm --enable-vaapi --enable-ffnvcodec --enable-cuda \
 --enable-cuvid --enable-nvdec --enable-nvenc --disable-cuda-llvm \
 --extra-cflags=-I/work/header-prefix/include \
 --extra-ldflags=-Wl,-rpath,/opt/ifro-ffmpeg/lib
nice -n 10 make -j2
make DESTDIR=/work/install install
cc -std=gnu17 -O2 -Wall -Wextra -Werror  -o /work/install/opt/ifro-ffmpeg/bin/ffmpeg-jellyfin  /src/tools/legacy390/jellyfin-bridge.c -ldl
du -sh /work/build /work/install
date -Is
echo BUILD_OK

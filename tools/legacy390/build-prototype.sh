#!/bin/bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(git -C "$script_dir" rev-parse --show-toplevel)"
work_dir="${LEGACY390_WORKDIR:-$script_dir/work}"
mkdir -p "$work_dir"
work_dir="$(cd "$work_dir" && pwd)"
if [ ! -d "$work_dir/headers/.git" ]; then
 git clone --depth 1 --branch n13.0.19.1 https://github.com/FFmpeg/nv-codec-headers.git "$work_dir/headers"
fi
if git -C "$work_dir/headers" apply --check "$script_dir/nv-codec-headers.patch"; then
 git -C "$work_dir/headers" apply "$script_dir/nv-codec-headers.patch"
else
 git -C "$work_dir/headers" apply --reverse --check "$script_dir/nv-codec-headers.patch"
fi
make -C "$work_dir/headers" PREFIX="$work_dir/prefix" install
mkdir -p "$work_dir/build"
cd "$work_dir/build"
PKG_CONFIG_PATH="$work_dir/prefix/lib/pkgconfig" "$repo_dir/configure" \
 --prefix="$work_dir/prefix" --extra-cflags="-I$work_dir/prefix/include" \
 --disable-everything --disable-autodetect --disable-doc --disable-network \
 --disable-debug --disable-shared --enable-static --enable-ffmpeg --enable-ffprobe \
 --enable-ffnvcodec --enable-cuda --enable-cuvid --enable-nvdec --disable-nvenc \
 --enable-hwaccel=h264_nvdec --enable-decoder=h264,h264_cuvid \
 --enable-parser=h264 --enable-demuxer=h264 --enable-muxer=null,framehash,rawvideo \
 --enable-protocol=file --enable-filter=hwdownload,format,scale \
 --enable-encoder=rawvideo --extra-version=legacy390-prototype
make -j"${JOBS:-2}"
make install
printf 'FFmpeg: %s/prefix/bin/ffmpeg\n' "$work_dir"

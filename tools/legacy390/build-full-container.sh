#!/bin/bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(git -C "$script_dir" rev-parse --show-toplevel)"
work_dir="${LEGACY390_FULL_WORKDIR:-$script_dir/work-full}"
mkdir -p "$work_dir"
work_dir="$(cd "$work_dir" && pwd)"
headers_dir="$work_dir/header-source"
if [ ! -d "$headers_dir/.git" ]; then
 git clone --depth 1 --branch n13.0.19.1 https://github.com/FFmpeg/nv-codec-headers.git "$headers_dir"
fi
if git -C "$headers_dir" apply --check "$script_dir/nv-codec-headers.patch"; then
 git -C "$headers_dir" apply "$script_dir/nv-codec-headers.patch"
else
 git -C "$headers_dir" apply --reverse --check "$script_dir/nv-codec-headers.patch"
fi
build_image="${JELLYFIN_BUILD_IMAGE:-$(docker inspect jellyfin --format '{{.Image}}')}"
docker run --rm --memory=1200m --cpus=2 --pids-limit=256 \
 --entrypoint /bin/bash -v "$repo_dir:/src:ro" \
 -v "$headers_dir:/headers:ro" -v "$work_dir:/work" \
 "$build_image" /src/tools/legacy390/build-full.sh
printf 'Instalação: %s/install/opt/ifro-ffmpeg\n' "$work_dir"

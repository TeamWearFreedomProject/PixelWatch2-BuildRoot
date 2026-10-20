#!/bin/bash
# Build a regular ext4 image without loop devices, chroot, or executing target ARM code.
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(realpath "$1")
DEVICE=$(realpath "$2")
OUT=$(realpath -m "$3")
test "$(id -u)" -eq 0 || { echo 'Run assembly as root to preserve numeric ownership.' >&2; exit 1; }
ROOTFS="$WORK/rootfs"
test ! -e "$ROOTFS" || { echo 'Use a fresh rootfs work directory.' >&2; exit 1; }
mkdir -p "$ROOTFS" "$OUT"
tar --numeric-owner -xpzf "$WORK/inputs/ubuntu-touch-android9plus-rootfs-armhf.tar.gz" -C "$ROOTFS"
for archive in "$WORK/inputs/halium_halium_arm.tar.xz" "$DEVICE"; do
    tar --numeric-owner -xpf "$archive" -C "$ROOTFS" --strip-components=1 --wildcards 'system/*'
done
# The Android container image is distinct from Ubuntu's host rootfs.
ANDROID="$ROOTFS/var/lib/lxc/android"
if [ -f "$ANDROID/system.img" ] && [ ! -e "$ANDROID/android-rootfs.img" ]; then
    mv "$ANDROID/system.img" "$ANDROID/android-rootfs.img"
fi
test -s "$ANDROID/android-rootfs.img"
test -s "$ROOTFS/usr/bin/apt"
# Halium's reviewed mountroot checks this marker to retain a writable host rootfs.
touch "$ROOTFS/.writable_image"
cp "$WORK/sources.json" "$ROOTFS/etc/aurora-stage24-sources.json"
cp "$WORK/sources.json" "$OUT/sources.json"
SIZE=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["target"]["system_partition_size"])' "$WORK/sources.json")
truncate -s "$SIZE" "$OUT/ubuntu.img"
mke2fs -q -t ext4 -F -b 4096 -m 0 -O '^metadata_csum' -d "$ROOTFS" "$OUT/ubuntu.img"
# e2fsprogs 1.46 (Ubuntu 22.04) does not recognize even ^orphan_file.
# Newer hosts may enable it by default; disable it only when actually present.
if dumpe2fs -h "$OUT/ubuntu.img" 2>/dev/null | grep -qw orphan_file; then
    tune2fs -O '^orphan_file' "$OUT/ubuntu.img"
fi
e2fsck -fn "$OUT/ubuntu.img"
python3 "$PROJECT/stage24/audit.py" rootfs "$OUT/ubuntu.img" --output "$OUT/audit.json"
cp "$PROJECT/docs/STAGE24.md" "$OUT/README-STAGE24.md"
zstd -T2 -10 --force "$OUT/ubuntu.img" -o "$OUT/ubuntu.img.zst"
(cd "$OUT" && sha256sum ubuntu.img ubuntu.img.zst sources.json audit.json README-STAGE24.md > SHA256SUMS)

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/stage2-work"
BR="$WORK/buildroot"
OUTPUT="$WORK/br-output"
BUILDROOT_REF="2025.02.1"

if [[ -s "$OUTPUT/images/rootfs.cpio.gz" && -s "$OUTPUT/images/rootfs.tar" ]]; then
  echo "Using cached ARM32 rootfs; verifying contents."
else
  if [[ ! -e "$BR/Makefile" ]]; then
    git clone --depth 1 --branch "$BUILDROOT_REF" \
      https://github.com/buildroot/buildroot.git "$BR"
  fi
  make -C "$BR" BR2_EXTERNAL="$ROOT" O="$OUTPUT" aurora_arm32_defconfig
  make -C "$BR" O="$OUTPUT" -j2
fi

test -s "$OUTPUT/images/rootfs.cpio.gz"
test -s "$OUTPUT/images/rootfs.tar"
mkdir -p "$WORK/rootfs-check"
tar -xf "$OUTPUT/images/rootfs.tar" -C "$WORK/rootfs-check"
test -x "$WORK/rootfs-check/init"
test -x "$WORK/rootfs-check/sbin/init"
file "$WORK/rootfs-check/bin/busybox" | grep -E 'ELF 32-bit.*ARM'
echo "ARM32 rootfs is ready for embedded-initramfs build."

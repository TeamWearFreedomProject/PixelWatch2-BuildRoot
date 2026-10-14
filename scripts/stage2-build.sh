#!/usr/bin/env bash
set -euo pipefail

# Stage 2 - link ARM32 Buildroot rootfs into ARM64 Linux and package boot.img.
# Run scripts/stage2-preflight.sh and scripts/stage2-rootfs.sh first.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/stage2-work"
KO="$WORK/kernel-out"
KS="$WORK/kernel"
TOOLS="$WORK/mkbootimg"
OUT="$ROOT/stage2-artifacts"
ROOTFS="$WORK/br-output/images/rootfs.cpio.gz"

test -s "$ROOTFS" || { echo "ARM32 rootfs missing"; exit 1; }
test -s "$KO/.config" || { echo "Kernel config missing"; exit 1; }
test -d "$KS/.git" || { echo "Kernel checkout missing"; exit 1; }
mkdir -p "$OUT"

echo "=== Embed Buildroot initramfs in ARM64 kernel ==="
COMMON=( -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- )
"$KS/scripts/config" --file "$KO/.config" \
  -e BLK_DEV_INITRD \
  --set-str INITRAMFS_SOURCE "$ROOTFS" \
  -d WERROR
make "${COMMON[@]}" olddefconfig
grep -Fqx "CONFIG_INITRAMFS_SOURCE=\"$ROOTFS\"" "$KO/.config"
grep -qx 'CONFIG_ARM64=y' "$KO/.config"
grep -qx 'CONFIG_COMPAT=y' "$KO/.config"

echo "=== Compile ARM64 uncompressed Image ==="
make "${COMMON[@]}" -j2 Image
IMAGE="$KO/arch/arm64/boot/Image"
test -s "$IMAGE"
file "$IMAGE"

echo "=== Build Android boot image header v4 ==="
if [[ ! -d "$TOOLS/.git" ]]; then
  git clone --depth 1 --branch android13-release \
    https://android.googlesource.com/platform/system/tools/mkbootimg "$TOOLS"
fi
python3 "$TOOLS/mkbootimg.py" \
  --kernel "$IMAGE" \
  --header_version 4 \
  --pagesize 4096 \
  --output "$OUT/boot.img"

echo "=== Research-only structural verification ==="
python3 "$ROOT/scripts/verify_bootimg.py" \
  --boot "$OUT/boot.img" --kernel "$IMAGE" --max-bytes 67108864 \
  | tee "$OUT/verification.txt"
cp "$KO/.config" "$OUT/kernel.config"
cp "$ROOTFS" "$OUT/rootfs.cpio.gz"
{
  printf 'Buildroot: 2025.02.1\n'
  printf 'Research config: e3d5fc73b4c97ea19ae5a0fd1d4eee1324703ad0\n'
  printf 'Kernel commit: %s\n' "$(git -C "$KS" rev-parse HEAD)"
  printf 'Kernel patches: ci-only BAM NDP guards and experimental QUSB SCM helper\n'
  printf 'mkbootimg commit: %s\n' "$(git -C "$TOOLS" rev-parse HEAD)"
  printf 'User ABI: ARM32 musl\nKernel ABI: ARM64\n'
  printf 'Device tested: NO\nFlashable: NO\n'
} > "$OUT/SOURCES.txt"
( cd "$OUT" && sha256sum boot.img rootfs.cpio.gz kernel.config > SHA256SUMS )
echo "UNVERIFIED research boot image produced; DO NOT FLASH."

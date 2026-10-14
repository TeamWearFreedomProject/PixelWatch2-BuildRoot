#!/usr/bin/env bash
set -euo pipefail

# Stage 2 = build a research-only ARM64 Linux kernel + built-in ARM32 initramfs.
# No device is accessed, and no flashing commands are executed.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${ROOT}/stage2-work"
BR="${WORK}/buildroot"
KO="${WORK}/kernel-out"
KS="${WORK}/kernel"
TOOLS="${WORK}/mkbootimg"
OUT="${ROOT}/stage2-artifacts"
BUILDROOT_REF="2025.02.1"
KERNEL_REF="android-msm-eos-5.15-tm-wear-kr3-pixel-watch"
AURORA_RESEARCH_SHA="e3d5fc73b4c97ea19ae5a0fd1d4eee1324703ad0"

mkdir -p "$WORK" "$KO" "$OUT"
echo "=== Stage 2: ARM32 Buildroot userspace ==="
if [[ ! -e "$BR/Makefile" ]]; then
  git clone --depth 1 --branch "$BUILDROOT_REF" \
    https://github.com/buildroot/buildroot.git "$BR"
fi
make -C "$BR" BR2_EXTERNAL="$ROOT" O="$WORK/br-output" aurora_arm32_defconfig
make -C "$BR" O="$WORK/br-output" -j2

ROOTFS="$WORK/br-output/images/rootfs.cpio.gz"
test -s "$ROOTFS"
mkdir -p "$WORK/rootfs-check"
tar -xf "$WORK/br-output/images/rootfs.tar" -C "$WORK/rootfs-check"
test -x "$WORK/rootfs-check/init"
test -x "$WORK/rootfs-check/sbin/init"
file "$WORK/rootfs-check/bin/busybox" | grep -E 'ELF 32-bit.*ARM'

echo "=== Stage 2: source kernel + upstream research configuration ==="
if [[ ! -d "$KS/.git" ]]; then
  git clone --depth 1 --branch "$KERNEL_REF" \
    https://android.googlesource.com/kernel/msm "$KS"
fi
curl --fail --location --retry 3 \
  "https://raw.githubusercontent.com/argosphil/aurora/${AURORA_RESEARCH_SHA}/defconfig" \
  --output "$KO/.config"
test -s "$KO/.config"
test "$(grep -c '^CONFIG_ARM64=y$' "$KO/.config")" -eq 1
test "$(grep -c '^CONFIG_COMPAT=y$' "$KO/.config")" -eq 1

echo "=== Stage 2: configure built-in initramfs ==="
COMMON=( -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- )
make "${COMMON[@]}" olddefconfig
"$KS/scripts/config" --file "$KO/.config" \
    -e BLK_DEV_INITRD \
    --set-str INITRAMFS_SOURCE "$ROOTFS" \
    -d WERROR
make "${COMMON[@]}" olddefconfig
grep -Fqx "CONFIG_INITRAMFS_SOURCE=\"$ROOTFS\"" "$KO/.config"
grep -qx 'CONFIG_ARM64=y' "$KO/.config"
grep -qx 'CONFIG_COMPAT=y' "$KO/.config"

echo "=== Stage 2: compile ARM64 Image (uncompressed) ==="
make "${COMMON[@]}" -j2 Image
IMAGE="$KO/arch/arm64/boot/Image"
test -s "$IMAGE"
file "$IMAGE"

echo "=== Stage 2: assemble Android boot header v4 ==="
git clone --depth 1 --branch android13-release \
  https://android.googlesource.com/platform/system/tools/mkbootimg "$TOOLS"
python3 "$TOOLS/mkbootimg.py" \
  --kernel "$IMAGE" \
  --header_version 4 \
  --pagesize 4096 \
  --output "$OUT/boot.img"

echo "=== Stage 2: inspect research-only boot image ==="
python3 "$ROOT/scripts/verify_bootimg.py" \
  --boot "$OUT/boot.img" --kernel "$IMAGE" --max-bytes 67108864 \
  | tee "$OUT/verification.txt"
cp "$KO/.config" "$OUT/kernel.config"
cp "$ROOTFS" "$OUT/rootfs.cpio.gz"
{
  printf 'Buildroot ref: %s\n' "$BUILDROOT_REF"
  printf 'Argosphil config commit: %s\n' "$AURORA_RESEARCH_SHA"
  printf 'Kernel ref: %s\n' "$KERNEL_REF"
  printf 'Kernel commit: %s\n' "$(git -C "$KS" rev-parse HEAD)"
  printf 'mkbootimg commit: %s\n' "$(git -C "$TOOLS" rev-parse HEAD)"
  printf 'Source ABI: ARM32 musl\nKernel ABI: ARM64\n'
  printf 'Hardware boot verified: NO\nFlashable: NO\n'
} > "$OUT/SOURCES.txt"
( cd "$OUT" && sha256sum boot.img rootfs.cpio.gz kernel.config > SHA256SUMS )
echo "Produced research-only $OUT/boot.img; NOT FLASHABLE."

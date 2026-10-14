#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/stage2-work"
KS="$WORK/kernel"
KO="$WORK/kernel-out"
KERNEL_REF="android-msm-eos-5.15-tm-wear-kr3-pixel-watch"
AURORA_RESEARCH_SHA="e3d5fc73b4c97ea19ae5a0fd1d4eee1324703ad0"

mkdir -p "$WORK" "$KO"
if [[ ! -d "$KS/.git" ]]; then
  git clone --depth 1 --branch "$KERNEL_REF" \
    https://android.googlesource.com/kernel/msm "$KS"
fi
curl --fail --location --retry 3 \
  "https://raw.githubusercontent.com/argosphil/aurora/${AURORA_RESEARCH_SHA}/defconfig" \
  --output "$KO/.config"

test -s "$KO/.config"
grep -qx 'CONFIG_ARM64=y' "$KO/.config"
grep -qx 'CONFIG_COMPAT=y' "$KO/.config"

COMMON=( -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- )
make "${COMMON[@]}" olddefconfig
"$KS/scripts/config" --file "$KO/.config" \
  -e BLK_DEV_INITRD --set-str INITRAMFS_SOURCE '' -d WERROR
make "${COMMON[@]}" olddefconfig

python3 "$ROOT/scripts/patch_bam_ndp.py" \
  "$KS/drivers/soc/qcom/sps/bam.c" "$KO/.config"
python3 "$ROOT/scripts/patch_qusb_scm.py" "$KS"

echo "=== Fast-fail: compile three previously problematic driver objects ==="
# Catch BAM / QUSB / SCM errors before expensive Buildroot and full Image.
make "${COMMON[@]}" -j2 \
  drivers/soc/qcom/sps/bam.o \
  drivers/firmware/qcom_scm.o \
  drivers/usb/phy/phy-msm-qusb.o

echo "All three targeted kernel objects compiled. Full kernel NOT yet validated."

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
  -e BLK_DEV_INITRD --set-str INITRAMFS_SOURCE '' -d WERROR \
  -d QCOM_POWER_SUPPLY -d QPNP_SMBLITE -d QTI_QBG
make "${COMMON[@]}" olddefconfig

# This upstream kernel tree lacks external google-modules/bms headers used by
# the in-tree qpnp-smblite driver. Match AsteroidOS' aurora sw5100.fragment
# when doing compilation-only experiments. This DOES NOT mean the resulting
# kernel supports battery monitoring or safe charging on real hardware.
for sym in QCOM_POWER_SUPPLY QPNP_SMBLITE QTI_QBG; do
  if grep -Eq "^CONFIG_${sym}=[ym]$" "$KO/.config"; then
    echo "ERROR: CONFIG_${sym} remained enabled; aborting before expensive build"
    exit 1
  fi
done
echo "Power supply vendor drivers omitted for offline compile only; no device boot validation."

python3 "$ROOT/scripts/patch_bam_ndp.py" \
  "$KS/drivers/soc/qcom/sps/bam.c" "$KO/.config"
python3 "$ROOT/scripts/patch_qusb_scm.py" "$KS"

echo "=== Fast-fail: compile BAM, SCM, QUSB and power-supply directory ==="
# Catch previously failing objects and new power-supply errors before Buildroot.
make "${COMMON[@]}" -j2 \
  drivers/soc/qcom/sps/bam.o \
  drivers/firmware/qcom_scm.o \
  drivers/usb/phy/phy-msm-qusb.o \
  drivers/power/supply/qcom/

echo "Targeted kernel objects and power-supply directory compiled. Full kernel NOT yet validated."

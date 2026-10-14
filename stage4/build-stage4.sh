#!/usr/bin/env bash
set -euo pipefail
# Stage 4: build-only, NOT a bootable/flashable device image.
# The SOUND=n setting is meant to prevent Linux ALSA sound output.
# It does not validate the haptic subsystem or bootloader/vendor audio paths.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KS="$ROOT/stage2-work/kernel"
KO="$ROOT/stage2-work/kernel-out"
ROOTFS="$ROOT/stage2-work/br-output/images/rootfs.cpio.gz"
OUT="$ROOT/stage4-artifacts"

test -f "$KO/.config"
test -s "$ROOTFS"
test -d "$KS/.git"
mkdir -p "$OUT"

COMMON=( -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- )
echo "=== Stage 4: disable Linux sound core before linking kernel ==="
"$KS/scripts/config" --file "$KO/.config" \
  -d SOUND \
  -d SND \
  -d SND_SOC \
  -d SND_USB_AUDIO
make "${COMMON[@]}" olddefconfig

grep -Fxq '# CONFIG_SOUND is not set' "$KO/.config" || {
  echo 'STOP: SOUND unexpectedly enabled'; exit 1;
}
grep -Fxq 'CONFIG_ARM64=y' "$KO/.config"
grep -Fxq 'CONFIG_COMPAT=y' "$KO/.config"

# Stage 2's kernel-first compiler guards and QUSB experiment remain present.
# Keep power-management omissions explicit: this cannot boot safely.
for symbol in QCOM_POWER_SUPPLY QPNP_SMBLITE QTI_QBG; do
  if grep -Eq "^CONFIG_${symbol}=[ym]$" "$KO/.config"; then
    echo "Unreviewed power driver state: ${symbol}; stop."
    exit 1
  fi
done

echo "=== Stage 4: build ARM64 Image with ARM32 adbd rootfs ==="
# Stage 2's linker/packager is reused; it will read the stage4 rootfs at
# stage2-work/br-output/images/rootfs.cpio.gz and preserve SOUND=n.
bash "$ROOT/scripts/stage2-build.sh"

grep -Fxq '# CONFIG_SOUND is not set' "$KO/.config" || {
  echo 'STOP: SOUND re-enabled during kernel build'; exit 1;
}
# Check adbd resides in the actual built-in initramfs payload source.
test -s "$ROOT/stage4-rootfs-verification.txt"
cp "$ROOT/stage2-artifacts/"* "$OUT/"
test -s "$OUT/boot.img"
test -s "$OUT/rootfs.cpio.gz"

cat >> "$OUT/SOURCES.txt" <<'EOF'

Stage 4 research profile:
- rootfs variant: aurora_arm32_adbd_defconfig (ARM32 /usr/bin/adbd)
- Linux CONFIG_SOUND=n (haptic functionality NOT validated)
- adbd is NOT started and USB gadget is NOT configured
- power/charger/fuel gauge disabled; unsafe to boot on hardware
- QUSB SCM helper is experimental, not hardware validated
- BOOT/FLASH: FORBIDDEN. Offline CI validation only.
EOF
cp "$ROOT/stage4-rootfs-verification.txt" "$OUT/adbd-check.txt"
cat > "$OUT/README-DO-NOT-BOOT.txt" <<'EOF'
STAGE 4 OFFLINE RESEARCH ARTIFACT ONLY.
Do not run fastboot boot/flash, or install this onto a Pixel Watch 2.
This kernel deliberately lacks critical power/charger drivers and uses
an unverified QUSB SCM patch. ADB binary availability is NOT USB ADB.
Linux SOUND=n is checked, but full hardware speaker silence cannot be
proven without separately validated device-specific hardware support.
EOF
(
  cd "$OUT"
  sha256sum boot.img rootfs.cpio.gz kernel.config > SHA256SUMS
)
echo 'Stage 4 boot.img compiled, NOT suitable for any hardware operation.'

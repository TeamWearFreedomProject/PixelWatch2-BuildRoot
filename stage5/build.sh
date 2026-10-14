#!/usr/bin/env bash
set -euo pipefail

# CI-only Stage 5: no hardware operations and NOT a boot-safe image.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/stage2-work"
BR="$WORK/buildroot"
BR_OUT="$WORK/br-output"
KS="$WORK/kernel"
KO="$WORK/kernel-out"
OUT="$ROOT/stage5-artifacts"
mkdir -p "$WORK" "$OUT"

echo "=== Build Stage 5 ARM32 rootfs with USB CDC ACM debug files ==="
if [[ -s "$BR_OUT/images/rootfs.tar" && -s "$BR_OUT/images/rootfs.cpio.gz" ]]; then
    echo "Stage 5-specific rootfs cache available"
else
    if [[ ! -f "$BR/Makefile" ]]; then
        git clone --depth 1 --branch 2025.02.1 \
            https://github.com/buildroot/buildroot.git "$BR"
    fi
    make -C "$BR" BR2_EXTERNAL="$ROOT" O="$BR_OUT" aurora_arm32_adbd_defconfig
    sed -i -e '/^BR2_ROOTFS_OVERLAY=/d' \
           -e '/^BR2_ROOTFS_POST_BUILD_SCRIPT=/d' "$BR_OUT/.config"
    cat >> "$BR_OUT/.config" <<'EOF'
BR2_ROOTFS_OVERLAY="$(BR2_EXTERNAL_AURORA_WATCH_PATH)/board/google/aurora/rootfs-overlay $(BR2_EXTERNAL_AURORA_WATCH_PATH)/stage5/rootfs-overlay"
BR2_ROOTFS_POST_BUILD_SCRIPT="$(BR2_EXTERNAL_AURORA_WATCH_PATH)/stage5/post-build.sh"
EOF
    make -C "$BR" BR2_EXTERNAL="$ROOT" O="$BR_OUT" olddefconfig
    grep -Fxq 'BR2_PACKAGE_ANDROID_TOOLS_ADBD=y' "$BR_OUT/.config"
    grep -Fq '/stage5/rootfs-overlay' "$BR_OUT/.config"
    grep -Fq '/stage5/post-build.sh' "$BR_OUT/.config"
    make -C "$BR" BR2_EXTERNAL="$ROOT" O="$BR_OUT" -j2
fi

test -s "$BR_OUT/images/rootfs.cpio.gz"
test -s "$BR_OUT/images/rootfs.tar"
mkdir -p "$WORK/stage5-verify"
tar -xf "$BR_OUT/images/rootfs.tar" -C "$WORK/stage5-verify"
test -x "$WORK/stage5-verify/usr/bin/adbd"
test -x "$WORK/stage5-verify/usr/sbin/aurora-acm"
test -x "$WORK/stage5-verify/etc/init.d/S90aurora-acm"
test -f "$WORK/stage5-verify/etc/aurora/dev-acm-enabled"
grep -Fq 'ttyGS0::respawn:/sbin/getty -L 115200 ttyGS0 vt100' \
    "$WORK/stage5-verify/etc/inittab"
file "$WORK/stage5-verify/bin/busybox" | grep -q 'ELF 32-bit.*ARM'
file "$WORK/stage5-verify/usr/bin/adbd" | grep -q 'ELF 32-bit.*ARM'
sh -n "$WORK/stage5-verify/usr/sbin/aurora-acm"
sh -n "$WORK/stage5-verify/etc/init.d/S90aurora-acm"
echo "Verified ARM32 adbd and USB-serial getty in offline rootfs"

echo "=== Check kernel audio, USB and battery-gauge states ==="
test -d "$KS/.git"
test -s "$KO/.config"
"$KS/scripts/config" --file "$KO/.config" \
    -d SOUND -d SND -d SND_SOC -d SND_USB_AUDIO
make -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
grep -Fxq '# CONFIG_SOUND is not set' "$KO/.config"
grep -Fxq 'CONFIG_COMPAT=y' "$KO/.config"
for sym in USB_GADGET USB_DWC3 USB_CONFIGFS USB_CONFIGFS_ACM USB_F_ACM; do
    grep -Fxq "CONFIG_$sym=y" "$KO/.config" || {
        echo "ERROR: missing $sym. Aborting before full kernel compilation."
        exit 1
    }
done
for sym in QCOM_POWER_SUPPLY QPNP_SMBLITE QTI_QBG; do
    if grep -Eq "^CONFIG_$sym=[ym]$" "$KO/.config"; then
        echo "ERROR: unexpected power module $sym"
        exit 1
    fi
done

echo "=== Package ARM64 kernel with ARM32 serial initramfs ==="
bash "$ROOT/scripts/stage2-build.sh"
cp "$ROOT/stage2-artifacts/boot.img" "$OUT/"
cp "$ROOT/stage2-artifacts/rootfs.cpio.gz" "$OUT/"
cp "$ROOT/stage2-artifacts/kernel.config" "$OUT/"
cp "$ROOT/stage2-artifacts/verification.txt" "$OUT/"
cp "$ROOT/stage2-artifacts/SOURCES.txt" "$OUT/"
cat >> "$OUT/SOURCES.txt" <<'EOF'

Stage 5: built-in ARM32 rootfs has a ttyGS0 getty and ConfigFS CDC-ACM script.
ADB binary present; USB ADB not configured.
Kernel SOUND=n; physical speaker silence/haptics NOT validated.
Google BMS/charger drivers absent; QUSB SCM patch is experimental.
Watch physically tested: NO
Hardware boot and flashing: FORBIDDEN
EOF
cat > "$OUT/README-DO-NOT-BOOT.txt" <<'EOF'
STAGE 5 OFFLINE RESEARCH ONLY. DO NOT BOOT OR FLASH.
The kernel lacks validated charging, battery gauge and power drivers.
The QUSB secure-monitor helper and USB device controller are unverified.
The USB identity values are Linux development examples, not assigned IDs.
Physical USB root login requires secure credentials before actual use.
No watch has been booted, modified or tested in this build.
EOF
(cd "$OUT" && sha256sum boot.img rootfs.cpio.gz kernel.config > SHA256SUMS)
echo "STAGE 5 offline image assembled. DO NOT BOOT OR FLASH."

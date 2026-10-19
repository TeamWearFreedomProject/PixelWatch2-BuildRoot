#!/usr/bin/env bash
set -euo pipefail
# OFFLINE ONLY: no hardware access, flashing, module loads or boot image.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KS="$ROOT/stage17-work/kernel"
KO="$ROOT/stage17-work/out"
IN="$ROOT/stage17-input"
OUT="$ROOT/stage17-artifacts"
mkdir -p "$OUT" "$KO"
(cd "$IN" && sha256sum -c SHA256SUMS)
PIN="$(awk '/^Kernel source: / {print $3; exit}' "$IN/SOURCES.txt")"
[[ "$PIN" =~ ^[0-9a-f]{40}$ ]] || { echo "Stage 7 kernel pin missing"; exit 1; }
git init -q "$KS"
git -C "$KS" remote add origin https://android.googlesource.com/kernel/msm
git -C "$KS" fetch -q --depth 1 origin "$PIN"
git -C "$KS" checkout -q --detach FETCH_HEAD
test "$(git -C "$KS" rev-parse HEAD)" = "$PIN"
# Stage 7's kernel.config embeds this existing initramfs at its
# original CI path. Restore precisely the SHA256-verified Stage 7 input
# for the scratch compilation; do not edit its contents.
mkdir -p "$ROOT/stage2-work/br-output/images"
cp "$IN/rootfs.cpio.gz" "$ROOT/stage2-work/br-output/images/rootfs.cpio.gz"
cmp "$IN/rootfs.cpio.gz" "$ROOT/stage2-work/br-output/images/rootfs.cpio.gz"
cp "$IN/kernel.config" "$KO/.config"
make -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
cp "$KO/.config" "$OUT/baseline-kernel.config"
grep -R -E '^[[:space:]]*config QCOM_SPMI_TEMP_ALARM$' "$KS/drivers/thermal" | tee "$OUT/kconfig-location.txt"
grep -R -F 'CONFIG_QCOM_SPMI_TEMP_ALARM' "$KS/drivers/thermal/Makefile" "$KS/drivers/thermal/qcom/Makefile" | tee "$OUT/kbuild-rule.txt"
grep -q 'qcom-spmi-temp-alarm.o' "$OUT/kbuild-rule.txt"
test -f "$KS/drivers/thermal/qcom/qcom-spmi-temp-alarm.c"
grep -Fxq '# CONFIG_QCOM_SPMI_TEMP_ALARM is not set' "$KO/.config"
"$KS/scripts/config" --file "$KO/.config" -e QCOM_SPMI_TEMP_ALARM
make -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
cp "$KO/.config" "$OUT/thermal-research.config"
grep -Fxq 'CONFIG_QCOM_SPMI_TEMP_ALARM=y' "$KO/.config"
for flag in 'CONFIG_ARM64=y' 'CONFIG_THERMAL=y' 'CONFIG_SPMI=y' 'CONFIG_REGMAP_SPMI=y' '# CONFIG_SOUND is not set' '# CONFIG_TRIM_UNUSED_KSYMS is not set'; do
  grep -Fxq "$flag" "$KO/.config" || { echo "Unexpected kernel config: $flag"; exit 1; }
done
# Kbuild single-object/directory goals are not reliable on this EOS tree.
# Reuse the Stage 6 proven complete ARM64 Image build path, with the two
# existing OFFLINE source compile patches, but never package an Android boot.
python3 "$ROOT/scripts/patch_bam_ndp.py" "$KS/drivers/soc/qcom/sps/bam.c" "$KO/.config"
python3 "$ROOT/scripts/patch_qusb_scm.py" "$KS"
make -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j2 Image
test -s "$KO/arch/arm64/boot/Image"
OBJ="$KO/drivers/thermal/qcom/qcom-spmi-temp-alarm.o"
test -s "$OBJ"
python3 "$ROOT/stage17/report_compile.py" --baseline "$OUT/baseline-kernel.config" --variant "$OUT/thermal-research.config" --object "$OBJ" --kernel-source "$KS" --kernel-image "$KO/arch/arm64/boot/Image" --output "$OUT/thermal-object-evidence.json"
echo "Stage 17: AArch64 thermal alarm object compiled offline; hardware NOT tested."

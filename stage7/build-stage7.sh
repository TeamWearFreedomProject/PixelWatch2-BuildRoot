#!/usr/bin/env bash
set -euo pipefail
# Stage 7 offline-only. NEVER boot, flash or load these research artifacts.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/stage2-work"
KS="$WORK/kernel"
KO="$WORK/kernel-out"
MODS="$ROOT/stage6-artifacts"
OUT="$ROOT/stage7-artifacts"
INPUT="$ROOT/stage6-input"
mkdir -p "$OUT"

# Build Stage 6's matching untrimmed kernel, Module.symvers and all seven .ko.
bash "$ROOT/stage6/build-power-modules.sh"
KREL="$(make -s -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- kernelrelease)"
[[ "$KREL" =~ ^[A-Za-z0-9._+-]+$ ]] || {
  echo "Invalid kernel release: $KREL"; exit 1;
}
test -s "$KO/Module.symvers"
test -s "$KO/arch/arm64/boot/Image"
(cd "$MODS" && sha256sum -c SHA256SUMS)
grep -Fxq 'CONFIG_MODVERSIONS=y' "$KO/.config"
grep -Fxq '# CONFIG_TRIM_UNUSED_KSYMS is not set' "$KO/.config"
grep -Fxq '# CONFIG_SOUND is not set' "$KO/.config"

for ko in "$MODS"/*.ko; do
  test -f "$ko"
  vermagic="$(modinfo -F vermagic "$ko")"
  if [[ "$vermagic" != "$KREL "* ]]; then
    echo "Module vermagic mismatch: $ko => $vermagic, expected $KREL"
    exit 1
  fi
done
python3 "$ROOT/stage7/validate_abi.py" \
  --kernel "$KO/Module.symvers" \
  --group "$WORK/google-modules/bms/misc/Module.symvers" \
  --group "$KS/drivers/power/supply/qcom/Module.symvers" \
  --group "$WORK/google-modules/bms/Module.symvers" \
  --module-dir "$MODS" \
  --output "$OUT/abi-report.json"

# Generate module dependency metadata without loading anything.
FAKEROOT="$ROOT/stage7-depmod-sysroot"
DEPMOD_DIR="$FAKEROOT/lib/modules/$KREL"
mkdir -p "$DEPMOD_DIR/extra"
cp "$MODS"/*.ko "$DEPMOD_DIR/extra/"
depmod -b "$FAKEROOT" "$KREL"
test -f "$DEPMOD_DIR/modules.dep"

OLD_CONFIG="$(sha256sum "$KO/.config" | cut -d' ' -f1)"
OLD_SYMVERS="$(sha256sum "$KO/Module.symvers" | cut -d' ' -f1)"
OLD_IMAGE="$(sha256sum "$KO/arch/arm64/boot/Image" | cut -d' ' -f1)"

python3 "$ROOT/stage7/pack_modules.py" \
  --input "$INPUT/rootfs.cpio.gz" \
  --output "$OUT/rootfs.cpio.gz" \
  --modules "$MODS" \
  --metadata "$DEPMOD_DIR" \
  --kernel-release "$KREL" \
  --report "$OUT/integration-report.json"

# Rebuild the ARM64 Image so the packed modules live inside built-in initramfs.
cp "$OUT/rootfs.cpio.gz" "$WORK/br-output/images/rootfs.cpio.gz"
bash "$ROOT/scripts/stage2-build.sh"
cmp "$OUT/rootfs.cpio.gz" "$ROOT/stage2-artifacts/rootfs.cpio.gz"
NEW_CONFIG="$(sha256sum "$KO/.config" | cut -d' ' -f1)"
NEW_SYMVERS="$(sha256sum "$KO/Module.symvers" | cut -d' ' -f1)"
NEW_IMAGE="$(sha256sum "$KO/arch/arm64/boot/Image" | cut -d' ' -f1)"
[[ "$OLD_CONFIG" == "$NEW_CONFIG" ]] || {
  echo 'Kernel configuration changed after compiling modules'; exit 1;
}
[[ "$OLD_SYMVERS" == "$NEW_SYMVERS" ]] || {
  echo 'Exported module symbol CRCs changed after packaging'; exit 1;
}
[[ "$OLD_IMAGE" != "$NEW_IMAGE" ]] || {
  echo 'Kernel Image unchanged, cannot confirm initramfs embed'; exit 1;
}
grep -Fxq '# CONFIG_TRIM_UNUSED_KSYMS is not set' "$KO/.config"
grep -Fxq '# CONFIG_SOUND is not set' "$KO/.config"

cp "$ROOT/stage2-artifacts/boot.img" "$OUT/boot.img"
cp "$ROOT/stage2-artifacts/kernel.config" "$OUT/kernel.config"
cp "$ROOT/stage2-artifacts/verification.txt" "$OUT/verification.txt"
cp "$KO/Module.symvers" "$OUT/Module.symvers"
cp "$MODS/PROVENANCE.txt" "$OUT/POWER-SOURCE-PINS.txt"
cat > "$OUT/README-FIRST-DO-NOT-BOOT.txt" <<'EOF'
STAGE 7 RESEARCH BOOT IMAGE. DO NOT BOOT, FLASH OR LOAD MODULES.
ARM64 kernel + 7 Google BMS/Qualcomm .ko share a single Stage 6 ABI.
Modules are stored in ARM32 initramfs, but NOT autoloaded.
Power/charger/thermal/device-tree/firmware/USB behavior is NOT verified.
The QUSB SCM helper is experimental. Watch hardware was NEVER tested.
No proof of safe battery management, sound silence or boot compatibility.
Never use fastboot boot, flash, erase, sideload or modprobe with these files.
EOF
cat > "$OUT/SOURCES.txt" <<EOF
Stage 7 ABI-coherent offline research bundle
Stage 5 rootfs input: GitHub run 38564131552
Kernel source: $(git -C "$KS" rev-parse HEAD)
Kernel release: $KREL
CONFIG_MODVERSIONS=y; CONFIG_TRIM_UNUSED_KSYMS=n; CONFIG_SOUND=n
Power modules: rebuilt with matching kernel by Stage 6 in same CI job
Power module autoload: NO
Physical watch tested: NO
Flashable: NO
Hardware boot safe: NOT VERIFIED
EOF
(cd "$OUT" && sha256sum boot.img rootfs.cpio.gz kernel.config Module.symvers > SHA256SUMS)
echo 'Stage 7 compiled offline only; NO hardware test or flash.'

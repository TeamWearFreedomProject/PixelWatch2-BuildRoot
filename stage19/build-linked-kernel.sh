#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KS="$ROOT/stage19-work/kernel"
KO="$ROOT/stage19-work/out"
IN="$ROOT/stage19-input/stage7"
OUT="$ROOT/stage19-artifacts"
mkdir -p "$OUT" "$KO"
(cd "$IN" && sha256sum -c SHA256SUMS)
PIN="$(awk '/^Kernel source: / {print $3; exit}' "$IN/SOURCES.txt")"
[[ "$PIN" =~ ^[0-9a-f]{40}$ ]] || { echo 'Missing kernel source pin'; exit 1; }
python3 - "$ROOT" "$PIN" <<'PY'
import json, sys
from pathlib import Path
root, pin = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(root))
from stage18.report_contract import verify_stage17
pins=json.loads((root/'stage18/pins.json').read_text())
assert pins['kernel_revision']==pin
verify_stage17(root/'stage19-input/stage17/stage17-artifacts', pins)
PY
git init -q "$KS"
git -C "$KS" remote add origin https://android.googlesource.com/kernel/msm
git -C "$KS" fetch -q --depth 1 origin "$PIN"
git -C "$KS" checkout -q --detach FETCH_HEAD
test "$(git -C "$KS" rev-parse HEAD)" = "$PIN"
python3 - "$ROOT" "$KS" <<'PY'
import hashlib, json, sys
from pathlib import Path
root, source = map(Path, sys.argv[1:])
for path, expected in json.loads((root/'stage18/pins.json').read_text())['files'].items():
    assert hashlib.sha256((source/path).read_bytes()).hexdigest()==expected, path
PY
git -C "$KS" apply --check "$ROOT/stage19/0001-thermal-reach-spmi-alarm.patch"
git -C "$KS" apply "$ROOT/stage19/0001-thermal-reach-spmi-alarm.patch"
git -C "$KS" diff -- drivers/thermal/Makefile > "$OUT/thermal-parent.patch"
python3 "$ROOT/stage19/check_routing.py" --kernel-source "$KS" --output "$OUT/kbuild-matrix.json"

# Restore the immutable Stage 7 initramfs where its pinned config expects it.
mkdir -p "$ROOT/stage2-work/br-output/images"
cp "$IN/rootfs.cpio.gz" "$ROOT/stage2-work/br-output/images/rootfs.cpio.gz"
cmp "$IN/rootfs.cpio.gz" "$ROOT/stage2-work/br-output/images/rootfs.cpio.gz"
cp "$IN/kernel.config" "$KO/.config"
grep -Fxq "CONFIG_INITRAMFS_SOURCE=\"$ROOT/stage2-work/br-output/images/rootfs.cpio.gz\"" "$KO/.config"
COMMON=(-C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-)
make "${COMMON[@]}" olddefconfig
cp "$KO/.config" "$OUT/control-off.config"
grep -Fxq '# CONFIG_QCOM_SPMI_TEMP_ALARM is not set' "$KO/.config"
grep -Fxq '# CONFIG_QCOM_TSENS is not set' "$KO/.config"
"$KS/scripts/config" --file "$KO/.config" -e QCOM_SPMI_TEMP_ALARM
make "${COMMON[@]}" olddefconfig
cp "$KO/.config" "$OUT/linked-on.config"
grep -Fxq 'CONFIG_QCOM_SPMI_TEMP_ALARM=y' "$KO/.config"

# Keep the two compatibility changes already used by Stage 17 explicit.
python3 "$ROOT/scripts/patch_bam_ndp.py" "$KS/drivers/soc/qcom/sps/bam.c" "$KO/.config"
python3 "$ROOT/scripts/patch_qusb_scm.py" "$KS"
git -C "$KS" diff > "$OUT/all-research-source-changes.patch"
export KBUILD_BUILD_TIMESTAMP="$(git -C "$KS" show -s --format=%cD HEAD)"
export KBUILD_BUILD_USER=aurora-ci KBUILD_BUILD_HOST=stage19 KBUILD_BUILD_VERSION=19
BUILD_JOBS="${AURORA_BUILD_JOBS:-2}"
[[ "$BUILD_JOBS" =~ ^[1-4]$ ]] || { echo 'Build jobs must be 1..4'; exit 1; }
echo '=== STAGE19 ON: compile and link final kernel ==='
make "${COMMON[@]}" -j"$BUILD_JOBS" Image
python3 "$ROOT/stage19/verify_link.py" --out "$KO" --mode on --output "$OUT/link-on.json"

# Reuse the output directory deliberately: the OFF link must remove the
# driver even though a previously compiled .o may still exist on disk.
echo '=== STAGE19 OFF: remove only alarm config and relink negative control ==='
cp "$OUT/control-off.config" "$KO/.config"
make "${COMMON[@]}" olddefconfig
cmp "$OUT/control-off.config" "$KO/.config"
make "${COMMON[@]}" -j"$BUILD_JOBS" Image
python3 "$ROOT/stage19/verify_link.py" --out "$KO" --mode off --output "$OUT/link-off.json"
python3 "$ROOT/stage19/verify_link.py" --summary-dir "$OUT" --output "$OUT/thermal-link-evidence.json"
printf 'Kernel source: %s\nStage 7 input run: 38721433935\nStage 17 reference run: 39196338067\n' "$PIN" > "$OUT/SOURCES.txt"
(cd "$OUT" && sha256sum ./*.json ./*.config ./*.patch SOURCES.txt > SHA256SUMS)
echo 'STAGE19_COMPLETE: final-kernel alarm linkage and OFF control passed; runtime not tested.'

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KS="$ROOT/stage22-work/kernel"
KO="$ROOT/stage22-work/out"
OUT="$ROOT/stage22-artifacts"
PIN="$(python3 -c 'import json; print(json.load(open("stage22/pins.json"))["kernel_revision"])')"
mkdir -p "$KO" "$OUT"
python3 - "$ROOT" <<'PY'
import hashlib,json,sys
from pathlib import Path
r=Path(sys.argv[1]);p=json.loads((r/'stage22/pins.json').read_text())
for name,digest in p['stage20_files'].items():
 assert hashlib.sha256((r/'stage22-input/stage20'/name).read_bytes()).hexdigest()==digest,name
PY
git init -q "$KS"
git -C "$KS" remote add origin https://android.googlesource.com/kernel/msm
FETCHED=0
for attempt in 1 2 3 4 5; do
  if timeout 180 git -C "$KS" -c http.lowSpeedLimit=1024 -c http.lowSpeedTime=60 fetch -q --depth 1 origin "$PIN"; then
    FETCHED=1
    break
  fi
  sleep "$((attempt * 3))"
done
test "$FETCHED" = 1
git -C "$KS" checkout -q --detach FETCH_HEAD
test "$(git -C "$KS" rev-parse HEAD)" = "$PIN"
python3 - "$ROOT" "$KS" <<'PY'
import hashlib,json,sys
from pathlib import Path
r,k=map(Path,sys.argv[1:]);p=json.loads((r/'stage22/pins.json').read_text())
for name,digest in json.loads((r/'stage18/pins.json').read_text())['files'].items():
 assert hashlib.sha256((k/name).read_bytes()).hexdigest()==digest,name
for key,name in [('original','drivers/interconnect/qcom/monaco.c'),('core','drivers/interconnect/core.c')]:
 assert hashlib.sha256((k/name).read_bytes()).hexdigest()==p['sources'][key],name
PY
cp "$KS/drivers/interconnect/qcom/monaco.c" "$ROOT/stage22-work/monaco-original.c"
git -C "$KS" apply --check "$ROOT/stage19/0001-thermal-reach-spmi-alarm.patch"
git -C "$KS" apply "$ROOT/stage19/0001-thermal-reach-spmi-alarm.patch"
git -C "$KS" apply --check "$ROOT/stage22/0001-monaco-unwind-provider-on-probe-error.patch"
git -C "$KS" apply "$ROOT/stage22/0001-monaco-unwind-provider-on-probe-error.patch"
python3 "$ROOT/stage20/integrate_usb_shim.py" --kernel-source "$KS" --pins "$ROOT/stage20/pins.json" --output "$OUT/usb-shim-source.json"
cp "$ROOT/stage22-input/stage20/kernel.config" "$KO/.config"
cp "$ROOT/stage22-input/stage20/rootfs.cpio.gz" "$OUT/rootfs.cpio.gz"
mkdir -p "$ROOT/stage2-work/br-output/images"
cp "$OUT/rootfs.cpio.gz" "$ROOT/stage2-work/br-output/images/rootfs.cpio.gz"
grep -Fxq "CONFIG_INITRAMFS_SOURCE=\"$ROOT/stage2-work/br-output/images/rootfs.cpio.gz\"" "$KO/.config"
make -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
for sym in ARM64 COMPAT COMPAT_BINFMT_ELF INITRAMFS_FORCE DEVTMPFS USB_CONFIGFS_ACM USB_DWC3_MSM EXTCON_GOOGLE_USB_SHIM QCOM_SPMI_TEMP_ALARM KASAN KASAN_GENERIC; do
  grep -Fxq "CONFIG_$sym=y" "$KO/.config" || { echo "Required option missing: $sym"; exit 1; }
done
grep -Fxq '# CONFIG_SOUND is not set' "$KO/.config"
python3 - "$ROOT" <<'PY'
import hashlib,json,sys
from pathlib import Path
r=Path(sys.argv[1]);a=r/'stage22-input/stage20/kernel.config';b=r/'stage22-work/out/.config'
def options(path):
 return {s for s in path.read_text().splitlines() if s.startswith('CONFIG_') or s.startswith('# CONFIG_')}
assert options(a)==options(b),'Unexpected config change'
report={'stage':22,'same_config_options_as_stage20':True,'kasan_retained':True,
        'stage20_config_sha256':hashlib.sha256(a.read_bytes()).hexdigest(),
        'stage22_config_sha256':hashlib.sha256(b.read_bytes()).hexdigest()}
(r/'stage22-artifacts/config-preservation.json').write_text(json.dumps(report,indent=2)+'\n')
PY
python3 "$ROOT/scripts/patch_bam_ndp.py" "$KS/drivers/soc/qcom/sps/bam.c" "$KO/.config"
python3 "$ROOT/scripts/patch_qusb_scm.py" "$KS"
python3 "$ROOT/stage22/run_probe_tests.py" --original "$ROOT/stage22-work/monaco-original.c" \
  --patched "$KS/drivers/interconnect/qcom/monaco.c" --core "$KS/drivers/interconnect/core.c" \
  --output "$OUT/probe-tests.json"
git -C "$KS" diff > "$OUT/source-changes.patch"
cp "$KO/.config" "$OUT/kernel.config"
printf 'Kernel: %s\nUnchanged userspace: Stage 20 run 39363419356\nKernel build version: 22\n' "$PIN" > "$OUT/SOURCES.txt"
echo STAGE22_KERNEL_PREPARED_AND_PROBE_TESTED

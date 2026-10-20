#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KS="$ROOT/stage20-work/kernel"
KO="$ROOT/stage20-work/out"
OUT="$ROOT/stage20-artifacts"
PIN="$(python3 -c 'import json; print(json.load(open("stage18/pins.json"))["kernel_revision"])')"
mkdir -p "$KO" "$OUT"
python3 - "$ROOT" <<'PY'
import hashlib,json,sys
from pathlib import Path
r=Path(sys.argv[1]);pins=json.loads((r/'stage20/pins.json').read_text())
for label,files in pins['files'].items():
 for name,digest in files.items():
  assert hashlib.sha256((r/'stage20-input'/label/name).read_bytes()).hexdigest()==digest, (label,name)
e=json.loads((r/'stage20-input/stage19/stage19-artifacts/thermal-link-evidence.json').read_text())
assert e['positive_link_proof'] and e['negative_control_pass']
PY
git init -q "$KS"
git -C "$KS" remote add origin https://android.googlesource.com/kernel/msm
FETCHED=0
for attempt in 1 2 3 4 5; do
  if timeout 180 git -C "$KS" -c http.lowSpeedLimit=1024 -c http.lowSpeedTime=60 fetch -q --depth 1 origin "$PIN"; then
    FETCHED=1
    break
  fi
  echo "Source fetch retry $attempt/5"
  sleep "$((attempt * 3))"
done
test "$FETCHED" = 1
git -C "$KS" checkout -q --detach FETCH_HEAD
test "$(git -C "$KS" rev-parse HEAD)" = "$PIN"
python3 - "$ROOT" "$KS" <<'PY'
import hashlib,json,sys
from pathlib import Path
r,k=map(Path,sys.argv[1:])
for p,d in json.loads((r/'stage18/pins.json').read_text())['files'].items():
 assert hashlib.sha256((k/p).read_bytes()).hexdigest()==d,p
PY
git -C "$KS" apply --check "$ROOT/stage19/0001-thermal-reach-spmi-alarm.patch"
git -C "$KS" apply "$ROOT/stage19/0001-thermal-reach-spmi-alarm.patch"
mkdir -p "$ROOT/stage2-work/br-output/images"
cp "$OUT/rootfs.cpio.gz" "$ROOT/stage2-work/br-output/images/rootfs.cpio.gz"
cp "$ROOT/stage20-input/stage19/stage19-artifacts/linked-on.config" "$KO/.config"
grep -Fxq "CONFIG_INITRAMFS_SOURCE=\"$ROOT/stage2-work/br-output/images/rootfs.cpio.gz\"" "$KO/.config"
python3 "$ROOT/stage20/integrate_usb_shim.py" --kernel-source "$KS" --pins "$ROOT/stage20/pins.json" --output "$OUT/usb-shim-source.json"
"$KS/scripts/config" --file "$KO/.config" -e EXTCON_GOOGLE_USB_SHIM
make -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
for sym in ARM64 COMPAT COMPAT_BINFMT_ELF BLK_DEV_INITRD INITRAMFS_FORCE DEVTMPFS USB_GADGET USB_DWC3 USB_DWC3_MSM USB_CONFIGFS USB_CONFIGFS_ACM USB_F_ACM QCOM_SPMI_TEMP_ALARM EXTCON EXTCON_GOOGLE_USB_SHIM QCOM_EUD POWER_RESET_MSM; do
  grep -Fxq "CONFIG_$sym=y" "$KO/.config" || { echo "Required option missing: $sym"; exit 1; }
done
grep -Fxq '# CONFIG_SOUND is not set' "$KO/.config"
python3 "$ROOT/scripts/patch_bam_ndp.py" "$KS/drivers/soc/qcom/sps/bam.c" "$KO/.config"
python3 "$ROOT/scripts/patch_qusb_scm.py" "$KS"
git -C "$KS" diff > "$OUT/source-changes.patch"
cp "$KO/.config" "$OUT/kernel.config"
printf 'Kernel source: %s\nStage 7 input: 38721433935\nStage 19 link reference: 39348516565\nBuildroot userspace: 2025.02.1, ARM32 musl\n' "$PIN" > "$OUT/SOURCES.txt"
echo STAGE20_KERNEL_PREPARED

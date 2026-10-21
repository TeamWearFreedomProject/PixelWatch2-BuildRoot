#!/bin/bash
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
cd "$PROJECT"
WORK="$PROJECT/stage26-work"
OUT="$PROJECT/stage26-artifacts"
mkdir -p "$WORK/diagnostic" "$OUT"
python3 stage24/fetch.py --phase adaptation --work "$WORK"
python3 - <<'PY'
import hashlib,json,pathlib,urllib.request
pins=json.loads(pathlib.Path('stage25/pins.json').read_text());p=pathlib.Path('stage26-work/stage24.zip')
if not p.exists():
    with urllib.request.urlopen(pins['artifact_url'],timeout=120) as src,p.open('wb') as dst:
        while chunk:=src.read(1024*1024):dst.write(chunk)
if hashlib.sha256(p.read_bytes()).hexdigest()!=pins['artifact_sha256']:raise SystemExit('Stage24 artifact SHA256 mismatch')
PY
aarch64-linux-gnu-gcc -Os -static -fno-ident -Wl,--build-id=none -Wall -Wextra -Werror stage26/pid1.c -o "$WORK/diagnostic/pid1"
qemu-aarch64 "$WORK/diagnostic/pid1" --check
python3 stage26/prepare.py "$WORK/stage24.zip" "$WORK/diagnostic/pid1" "$WORK/diagnostic"
python3 stage26/hook.py "$WORK/port/build"
export AURORA_STAGE26_PROJECT="$PROJECT"
export AURORA_STAGE26_INITRAMFS="$WORK/diagnostic/diagnostic.cpio"
(cd "$WORK/port" && bash build/build.sh -k)
python3 stage26/assemble.py "$WORK" "$OUT"
python3 stage26/qemu_check.py "$OUT" "$WORK/qemu"
cp docs/STAGE26.md "$OUT/README-STAGE26.md"
python3 stage26/make_capture.py "$OUT"
(cd "$OUT" && sha256sum boot-stage26-usb.img *.json *.md kernel.config qemu-boot.log > SHA256SUMS && sha256sum -c SHA256SUMS)

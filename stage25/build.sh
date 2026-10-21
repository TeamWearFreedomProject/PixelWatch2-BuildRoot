#!/bin/bash
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
cd "$PROJECT"
mkdir -p stage25-work/input stage25-artifacts
python3 - <<'PY'
import hashlib,json,pathlib,urllib.request,zipfile
pins=json.loads(pathlib.Path('stage25/pins.json').read_text())
zip_path=pathlib.Path('stage25-work/stage24.zip')
if not zip_path.exists():
    with urllib.request.urlopen(pins['artifact_url'],timeout=120) as src, zip_path.open('wb') as dst:
        while chunk:=src.read(1024*1024): dst.write(chunk)
if hashlib.sha256(zip_path.read_bytes()).hexdigest()!=pins['artifact_sha256']:
    raise SystemExit('Stage24 artifact ZIP SHA256 mismatch')
with zipfile.ZipFile(zip_path) as z:
    if z.testzip(): raise SystemExit('Artifact ZIP CRC failure')
    for name in ('boot.img','init_boot.img'):
        pathlib.Path('stage25-work/input',name).write_bytes(z.read(name))
PY
aarch64-linux-gnu-gcc -Os -static -fno-ident -Wl,--build-id=none -Wall -Wextra -Werror stage25/return_bootloader.c -o stage25-work/aurora-return
qemu-aarch64 stage25-work/aurora-return --check
python3 stage25/package.py stage25-work/input stage25-work/aurora-return stage25-artifacts
qemu-aarch64 stage25-artifacts/busybox-for-check --list > stage25-work/applets.txt
for a in sh getty mount sleep cat ln; do grep -Fxq "$a" stage25-work/applets.txt; done
rm stage25-artifacts/busybox-for-check
cp docs/STAGE25.md stage25-artifacts/README-STAGE25.md
python3 stage25/make_capture.py stage25-artifacts
(cd stage25-artifacts && sha256sum boot-stage25-usb.img audit.json sources.json README-STAGE25.md WINDOWS-CAPTURE.md > SHA256SUMS && sha256sum -c SHA256SUMS)

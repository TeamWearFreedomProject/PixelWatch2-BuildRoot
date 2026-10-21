#!/bin/bash
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
cd "$PROJECT"
WORK="$PROJECT/stage26-work"
mkdir -p "$WORK/diagnostic"
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
(cd "$WORK/diagnostic" && sha256sum diagnostic.cpio diagnostic.cpio.gz baseline.config initramfs.json > SHA256SUMS)

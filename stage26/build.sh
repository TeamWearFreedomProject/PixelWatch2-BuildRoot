#!/bin/bash
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
cd "$PROJECT"
WORK="$PROJECT/stage26-work"
OUT="$PROJECT/stage26-artifacts"
mkdir -p "$WORK/diagnostic" "$OUT"
python3 stage24/fetch.py --phase adaptation --work "$WORK"
(cd "$WORK/diagnostic" && sha256sum -c SHA256SUMS)
python3 stage26/hook.py "$WORK/port/build"
export AURORA_STAGE26_PROJECT="$PROJECT"
export AURORA_STAGE26_BASELINE="$WORK/diagnostic/baseline.config"
export AURORA_STAGE26_INITRAMFS="$WORK/diagnostic/diagnostic.cpio"
(cd "$WORK/port" && bash build/build.sh -k)
python3 stage26/assemble.py "$WORK" "$OUT"
(cd "$OUT" && sha256sum boot-stage26-usb.img *.json kernel.config > SHA256SUMS)

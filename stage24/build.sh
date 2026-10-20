#!/bin/bash
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(realpath "${1:-stage24-work}")
OUT=$(realpath -m "${2:-stage24-artifacts/adaptation}")
mkdir -p "$OUT"
cd "$WORK/port"
bash build/build.sh
test -s out/device_eos.tar.xz
cp out/device_eos.tar.xz "$OUT/"
cp workdir/tmp/partitions/boot.img workdir/tmp/partitions/init_boot.img "$OUT/"
cp workdir/downloads/KERNEL_OBJ/.config "$OUT/kernel.config"
cp "$WORK/sources.json" "$OUT/sources.json"
python3 "$PROJECT/stage24/audit.py" boot "$OUT" --output "$OUT/audit.json"
(cd "$OUT" && sha256sum boot.img init_boot.img device_eos.tar.xz kernel.config sources.json audit.json > SHA256SUMS)

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BR="$ROOT/stage2-work/buildroot"
OUTPUT="$ROOT/stage2-work/br-output"
mkdir -p "$ROOT/stage2-work"

if [[ ! -s "$OUTPUT/images/rootfs.tar" || ! -s "$OUTPUT/images/rootfs.cpio.gz" ]]; then
  if [[ ! -e "$BR/Makefile" ]]; then
    git clone --depth 1 --branch 2025.02.1 \
      https://github.com/buildroot/buildroot.git "$BR"
  fi
  make -C "$BR" BR2_EXTERNAL="$ROOT" O="$OUTPUT" aurora_arm32_adbd_defconfig
  grep -Fxq 'BR2_PACKAGE_ANDROID_TOOLS_ADBD=y' "$OUTPUT/.config"
  make -C "$BR" O="$OUTPUT" -j2
else
  echo 'Reusing cached adbd-specific ARM32 rootfs archive.'
fi

test -s "$OUTPUT/images/rootfs.tar"
test -s "$OUTPUT/images/rootfs.cpio.gz"
mkdir -p "$ROOT/stage4-rootfs-inspect"
tar -xf "$OUTPUT/images/rootfs.tar" -C "$ROOT/stage4-rootfs-inspect"
test -x "$ROOT/stage4-rootfs-inspect/usr/bin/adbd" || {
  echo 'STOP: /usr/bin/adbd missing'; exit 1;
}
file "$ROOT/stage4-rootfs-inspect/usr/bin/adbd" \
  | tee "$ROOT/stage4-rootfs-verification.txt"
grep -E 'ELF 32-bit.*ARM' "$ROOT/stage4-rootfs-verification.txt"
file "$ROOT/stage4-rootfs-inspect/bin/busybox" \
  | tee -a "$ROOT/stage4-rootfs-verification.txt"
grep -E 'BusyBox|ELF 32-bit.*ARM' "$ROOT/stage4-rootfs-verification.txt" >/dev/null
test -x "$ROOT/stage4-rootfs-inspect/init"
echo 'ARM32 adbd present. This does not establish functioning USB/ADB.'

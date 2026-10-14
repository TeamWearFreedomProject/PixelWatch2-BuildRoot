#!/bin/sh
# Buildroot target post-build: append one physical-USB login console.
# All modifications happen inside the disposable CI rootfs.
set -eu
TARGET="$1"
test -f "$TARGET/etc/inittab"
test -x "$TARGET/usr/sbin/aurora-acm"
test -x "$TARGET/etc/init.d/S90aurora-acm"
if grep -q 'ttyGS0::' "$TARGET/etc/inittab"; then
    echo 'Duplicate ttyGS0 getty, refusing to continue' >&2
    exit 1
fi
printf '%s\n' \
    '# Stage 5 research: local CDC ACM physical USB login' \
    'ttyGS0::respawn:/sbin/getty -L 115200 ttyGS0 vt100' \
    >> "$TARGET/etc/inittab"

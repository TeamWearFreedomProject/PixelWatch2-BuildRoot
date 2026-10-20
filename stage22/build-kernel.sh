#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KS="$ROOT/stage22-work/kernel"
KO="$ROOT/stage22-work/out"
export KBUILD_BUILD_TIMESTAMP="$(git -C "$KS" show -s --format=%cD HEAD)"
export KBUILD_BUILD_USER=aurora-ci KBUILD_BUILD_HOST=stage22 KBUILD_BUILD_VERSION=22
make -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j4 Image
test -s "$KO/vmlinux"
test -s "$KO/arch/arm64/boot/Image"
echo STAGE22_KERNEL_COMPILED

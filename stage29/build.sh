#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
stage29_work="$PWD/stage28-work"
source "$stage29_work/sdk/environment-setup-armv7vehf-neon-oe-linux-gnueabi"

# This pinned SDK's GCC searches for unprefixed as/ld, while the ARM tools are
# installed with triplet prefixes. Select those exact tools, never the host as.
stage29_tools="$stage29_work/driver-tools"
mkdir -p "$stage29_tools"
ln -sfn "$OECORE_NATIVE_SYSROOT/usr/bin/arm-oe-linux-gnueabi/arm-oe-linux-gnueabi-as" "$stage29_tools/as"
ln -sfn "$OECORE_NATIVE_SYSROOT/usr/bin/arm-oe-linux-gnueabi/arm-oe-linux-gnueabi-ld" "$stage29_tools/ld"
export CC="$CC -B$stage29_tools/"
export CXX="$CXX -B$stage29_tools/"
export CFLAGS="$CFLAGS -ffile-prefix-map=$PWD=/usr/src/aurora-ui"
export CXXFLAGS="$CXXFLAGS -ffile-prefix-map=$PWD=/usr/src/aurora-ui"
${CXX} -print-prog-name=as
"$stage29_tools/as" --version
cmake --fresh -S stage29/native -B "$stage29_work/arm32-home" \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build "$stage29_work/arm32-home" --parallel 2
${READELF} -h "$stage29_work/arm32-home/aurora-home"

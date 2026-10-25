#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
stage30_work="$PWD/stage28-work"
source "$stage30_work/sdk/environment-setup-armv7vehf-neon-oe-linux-gnueabi"

# This pinned SDK's GCC searches for unprefixed as/ld, while the ARM tools are
# installed with triplet prefixes. Select those exact tools, never the host as.
stage30_tools="$stage30_work/driver-tools"
mkdir -p "$stage30_tools"
ln -sfn "$OECORE_NATIVE_SYSROOT/usr/bin/arm-oe-linux-gnueabi/arm-oe-linux-gnueabi-as" "$stage30_tools/as"
ln -sfn "$OECORE_NATIVE_SYSROOT/usr/bin/arm-oe-linux-gnueabi/arm-oe-linux-gnueabi-ld" "$stage30_tools/ld"
export CC="$CC -B$stage30_tools/"
export CXX="$CXX -B$stage30_tools/"
export CFLAGS="$CFLAGS -ffile-prefix-map=$PWD=/usr/src/aurora-ui"
export CXXFLAGS="$CXXFLAGS -ffile-prefix-map=$PWD=/usr/src/aurora-ui"
${CXX} -print-prog-name=as
"$stage30_tools/as" --version
cmake --fresh -S stage30/native -B "$stage30_work/arm32-shell" \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build "$stage30_work/arm32-shell" --parallel 2
${READELF} -h "$stage30_work/arm32-shell/aurora-preview"

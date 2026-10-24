#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
stage28_work="$PWD/stage28-work"
source "$stage28_work/sdk/environment-setup-armv7vehf-neon-oe-linux-gnueabi"

# This pinned SDK's GCC searches for unprefixed as/ld, while the ARM tools are
# installed with triplet prefixes. Select those exact tools, never the host as.
stage28_tools="$stage28_work/driver-tools"
mkdir -p "$stage28_tools"
ln -sfn "$OECORE_NATIVE_SYSROOT/usr/bin/arm-oe-linux-gnueabi/arm-oe-linux-gnueabi-as" "$stage28_tools/as"
ln -sfn "$OECORE_NATIVE_SYSROOT/usr/bin/arm-oe-linux-gnueabi/arm-oe-linux-gnueabi-ld" "$stage28_tools/ld"
export CC="$CC -B$stage28_tools/"
export CXX="$CXX -B$stage28_tools/"
export CFLAGS="$CFLAGS -ffile-prefix-map=$PWD=/usr/src/aurora-ui"
export CXXFLAGS="$CXXFLAGS -ffile-prefix-map=$PWD=/usr/src/aurora-ui"
${CXX} -print-prog-name=as
"$stage28_tools/as" --version
cmake --fresh -S stage28/native -B "$stage28_work/arm32" \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build "$stage28_work/arm32" --parallel 2
${READELF} -h "$stage28_work/arm32/aurora-preview"

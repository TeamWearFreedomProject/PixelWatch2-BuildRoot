#!/usr/bin/env bash
set -euo pipefail
# Stage 6 OFFLINE CI ONLY. Never load modules, boot or flash the watch.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/stage2-work"
KS="$WORK/kernel"
KO="$WORK/kernel-out"
IN="$ROOT/stage6-input"
OUT="$ROOT/stage6-artifacts"
BMS="$WORK/google-modules/bms"
SOC="$WORK/google-modules/soc/msm"
mkdir -p "$OUT" "$WORK/br-output/images" "$WORK/google-modules/soc"

(cd "$IN" && sha256sum -c SHA256SUMS)
test -s "$IN/kernel.config"
test -s "$IN/rootfs.cpio.gz"
test -s "$IN/SOURCES.txt"
PIN="$(awk '/^Kernel commit:/{print $3; exit}' "$IN/SOURCES.txt")"
[[ "$PIN" =~ ^[0-9a-f]{40}$ ]] || { echo "Missing Stage 5 kernel revision"; exit 1; }
test "$(git -C "$KS" rev-parse HEAD)" = "$PIN" || {
    echo "Kernel source mismatch: cannot produce matching module ABI"; exit 1;
}
cp "$IN/kernel.config" "$KO/.config"
cp "$IN/rootfs.cpio.gz" "$WORK/br-output/images/rootfs.cpio.gz"
make -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
for k in ARM64 MODULES MODVERSIONS COMPAT; do
    grep -Fxq "CONFIG_$k=y" "$KO/.config" || {
        echo "Missing expected kernel option CONFIG_$k"; exit 1;
    }
done
grep -Fxq '# CONFIG_SOUND is not set' "$KO/.config"
echo "=== Build kernel and module symbol versions with identical Stage 5 rootfs/config ==="
make -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j2 Image
# Building Image/vmlinux alone may only emit vmlinux.symvers, which contains
# symbols exported by vmlinux but is NOT the final kernel Module.symvers.
# With CONFIG_MODVERSIONS=y, kernel 5.15 requires the full 'modules' target
# to run modpost and generate Module.symvers for external module ABI checks.
test -s "$KO/vmlinux.symvers" || {
    echo 'Missing vmlinux.symvers after Image; inspect the kernel build'; exit 1;
}
make -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j2 modules
test -s "$KO/Module.symvers" || {
    echo 'Missing final Module.symvers after make modules'; exit 1;
}
echo "Kernel exported symbols: $(wc -l < "$KO/Module.symvers")"
make -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- modules_prepare

echo '=== Fetch Google BMS/gvotable and companion SOC modules ==='
mkdir -p "$BMS" "$SOC"
git -C "$BMS" init
git -C "$BMS" remote add origin https://android.googlesource.com/kernel/google-modules/bms
git -C "$BMS" fetch --depth 1 origin 51583026f264e7597808a16aa6809fb9279eb8c4
git -C "$BMS" checkout --detach FETCH_HEAD
git -C "$SOC" init
git -C "$SOC" remote add origin https://android.googlesource.com/kernel/google-modules/soc/msm
git -C "$SOC" fetch --depth 1 origin 7a2cd1649e49373ca24bd81d4fe89e7440db4ab5
git -C "$SOC" checkout --detach FETCH_HEAD
test -f "$SOC/Makefile.include" || {
    echo "Google SOC MSM Makefile.include missing"; exit 1;
}
EXTRA=""
build_group() {
    label="$1"
    path="$2"
    shift 2
    echo "=== External module build: $label ==="
    make -C "$KS" O="$KO" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
        -j2 M="$path" KERNEL_SRC="$KS" OUT_DIR="$KS" \
        KBUILD_EXTRA_SYMBOLS="$EXTRA" "$@" modules
    test -s "$path/Module.symvers" || {
        echo "Missing Module.symvers from $label"; exit 1;
    }
    find "$path" -name '*.ko' -type f -print | tee "$OUT/$label-built.txt"
    test -s "$OUT/$label-built.txt" || {
        echo "No kernel module generated for $label"; exit 1;
    }
    EXTRA="$EXTRA $path/Module.symvers"
}
build_group gvotable "$BMS/misc" \
    CONFIG_GOOGLE_VOTABLE=m CONFIG_GOOGLE_LOGBUFFER=m
build_group google-bms "$BMS" \
    CONFIG_GOOGLE_BMS=m CONFIG_GOOGLE_BATTERY=m \
    CONFIG_GOOGLE_CHARGER=m CONFIG_GOOGLE_BMS_SW5100=m
build_group qcom-power "$KS/drivers/power/supply/qcom" \
    CONFIG_QPNP_SMBLITE=m CONFIG_QTI_QBG=m
{
    echo "Kernel: $PIN"
    echo "BMS: $(git -C "$BMS" rev-parse HEAD)"
    echo "Google SOC/MSM: $(git -C "$SOC" rev-parse HEAD)"
    echo 'Build-only experimental power drivers: NEVER LOAD ON WATCH'
} > "$OUT/PROVENANCE.txt"
find "$BMS" "$KS/drivers/power/supply/qcom" -name '*.ko' \
    -exec cp -v '{}' "$OUT/" ';'
(cd "$OUT" && sha256sum ./*.ko > SHA256SUMS)
echo 'Compiled experimental modules; charging safety NOT verified.'

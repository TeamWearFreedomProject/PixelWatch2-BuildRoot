# Stage 2 — ARM64 Linux kernel with built-in ARM32 Buildroot initramfs

**Research only — DO NOT FLASH.** This is not a verified Pixel Watch 2 bootable build.

## Current findings

- [First failed Stage 2 run](https://github.com/TeamWearFreedomProject/PixelWatch2-BuildRoot/actions/runs/38503278603): error compiling Qualcomm BAM SPS driver — NDP-only constants undefined when the NDP support configuration is off.
- [Second failed run](https://github.com/TeamWearFreedomProject/PixelWatch2-BuildRoot/actions/runs/38506637216): after the focused NDP guard patch, compilation advanced past BAM, but `drivers/usb/phy/phy-msm-qusb.c` references an undeclared function `qcom_scm_phy_update_scm_level_shifter` at line 204.
- Qualcomm engineer's [proposed upstream Linux patch, September 15 2022](https://lists.openwall.net/linux-kernel/2022/09/15/779) included that function with a secure-monitor QUSB level-shifter command, plus the header and SCM command constant. A maintainer [requested changes](https://lists.openwall.net/linux-kernel/2022/09/15/1001). Therefore the 2022 patch is **not independently verified as accepted upstream**.
- The CI-only experimental implementation in `scripts/patch_qusb_scm.py` is based on that proposal and guarded by exact source-layout checks. **Successful compilation does not establish secure monitor command compatibility on the Pixel Watch 2. Do not boot or flash images produced with this unverified function.**

## Build stages (fail fast and save time)

1. Clone Google's `android-msm-eos-5.15-tm-wear-kr3-pixel-watch` kernel and download the `argosphil/aurora` research config pinned to commit `e3d5fc73b4c97ea19ae5a0fd1d4eee1324703ad0`.
2. Locally apply the narrow SPS/NDP guard and experimental SCM helper, then **preflight-compile only three driver objects** before building the expensive ARM32 Buildroot rootfs.
3. Restore `rootfs.cpio.gz` and `rootfs.tar` from GitHub Actions cache if available; otherwise build and **save these artifacts to cache before the expensive full kernel compile**. The cache key includes the rootfs configuration and rootfs-overlay. Cache restoration is opportunistic.
4. Embed the cached/built rootfs through `CONFIG_INITRAMFS_SOURCE` and compile the complete ARM64 kernel `Image`.
5. If successful, package an Android boot header v4 `boot.img` using AOSP `mkbootimg`, then verify the header, kernel payload, absence of an external Android ramdisk, and the 64MiB size ceiling.

The initial ARM32 rootfs was confirmed by GitHub Actions as an ELF 32-bit ARM musl userspace, which is compatible *in principle* with a kernel configured for `CONFIG_COMPAT=y` and `CONFIG_COMPAT_BINFMT_ELF=y`. Real hardware/driver compatibility remains unverified.

## Boundaries

- No `init_boot.img`, `vendor_boot.img`, `dtb.img`, `dtbo.img`, or `userdata.img` is created or modified.
- The watch is never connected, flashed, erased, or repartitioned by CI.
- The existing firmware was described as TWD9, but the exact full build number and kernel/DTB compatibility are not verified.
- Both earlier Stage 2 runs failed; this update is a **new unverified experiment**, not a claimed fix.
- Kernel sources and experimental patches are all confined to disposable GitHub Actions runners.
- Upstream code belongs to its authors. Keep citations, license terms, and uncertainties visible.

## References

- [argosphil/aurora](https://github.com/argosphil/aurora) — AArch64 kernel research, internal initramfs, barebox experiments and display/USB issues.
- [UBports google-eos](https://gitlab.com/ubports/porting/community-ports/android13/google-eos/google-eos) — Halium/Ubuntu Touch TWD9.240405.001 reference, **not** proof of Buildroot compatibility.
- [Google EOS kernel](https://android.googlesource.com/kernel/msm/+/refs/heads/android-msm-eos-5.15-tm-wear-kr3-pixel-watch).

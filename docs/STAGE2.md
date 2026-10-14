# Stage 2 — Kernel + built-in initramfs experiment

**Status: not validated on hardware. Generated files are for offline inspection only. Do NOT flash or boot them on the watch yet.**

Stage 1 generated a 32-bit ARM/musl Buildroot rootfs. Stage 2 compiles an **ARM64 kernel** with that **ARM32 userspace built into the kernel** as an initramfs. It then packages the resulting *uncompressed* kernel `Image` as an **Android boot image header v4**.

## Why this layout?

- [argosphil/aurora](https://github.com/argosphil/aurora) reports that the Watch 2 bootloader expects an **uncompressed ARM64 kernel**, and that a separately supplied boot ramdisk can be lost/overridden by other Android boot partitions. An internal initramfs was one research workaround.
- The upstream kernel `defconfig` enables `CONFIG_ARM64=y`, `CONFIG_COMPAT=y`, `CONFIG_COMPAT_BINFMT_ELF=y`, so an AArch32 userspace is *plausible* on this AArch64 kernel.
- [UBports google-eos](https://gitlab.com/ubports/porting/community-ports/android13/google-eos/google-eos) specifies TWD9.240405.001 for its Halium-based Ubuntu Touch port. This does **not** prove that an arbitrary TWD9 firmware or this kernel configuration is compatible.
- [Google/Qualcomm EOS 5.15 kernel](https://android.googlesource.com/kernel/msm/+/refs/heads/android-msm-eos-5.15-tm-wear-kr3-pixel-watch) and [Monaco build config](https://android.googlesource.com/kernel/msm/+/refs/heads/android-msm-eos-5.15-tm-wear-kr3-pixel-watch/build.config.msm.monaco) are the kernel-source baseline.

## Build procedure

Open the workflow [Stage 2 - Kernel and built-in initramfs](../.github/workflows/stage2-kernel.yml). On a pull request, this runs automatically. Buildroot and the Google kernel are cloned by GitHub Actions; only the free source files and kernel config are downloaded.

1. Buildroot builds ARM32 rootfs and checks `/init`, `/sbin/init` and BusyBox.
2. EOS 5.15 source is cloned; the `argosphil/aurora` defconfig is downloaded from **commit e3d5fc73b4c97ea19ae5a0fd1d4eee1324703ad0**.
3. The kernel is configured with `CONFIG_INITRAMFS_SOURCE=<Buildroot rootfs.cpio.gz>` and `CONFIG_COMPAT=y`. `CONFIG_WERROR` is disabled for compiler compatibility. The intent is an **uncompressed ARM64 Image**.
4. AOSP `mkbootimg` packages the compiled `Image` into a **v4 boot.img** with **no additional Android boot ramdisk or DTB**.
5. `verify_bootimg.py` checks format, kernel bytes, absence of external ramdisk and 64MiB size ceiling.

**This is a first attempt at compiling the extracted upstream config, not a proven reproducible Aurora kernel build.** The original research may require extra modules, patches and exact toolchain matching; the mainline Ubuntu runner and GCC are *not* the original compiler environment.

A successful workflow establishes **only build and basic image format**. It does not prove USB logs, display, charger safety, a working shell, DTB compatibility, AVB acceptance, `fastboot boot` support, or bootability. Never infer those from a green CI run.

## Stage 2 first-run failure & targeted experiment

[Run #38503278603](https://github.com/TeamWearFreedomProject/PixelWatch2-BuildRoot/actions/runs/38503278603) successfully built ARM32/musl rootfs and reached the ARM64 kernel compiler, then failed in `drivers/soc/qcom/sps/bam.c` on `P_HALT_P_LAST_DESC_ZLT` and `P_HALT_P_PIPE_EMPTY`.

The argosphil kernel config has `# CONFIG_SPS_SUPPORT_NDP_BAM is not set`. The affected status bits are NDP-specific; the kernel source's two query blocks reference them without a guard. The CI-only workaround in `scripts/patch_bam_ndp.py` puts **exactly those two status queries** under `#ifdef CONFIG_SPS_SUPPORT_NDP_BAM`, leaving their existing conservative `return false` path in place on non-NDP builds. It does **not** define hardware bits, force-enable NDP, turn off the entire SPS driver, or modify an upstream repository. It fails if the source shape or config differs.

**IMPORTANT:** This is a scoped hypothesis intended to keep compilation moving, not an established fix for the real BAM hardware or an endorsement for booting this kernel. Test the next CI run and inspect the next error or image verification failure before any device use.

## Images & firmware

- `boot.img`: produced *only if* kernel compilation and format checks succeed; **research-only**.
- `init_boot.img`: **not generated**; do not replace existing boot partition companions.
- `vendor_boot.img`, `dtb.img`, `dtbo.img`, `userdata`: **not generated or modified**.
- Build stage does not include any flashing, wiping, repartitioning, recovery sideload or fastboot device commands.

## Next tasks after CI

- If compilation fails: inspect exact first error and compare `CONFIG_*` / external tree and toolchain with upstream research.
- If compilation passes: verify exact TWD9 build ID, bootloader, current slot, header of a matching stock `boot.img` and selected live DTB/DTBO before hardware test.
- Investigate console and power/charging behavior before making any sustained-on-device experiment.

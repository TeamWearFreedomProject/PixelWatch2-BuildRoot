# Stage 3 — offline hardware-readiness audit and ARM32 adbd rootfs

**Not boot-ready and NOT flashable. Keep Stage 2's successful boot artifact unchanged.**

The Stage 2 [passing run #38520538421](https://github.com/TeamWearFreedomProject/PixelWatch2-BuildRoot/actions/runs/38520538421) generated a v4 Android `boot.img` containing an ARM64 `Image` with built-in ARM32 Buildroot initramfs. It passed offline structure checks, **not hardware boot**.

## Fast audit (no recompilation)

[stage3-offline-audit.yml](../.github/workflows/stage3-offline-audit.yml) downloads the exact passing Stage 2 artifact, verifies SHA256SUMS, the ARM64 Image header and size, built-in initramfs configuration, ARM32 BusyBox ELF, and flags known hardware requirements.

- Does not modify or repack the original `boot.img`.
- Reports missing charger/battery stack and adbd; identifies presence of sound subsystem and experimental QUSB secure monitor source patch.
- Uploads only `audit.json` and `README.md` (30-day retention), not another copy of the large image.
- **PASS = verified structure, NOT permission to boot.**

## Battery and charging: actual upstream dependencies

The [AsteroidOS Aurora kernel recipe](https://github.com/AsteroidOS/meta-smartwatch/blob/master/meta-aurora/recipes-kernel/linux/linux-aurora_5.15.144.bb) and [external module recipe](https://github.com/AsteroidOS/meta-smartwatch/blob/master/meta-aurora/recipes-kernel/linux/linux-aurora-modules_5.15.144.bb) are research references, **not interchangeable binary modules**.

Their external module chain, in build order, is:

1. `kernel/google-modules/bms` (`misc/gvotable.h`, `CONFIG_GOOGLE_VOTABLE`, `CONFIG_GOOGLE_LOGBUFFER`): example pinned reference `51583026f264e7597808a16aa6809fb9279eb8c4`, on Google branch `android-msm-eos-5.15-tm-wear-kr3-dr-eos`.
2. `google-modules/bms` battery/charger drivers.
3. `kernel/msm` `drivers/power/supply/qcom` built externally against matching headers and `Module.symvers` with matching `CONFIG_QPNP_SMBLITE=m`, `CONFIG_QTI_QBG=m`.
4. Install `.ko` and required firmware with correct dependencies and load order, then check actual power/thermal behavior safely with appropriately qualified hardware testing.

**Currently NO such kernel-specific external modules are built or shipped by our Buildroot CI.** Stage 2 disabled the three in-tree charger symbols to work around missing `misc/gvotable.h`. They must not be left absent on a real-device-ready release. Even a compiled module is not evidence of charge safety.

## Experimental QUSB patch is still blocking hardware tests

Stage 2's `scripts/patch_qusb_scm.py` inserts a proposed, unverified QUSB SCM function. The patch is compiler-only research until the Qualcomm SCM command and kernel tree have been reconciled with a matching **device-tested** upstream port. A green build is not validation.

## ADB and USB debug

Stage 2 was a minimal BusyBox rootfs; it **does not contain `adbd`**. Buildroot 2025.02.1 has `BR2_PACKAGE_ANDROID_TOOLS_ADBD=y` so `configs/aurora_arm32_adbd_defconfig` provides a separate, experimentally buildable variant via [stage3-adbd-rootfs.yml](../.github/workflows/stage3-adbd-rootfs.yml).

This longer build is **manual-only**, avoiding a 40-minute rebuild each time a README or audit script changes. It validates an ARM32 `adbd` binary in a rootfs archive, but does **not** yet configure/verify USB ConfigFS, FunctionFS, `/sys/class/udc`, authentication or phone connectivity; merely adding `adbd` does not create a working ADB USB gadget. The resulting rootfs is **not embedded in Stage 2 boot.img**.

## Speaker silence

Stage 2 kernel config still includes `CONFIG_SOUND=y`/`CONFIG_SND=y`. The current image is **not guaranteed silent**. Later prototype work must identify all speaker paths while **preserving the separate haptic driver**; do not simply remove `snd-soc-cs40l26` or indiscriminately delete audio modules.

## Exit criteria before any hardware boot consideration

- Exact firmware/bootloader/slot/partition compatibility audited, stock image header compared;
- Charger/power management and thermal monitoring dependencies restored and validated;
- QUSB SCM patch replaced by a validated implementation;
- Consistent kernel + vendor modules + DTB/DTBO + initramfs, with a reliable debug console;
- Explicit speaker-disabled profile and separate haptics verified;
- ADB USB path tested *without* boot-risk assumptions;
- Independent review of the image and recovery plan.

This repository contains **no fastboot flash, erase, format or sideload commands** in Stage 3. 

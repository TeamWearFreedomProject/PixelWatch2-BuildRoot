# Stage 7 — ABI-coherent ARM64 Linux + eight *stored* power modules

**Research build only — DO NOT BOOT, FLASH, SIDELOAD OR LOAD MODULES on a Pixel Watch 2.**

## Why Stage 7 needs a new boot.img

Stage 6 succeeded by disabling CONFIG_TRIM_UNUSED_KSYMS to retain exported
kernel symbols. Its modules are **not interchangeable** with the earlier
Stage 5 boot image (which had a different kernel configuration). Simply
copying Stage 6 .ko files onto Stage 5 does not create an ABI-correct system.

Stage 7 compiles the untrimmed Stage 6 kernel and the eight modules **in the
same CI job**, then repackages a new Android header-v4 boot.img whose built-in
ARM32 Buildroot initramfs contains those same .ko files. This is not a
boot-safe release: it is a structure and build consistency experiment.

## The eight modules

- gvotable.ko
- logbuffer.ko
- qpnp-smblite-main.ko
- qti-qbg-main.ko
- google-bms.ko
- google-battery.ko
- google-charger.ko
- sw5100_bms.ko

The build invokes Stage 6's pinned Google sources in the successful order
**Google misc → Qualcomm power → Google BMS**, with Stage 5's pinned
kernel/rootfs sources. It does not flash, erase or interact with a watch.

## Offline gates

1. A short Python-only test verifies the newc CPIO packer before any lengthy
   kernel compilation.
2. Stage 6 regenerates Image, Module.symvers and all eight modules against the
   same exact source/config; existing build failures abort.
3. Verify all SHA256SUMS, CONFIG_MODVERSIONS=y, CONFIG_SOUND=n and
   CONFIG_TRIM_UNUSED_KSYMS=n.
4. Verify each .ko's vermagic against compiled include/generated/utsrelease.h
   (not a potentially divergent dynamic kernelrelease query). Check imported CRCs using
   modprobe --dump-modversions against the exact kernel and external
   Module.symvers.
5. Use host depmod to generate modules.dep and related metadata in a
   disposable folder. The CPIO packer preserves the Stage 5 ARM32 rootfs and
   correctly handles /lib → /usr/lib if the rootfs uses usrmerge.
6. Store all eight AArch64 modules, plus metadata, inside the built-in
   initramfs. **No init.d service, modules-load.d file, or modprobe call is
   added to load the modules at boot.**
7. Rebuild ARM64 Image with this new initramfs; verify the kernel configuration
   and exported symbol CRC file did not change, and Image bytes actually
   changed to reflect the new embedded archive.
8. Verify Android boot header v4 and 64 MiB maximum using the Stage 2 verifier.
   If the image does not fit, **abort rather than overriding the size limit**.
9. Upload diagnostic logs and the research-only artifact separately.

A successful run means that the **static artifact is coherent under the
performed checks**, not that a hardware boot, module insertion, USB serial,
battery monitoring, charging or haptics would actually work.

## Critical blockers before any real watch experiment

- Google BMS and Qualcomm .ko files have only been compiled, not tested on the
  device. DTB/DTBO and regulator/PMIC wiring, thermal limits, battery capacity,
  and charging protections need device-specific verification.
- The QUSB SCM helper is still a research patch; USB PHY/UDC and CDC ACM
  enumeration never succeeded in this native Linux port.
- Vendor module stacks, secure monitor expectations, bootloader acceptance,
  reboot/shutdown and recovery behavior are unresolved.
- CONFIG_SOUND=n does not prove physical speaker silence and may interfere
  with haptic hardware.
- Stage 5 ttyGS0 console remains physically untested, and development gadget
  IDs are not release-ready. Its login account is not security-hardened.
- No automatic power driver insertion is allowed in this stage.

The next milestone is to examine vendor device trees, regulator/PMIC dependencies
and a safe diagnostic/recovery plan **before** any physical boot attempt.
All Stage 7 CI work happens on GitHub-hosted runners, not on watch hardware.

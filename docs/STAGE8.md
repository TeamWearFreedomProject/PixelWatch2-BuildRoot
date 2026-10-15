# Stage 8 — offline audit and independent boot-readiness gate

**Target:** a future Stage 9 diagnostic boot only after substantial hardware
evidence and recovery review. Stage 8 DOES NOT authorize fastboot boot/flash.

The upstream AOSP Android boot v4 format often separates vendor-specific DTB,
ramdisk and bootconfig into vendor_boot, while the boot partition carries the
kernel. The Stage 7 research boot image is not proof that the current physical
Aurora firmware supplies a compatible vendor_boot/dtbo/bootconfig.

## What this Stage 8 CI actually verifies

- Pinned successful Stage 7 Actions artifact from run 38721433935.
- Source artifact SHA256SUMS, boot magic, v4 header, ARM64 Image header.
- Image remains under the internal experimental 64 MiB CI limit. This
  **is not proof of the device's actual boot partition or fastboot RAM limit**.
- ARM64 kernel config has CONFIG_MODVERSIONS, ARM32 COMPAT,
  USB CDC-ACM config, SOUND=n, and TRIM_UNUSED_KSYMS=n.
- ARM32 rootfs retains ttyGS0 getty/aurora-acm prototype.
- Exactly eight matching ARM64 power kernel modules exist in the newc rootfs;
  the Stage 7 ABI report has no failed CRC checks.
- Stage 7 integration report declares that no power modules are autoloaded.

The static audit produces a report with two separate fields:
- format_and_static_integrity: PASS (if all tested structures match)
- physical_boot_authorization: BLOCKED

**A green Actions check means the audit code ran successfully. It is NOT
a green light for any operation on the watch.**

## Missing evidence before a responsible device-boot review

1. Actual firmware/product/bootloader/active-slot facts, obtained from
   the *current watch*, not assumptions from prior sessions.
2. An independently verified stock recovery path and exact restore images
   for this watch and installed firmware, with user data backup options.
3. Authenticated source compatibility of stock vendor_boot and dtbo
   (DTB compatible strings, overlays, reserved-memory/PMIC regulators,
   kernel bootconfig/command line). Do not redistribute Google's stock
   binaries; review their published terms.
4. Battery BMS, charger, QBG, thermal management and PMIC protection
   behavior reviewed on this exact hardware. Eight .ko files stored in an
   initramfs but **NOT LOADED** provide no working battery management.
5. Verify QUSB SCM helper against its actual stock firmware support and
   confirm that physical USB UDC/PHY and Linux ttyGS0 debug work.
6. Review uncertain SOUND=n/GKI hidden sound config warnings and haptics.
7. Ensure backup power and a physical recovery route that does not rely
   on an untested Linux shell. Non-flashing fastboot boot is still a
   runtime execution and may cause hangs, battery-control failures or a
   device that needs a manual recovery.

**Do not manufacture affirmative evidence from CI:** no script alone
can establish safe charging or recovery on hardware it never accessed.

## Stage 9 — diagnostic design once evidence is independently satisfied

Only after the documented hardware checks and recovery risk review should
anyone plan a tightly constrained in-memory boot diagnostic. Its first
milestone is proving a return to verified stock firmware and capturing an
observable boot-stage status, not running the UI or controlling charging.

Stage 8 does not instruct flashing, disabling protection, altering bootloader
security or experimenting with batteries, power contacts or USB voltages.

References:
- https://source.android.com/docs/core/architecture/partitions/generic-boot
- https://source.android.com/docs/core/architecture/partitions/vendor-boot-partitions
- https://developers.google.com/android/images-watch

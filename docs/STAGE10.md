# Stage 10: QEMU ARM32 user-space smoke test

**No watch cable, charger, physical device or partition access required.**

## Purpose
Stage 7 built the 64-bit Aurora kernel with 32-bit ARM BusyBox initramfs
and eight power-driver modules. Stage 8/9 checked formats and explicitly
blocked physical boot, but no CI job had actually executed the ARM32 shell.

Stage 10 runs the actual Buildroot ARM32 BusyBox in qemu-arm-static, using an
isolated Ubuntu CI chroot. This is an ELF userspace runtime test, NOT a Pixel
Watch 2 SoC simulator, and the experimental ARM64 watch kernel is NOT booted.

## Workflow
1. Download successful Stage 7 artifact from run 38721433935 and verify
   every listed SHA256 checksum.
2. Parse the newc rootfs and confirm ARM32 BusyBox/adbd ELF header,
   ttyGS0 console settings, and exactly eight stored power driver modules.
3. Extract the known CPIO archive into a disposable hosted CI directory.
4. Run readelf against ARM32 binaries and shell syntax checks on the
   USB gadget scripts, but do not execute the gadget or power drivers.
5. Use the qemu-arm-static interpreter to execute BusyBox shell in chroot.
   The shell prints a known string and checks the rootfs has expected files.
6. Fail the CI if the actual ARM32 executable does not run successfully.
7. Publish logs and JSON indicating a successful userspace-only test.

## NOT demonstrated
No watch kernel boot, USB UDC, CDC ACM, PMIC, charger, thermal system, DTB,
DTBO, secure boot, reboot behavior, physical restoration or stock compatibility
is tested. adbd ELF metadata is inspected, but adbd is NOT executed here.

A green workflow result never changes hardware boot authorization from BLOCKED.
The research images are not suitable for fastboot boot, flash or sideload.

Stage 10 is entirely offline so progress can continue while the user's
physical charging cable is unavailable.

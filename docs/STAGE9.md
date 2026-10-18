# Stage 9 — Stock firmware evidence before a potential first boot

**Research only. Do not use the experimental Linux boot.img on the watch.**
Stage 8 passed static checks but explicitly BLOCKED a physical boot.

## Purpose
Stage 7 compiled ARM64 Linux with eight Google/Qualcomm power modules in
an ARM32 initramfs, but it does not autoload those modules. It has never
demonstrated safe PMIC, thermal management or USB enumeration on hardware.

Stage 9 builds two read-only analysis paths:
- The Python tool in stage9/inspect_stock.py inspects existing OEM
  vendor_boot.img and vendor_kernel_boot.img (header versions 3/4, possible empty DTB sections, concatenated base DTBs, vendor ramdisk bounds) and
  dtbo.img (Android device-tree table, entries, FDT properties, checksums).
  It never writes or modifies an image or accesses a device.
- The Windows PowerShell tool in stage9/collect-readonly-fastboot.ps1
  asks a device already in fastboot for a small allowlist of getvar
  facts: product, slot, bootloader and partition sizes. It does not
  request serial numbers or modify partitions. No data is uploaded.

## Windows read-only collection (optional)
For a device that is already safely in fastboot, run the PowerShell
script from your local project copy, specifying your fastboot.exe path:

    .\stage9\collect-readonly-fastboot.ps1 -FastbootExe "C:\platform-tools\fastboot.exe"

The output is stored in the local user profile directory as
aurora-fastboot-evidence.json. This file excludes serialno.
Do not commit this private evidence or OEM binaries to a public repo.
Do not try this if the hardware is unstable or overheating.

## Optional offline vendor boot/DTBO analysis
With trustworthy stock images for the EXACT firmware build you have,
which were obtained without modifying or flashing the watch, use:

    python stage9/inspect_stock.py --vendor-boot vendor_boot.img --vendor-kernel-boot vendor_kernel_boot.img --dtbo dtbo.img --device-evidence aurora-fastboot-evidence.json --output stock-format-report.json

You may omit any optional input; the report records those fields as
missing, and physical boot permission remains BLOCKED in all cases.
The same compatible strings or checksums do not prove DTB, kernel,
vendor ramdisk or bootloader compatibility.

## CI
The Stage 9 workflow runs a synthetic DTB, DTBO and vendor_boot parser
unit test, downloads the pinned successful Stage 8 report, confirms
its offline format checks passed and its hardware decision is BLOCKED,
and emits an offline no-private-data report. CI Success NEVER means
it is safe to use fastboot boot.

## Requirements before proposing an in-memory boot diagnostic
1. Confirm exact Aurora build, current active slot and OEM image hashes;
   do not assume an older reported firmware is still installed.
2. Review OEM vendor_boot DTB, dtbo overlays, bootconfig and vendor ramdisk
   dependencies alongside the actual custom Linux kernel.
3. Confirm device-specific bootloader acceptance, partition capacities
   and a non-destructive stock recovery method.
4. Validate real battery gauge, charger, thermal and PMIC management.
   Compiled .ko files in initramfs are NOT functional charge protection.
5. Confirm USB PHY, UDC and serial console behavior, including QUSB SCM,
   without assuming Stage 5 CDC-ACM config implies enumeration.
6. Audit possible effect of SOUND=n and GKI sound config warnings.

Unresolved hardware evidence means no physical boot testing. In
particular, do not flash, erase, sideload, disable device protections
or experiment with batteries, charging contacts or power circuitry.

Sources:
https://source.android.com/docs/core/architecture/bootloader/boot-image-header
https://source.android.com/docs/core/architecture/partitions/vendor-boot-partitions
https://source.android.com/docs/core/architecture/dto/partitions

## OEM Aurora TWD9 research correction
On some authentic Aurora factory firmware packages vendor_boot carries no
base DTB. The base DTBs are instead in vendor_kernel_boot. Stage 9 explicitly
accepts this layout and keeps compatibility/physical boot BLOCKED until a
matching vendor_kernel_boot is supplied. Synthetic fixture tests cover both
zero DTBs and concatenated DTBs; no OEM images are committed to GitHub.

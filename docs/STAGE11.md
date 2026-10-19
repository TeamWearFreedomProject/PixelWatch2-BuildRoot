# Stage 11 — Pixel Watch 2 OEM TWD9 module-dependency audit

This is an OFFLINE research comparison. **DO NOT BOOT, FLASH, OR LOAD MODULES
ON A WATCH** using artifacts from Stage 7 or Stage 11.

## Sources and privacy

The user personally provided an Aurora TWD9.240405.001 OEM factory image.
Its vendor_kernel_boot ramdisk was decompressed locally and the
modules.dep, modules.load, modules.load.charger, and modules.load.recovery
were examined. The SHA256 of the original vendor_kernel_boot image is
recorded in the small stage11/oem-twd9-power-metadata.json file to preserve
provenance.

**No OEM boot binaries, proprietary .ko files, device serial numbers or
user-specific partition dumps are published in this repository.** The
committed JSON contains eight module filenames, their direct dependency
filenames, three load profile counts and selected USB module dependencies.

The comparison loads the exact published passing Stage 7 artifact from
GitHub Actions run 38721433935 and compares its actual initramfs depmod
metadata against the derived stock metadata.

## What was found in the actual TWD9 data

There are 96 stock kernel modules in the OEM vendor_kernel_boot ramdisk.
The normal boot modules.load list has 76 entries and omits all eight power
modules in our Stage 7 experiment. Stock charger mode loads 87 and stock
recovery 96, both containing these same eight power modules.

In stock charger mode, the power group occurs in this order:
gvotable, logbuffer, qpnp-smblite-main, qti-qbg-main, google-bms,
google-battery, google-charger, sw5100_bms. Stock recovery uses the same
sequence, with more recovery-specific drivers earlier in the list.

The OEM module-dependency closure of those eight contains precisely those
eight *.ko files. However, the driver framework and regulator/SPMI/clock/
thermal services outside this closure may be kernel built-ins or additional
modules. Dependency closure does not prove hardware availability.

Key stock recovery-specific USB modules include dwc3-msm, phy-generic,
phy-msm-snps-hs, google-extcon-usb-shim, and eud. They are absent from the
Stage 7 built-in initramfs module set. They may be compiled into the Stage 7
kernel or absent altogether: check Stage 7 config/source before inferring.
Also the OEM USB softdep contains an extra PHY name not present in the
stock module inventory, so neither a bare filename match nor the extracted
dependency list proves USB enumeration.

The recorded OEM module vermagic differs from the Stage 7 kernel build.
**Do not copy the stock .ko files to the custom rootfs.**

## The CI audit

- Verifies SHA256 checksums of the pinned Stage 7 research artifact.
- Parses its *actual* rootfs CPIO and the depmod modules.dep inside.
- Asserts all eight expected power .ko exist and autoload is OFF.
- Reads the OEM-derived manifest and compares each module's direct
  dependencies against Stage 7; produces JSON for any differences.
- Lists relevant Stage 7 kernel configuration values without making
  claims that an absent .ko implies a missing kernel feature.
- Never attempts an emulated or physical PMIC/USB operation, kernel module
  insertion, fastboot boot, or flashing.
- The report always states physical_fastboot_boot_authorization BLOCKED.

## What remains before considering any experimental watch boot

1. Review kernel built-ins and exact device-tree overlay selection.
2. Verify SPMI, regulator, watchdog, QBG, thermal, charger and battery
   protection architecture; the eight .ko are NOT autoloaded in Stage 7.
3. Verify physical USB PHY, DWC3 gadget path and recovery observability.
4. Validate a return-to-stock/recovery plan for the exact installed build.
5. Review older bootloader/firmware status without downgrading or flashing
   bootloader/radio as part of any Linux experiment.

A green GitHub Actions check verifies research consistency only, not
safe hardware readiness.

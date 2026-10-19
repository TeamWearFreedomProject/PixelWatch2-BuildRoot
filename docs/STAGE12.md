# Stage 12 — TWD9 base DTB / DTBO vs Stage 7 kernel configuration

**Offline static research only. A green CI never authorizes booting or
flashing this watch. Charging, battery and recovery behavior remain unproven.**

## Evidence source
Actual OEM Pixel Watch 2 Aurora TWD9.240405.001 images supplied by the user:
- vendor_kernel_boot.img SHA256:
  d7de39258a894ea00358559c131150a9006901803c61819b455e5550ba23e892
- dtbo.img SHA256:
  cd00526c4abed67d5c06d879792562415357afd26316d33784fe5eae05abe48c

These were inspected locally, not committed to the repository. Only a
limited JSON of their public device-tree compatible/status properties,
board ID / revision pairs, and image hashes is present in stage12/.

The vendor_boot DTB section was empty. vendor_kernel_boot supplies two
base FDT blobs:
- Qualcomm MonacoP: qcom,monacop (236537 bytes)
- Qualcomm Monaco: qcom,monaco (236485 bytes)

Both base FDTs list:
- qcom,spmi-pmic-arb, qcom,spmi-pmic and qcom,qpnp-power-on
- qcom,qpnp-pm5100-smblite with status okay
- qcom,qbg with status disabled (!!)
- qcom,spmi-temp-alarm and qcom,spmi-adc5-gen3 (ADC status ok)
- qcom,dwc-usb3-msm, snps,dwc3 and qcom,usb-hsphy-snps-femto
- qcom,msm-watchdog and usb-nop-xceiv

The OEM dtbo.img has 11 board/revision overlays. All eleven contain
google,battery, google,charger, google,extcon-usb-shim and
google,smblite-hvdcp compatible nodes. **We do not know which overlay this
particular bootloader selects**, and have NOT applied the corresponding
overlay onto the base FDT or observed the effective merged FDT.

## What Stage 12 CI checks

1. Stage 12 compares the curated metadata shape with the measured counts
   and critical base statuses (including qcom,qbg being disabled).
2. Downloads the exact passing Stage 7 artifact from run 38721433935,
   verifies SHA256SUMS, checks all eight stored power modules and rejects
   unexpected auto-loading of power modules.
3. Reads the actual Stage 7 kernel.config and confirms ARM64, COMPAT,
   MODULES, MODVERSIONS, SPMI/REGMAP_SPMI, QCOM_SCM, REGULATOR, THERMAL,
   USB_DWC3, USB_GADGET and USB_CONFIGFS_ACM are enabled, with SOUND
   disabled.
4. Lists candidate kernel CONFIG symbols **as search hints, not binding
   proof** for the OEM compatible strings. No exact of_device_id table,
   driver probe log, runtime SPMI/ADC, battery or USB behavior is proven.
5. Uploads a report that always has physical boot authorization BLOCKED.

## Important difference versus Stage 11

Matching eight stock power .ko names and direct module dependencies does
not mean an operational BMS. The base FDT actually disables the QBG node,
while the OEM charger-related devices partly come from board-specific
overlays. The Stage 7 experimental external power drivers remain
**not auto-loaded**. A boot attempt now could lack reliable battery,
charging and thermal supervision.

## Next research gates

- Independently establish the exact selected OEM overlay for the active
  board hardware and produce a reviewed merged FDT *offline*.
- Compare exact EOS kernel source of_device_id binding tables to the
  merged device-tree compatible values. Kconfig-y does not prove matching.
- Reconcile Qualcomm USB DWC3 wrapper, PHY and UDC with serial-gadget
  console strategy; physical USB enumeration is still untested.
- Prove charger, battery gauge, thermistor, regulator, watchdog and power
  safety and dependable return-to-stock recovery before any hardware run.

No OEM proprietary binary has been published by this stage, and no
watch commands or flashes are performed.

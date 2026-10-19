# Stage 17 — AArch64 PMIC temperature-alarm compilation proof

**This is a CPU-side offline compile experiment only. Do not boot, flash,
load or deploy anything built here to the Pixel Watch 2.**

## Why this stage exists
The passing Stage 12-16 offline audits found that the existing Stage 7
kernel config had CONFIG_QCOM_SPMI_TEMP_ALARM disabled. OEM TWD9 base DTBs
contain the Qualcomm SPMI PMIC temperature alarm compatible string. A
source-level of_device_id match alone did not establish that the driver
was selected and built. Even a compiled driver would not establish
real-world thermal management or safe battery charging.

## Reproducible research experiment
1. Fetch the exact passing Stage 7 research artifact (run 38721433935)
   and SHA256-verify its kernel.config/SOURCES.txt/boot image.
2. Clone **only the exact EOS kernel source git commit** recorded in Stage 7.
3. Start with its original Stage 7 .config in a completely new scratch
   output folder. Keep the original intact.
4. Verify the PMIC temperature alarm Kconfig declaration and its actual
   Kbuild object rule exist in the pinned kernel.
5. Enable CONFIG_QCOM_SPMI_TEMP_ALARM=y in the scratch config and run
   olddefconfig to test whether dependency constraints allow it.
6. Ensure ARCH=arm64, SPMI, thermal support, SOUND=n and the export
   configuration remain as expected. Fail if the alarm cannot be enabled.
7. Compile only drivers/thermal/qcom/qcom-spmi-temp-alarm.o with aarch64-linux-gnu
   GCC. Require a real ELF64 little-endian AArch64 relocatable object.
8. Save the original/research configs and a JSON report of changed config
   options, source pin, ELF hash and limitations. The compiled binary is
   **not included in the published artifacts**.

This deliberately does NOT compile an Android boot image, build the
eight Google battery modules again, create a bootable image, or change
power-driver autoload. It does not touch the device.

A green Actions check proves the limited source/config/object
experiment succeeded, nothing more. It cannot establish thermistor
readings, trip-point configuration, interrupt delivery, charging
termination, PMIC hardware binding, safe shutdown or recovery.

## What remains
- Compare exact OEM merged overlays for the user's watch board revision.
- Map PMIC thermal alarm IRQs/ADC resources and thermal zones against the
  reviewed device-tree and actual external Qualcomm/Google battery stack.
- Establish a trustworthy physical recovery method and safe power/thermal
  behavior before any hardware experiment.
- Review USB PHY/UDC and serial console readiness independently.

The existing Stage 7 boot image must remain labeled DO NOT BOOT.

# Stage 5 — experimental USB CDC-ACM serial shell

**Build-only research. Never boot or flash this image on Pixel Watch 2.**

Stage 4 compiled an ARM64 Linux kernel with an embedded ARM32 BusyBox
initramfs, Linux SOUND=n and an adbd binary. Stage 5 is the preparation
of a local physical-USB shell without assuming Wi-Fi/SSH or ADB works.

## USB serial approach

- Buildroot rootfs includes a ConfigFS ACM function setup script, a BusyBox
  init.d service and a ttyGS0 getty via /etc/inittab.
- When an actual compatible Linux USB device controller is available, the
  gadget might expose CDC ACM as a COM port on Windows or /dev/ttyACM0
  on Linux. Neither outcome has been tested on this watch.
- The ConfigFS setup uses conventional Linux example VID/PID 1d6b:0104,
  NOT a uniquely assigned Aurora USB identity. Replace before any release.
- A login service on physical USB needs password/security configuration
  before any real-device deployment. The current setup is research-only.
- The adbd binary is still present, but USB ADB is not configured or tested.
  SSH is not included; it would additionally require working IP connectivity.

## Build procedure

Stage 5 is isolated from the Stage 4 passing image and branch. GitHub Actions:

1. Runs the existing Stage 2 kernel preflight to catch compiler errors early.
2. Configures Buildroot 2025.02.1 ARM32 adbd rootfs with a Stage 5-specific
   overlay and an init-table post-build script.
3. Verifies the executable ACM helper, init.d hook, ttyGS0 entry and ARM32 ELF.
4. Checks Linux kernel SOUND=n, ARM32 compatibility, ConfigFS/ACM and DWC3
   config symbols while keeping charger/gauge drivers disabled.
5. Embeds rootfs in an ARM64 Image and repacks an Android header-v4 boot.img
   using the successful Stage 2 toolchain and packager.
6. Uploads separate diagnostic and research-only artifacts (30-day retention).

The ARM32 Buildroot output is cached for subsequent runs where possible.
A passing CI does NOT demonstrate actual boot or USB enumeration.

## Safety blockers (unchanged)

- Power supply/charging/fuel gauge drivers QCOM_POWER_SUPPLY, QPNP_SMBLITE
  and QTI_QBG are disabled. External Google BMS and gvotable dependencies
  remain unintegrated. Therefore battery/charging behavior cannot be trusted.
- QUSB PHY depends on an experimental SCM level-shifter helper copied from
  an unverified kernel patch; actual boot firmware compatibility is unknown.
- Vendor module stack, DTB/DTBO, PHY/UDC, display, touch and modem behavior
  are not validated.
- SOUND=n does not prove physical speaker silence or working vibration.

**Never use fastboot boot/flash/erase with this image.** Stage 6 should
work on properly matched Google BMS/Qualcomm power driver modules and verify
USB PHY prerequisites before any hardware diagnostic plan.

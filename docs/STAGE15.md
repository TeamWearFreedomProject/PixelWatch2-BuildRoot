# Stage 15 — ARM32 CDC ACM USB gadget startup and login readiness audit

**No watch, port, flash, boot or live USB gadget is used by this stage.**

Stage 10 demonstrated that the ARM32 BusyBox shell could run via
QEMU user mode, but neither that test nor Kconfig=y proved that USB
communication with the physical watch works.

Stage 15 extracts the exact SHA256-verified Stage 7 rootfs CPIO and
reads its real init.d service, gadget script, serial-console inittab,
development marker, and kernel.config. No gadget service is executed.

Key facts confirmed or flagged:
- The rootfs contains the development marker enabling the prototype
  USB script. The init.d service invokes it on start.
- The script checks /sys/class/udc and attempts ConfigFS CDC ACM setup,
  including binding to a registered UDC if one is present.
- Linux Foundation example USB VID/PID values appear in the prototype;
  they are NOT licensed product identifiers for Aurora.
- ttyGS0 BusyBox getty is configured. Its credentials, visibility and
  security have not been demonstrated on a real watch.
- Actual QUSB SCM helper, UDC enumeration, PHY power-up, DT overlay
  selection, charger, and thermal safety are unverified.
- No standalone ADB setup or successful physical USB login is claimed.

The source remains research only. Do not assume booted-safe operation,
and do not redistribute the demonstration USB identity values as if
assigned to this device.

A passing Actions run is a static audit, not a permission to use
fastboot boot. Physical boot authorization stays BLOCKED.

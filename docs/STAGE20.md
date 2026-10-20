# Stage 20 — bounded USB-shell boot candidate for aurora

This bundle is an **unsigned first-boot test candidate**, not a hardware-tested
OS release. Its purpose is to make a short Stage 21 test concrete. No device
has been booted by CI. A green build does not prove PMIC, charging, recovery,
USB PHY, bootloader acceptance or runtime temperature behavior.

## What is in the image

- The exact EOS kernel and conditional PMIC thermal Kbuild fix verified by
  Stage 19, with `CONFIG_SOUND=n` and ARM32 compatibility enabled.
- Google's exact SHA-pinned USB extcon shim is built in with its own Kconfig
  gate. Local libfdt inspection of all 22 OEM base/overlay candidates resolves
  the USB controller's first extcon provider to this shim. Its upstream code
  reports USB connected for debugging if the charger-side supplier cannot
  provide notifications. No new charger-driver implementation is substituted.
- A dedicated ARM32 `/init` running as PID 1. It mounts only proc, sysfs,
  devtmpfs, devpts and RAM filesystems. It does not use the old inittab,
  generic rc scripts, filesystem table, Android partitions, ADB or network
  services. The eight old-ABI `.ko` files are removed, not silently reused.
  A static character-device `/dev/null` is present before devtmpfs mounts,
  so the early background deadline process does not depend on a console.
- CDC ACM setup waits up to 30 seconds for exactly one UDC, creates a single
  serial function, then starts a **physical-USB root shell** on ttyGS0 without
  a password prompt. This is a private debug session, not a network service.
- An independent process waits **90 seconds from PID 1**, then asks the kernel
  to restart to `bootloader`. If that syscall returns, it tries ordinary
  restart. A panic requests a restart after 10 seconds via the cmdline.

The diagnostic cmdline uses `fw_devlink=permissive` so a missing supplier
driver does not prevent the shim's own debug fallback from probing. This
changes probe dependency enforcement for the test; it does not prove that
the USB PHY, clocks, regulator consumers or charger operate correctly.

The deadline is a software process, **not a hardware watchdog**. It cannot
help if the kernel never reaches PID 1, is completely wedged, cannot schedule
the process, or lacks functioning restart support. Restart reason handling
and return to Fastboot remain untested on the watch. Do not rely on this
timer as the only exit route.

This diagnostic userspace does not provide working battery-gauge or charger
management. PMIC die-temperature alarm code is linked; real readings and
protection are unverified. USB descriptor MaxPower is a declaration, not a
physical current limiter. The display/UI is not implemented; a blank screen
or old splash is possible even when a shell is running.

## CI evidence

The build checks pinned Stage 7/19 inputs, ten host tests, the real ARM32
return helper's harmless `--check` branch under QEMU, and the actual ARM32
BusyBox `/init --check` branch and necessary applets. CI never executes the
helper's `--request` branch or mounts a live USB gadget.

After compiling, it checks AArch64 vmlinux driver/initcall linkage and compares
the decompressed initramfs **inside final vmlinux** to the new rootfs. It
packages the new uncompressed Image using Stage 7's verified unsigned Android
header v4 template, with no separate Android boot ramdisk. The payload and
size are verified; the size must fit the historical 64-MiB limit. Actual
firmware acceptance and current device capacity require fresh preflight.

The Linux Foundation example VID/PID `1d6b:0104` is for this private development
test, not an assigned Aurora product ID. CDC class/subclass `02/02` follows
Microsoft's inbox Usbser.sys compatible-ID guidance; enumeration and driver
binding on this watch/PC are still untested.

## Stage 21: first check the actual watch

1. Before a custom boot, rehearse getting the **current stock watch** back to
   Fastboot using its buttons. Google's current recovery page says to hold
   crown and side button about **35 seconds or longer** for a forced restart;
   for Fastboot, tap the upper-left and lower-right screen edges together as
   the G logo appears. Stop at Fastboot; do not select factory reset or wipe.
   This is a documented route, not a successful rehearsal on this watch.
2. In Windows PowerShell, place the bundle with platform-tools or pass the
   actual executable path. Run the device-read-only collector:

   ```powershell
   .\preflight.ps1 -Fastboot .\fastboot.exe -Image .\boot-stage20.img
   ```

   Review `stage21-preflight.json`: product must be **aurora**, bootloader
   unlocked, slot known and image size suitable. Compare the image SHA256
   with this bundle's `SHA256SUMS`. The historical firmware evidence was
   TWD9 / bootloader `eos-0.4-11366482`, slot b; these are not current readings.
   Unknown/different firmware needs review, **not a bootloader/radio downgrade**.
   The script issues only named `getvar` commands and never boots or flashes.
3. After that evidence and physical recovery are checked, the intended test
   is a **one-time RAM boot**, without changing slots or flashing partitions:

   ```powershell
   .\fastboot.exe boot .\boot-stage20.img
   ```

   This is the Stage 21 test command, not something CI or preflight executes.
   Do not substitute `flash`, erase, repartition, DTBO changes or userdata writes.
   Observe this short diagnostic session; it is not a wearable/charging test.
4. If Windows exposes a new COM port, identify it instead of guessing:

   ```powershell
   Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name
   .\serial-console.ps1 -Port COM7
   ```

   Replace COM7 with the actual new watch port. Ctrl+] closes the terminal.
   Success evidence is the `AURORA_STAGE20_USB_SHELL` banner plus commands
   such as `uname -a`, `cat /proc/uptime` and `aurora-info`. USB/COM access
   replaces ADB in this candidate. Automatic return disconnects the port.

If there is no COM port, distinguish bootloader rejection, an early kernel
failure and a USB failure; absence of USB alone does not prove `/init` never
ran. Record host output and the elapsed time to any return to Fastboot. If
automatic return does not occur, use the rehearsed physical restart route.
Stop a session that behaves abnormally rather than repeating it unattended.

## Bundle and references

The successful Actions artifact includes `boot-stage20.img`, `rootfs.cpio.gz`,
`kernel.config`, JSON verification reports, two PowerShell scripts, source
patches/pins and `SHA256SUMS`. These prove build structure, not runtime safety.

Primary references, checked 2026-10-20:

- Google restart/Fastboot controls: https://support.google.com/googlepixelwatch/answer/13575675?hl=en
- Microsoft Usbser.sys class/subclass: https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-driver-installation-based-on-compatible-ids
- Upstream device research and kernel-integrated initramfs observations: https://github.com/argosphil/aurora
- Exact EOS source: https://android.googlesource.com/kernel/msm/+/99c2312e4f131f45993d7f4d741e61d647e7ed10
- Buildroot ARM32 userspace provenance: Stage 7 input run 38721433935, Buildroot 2025.02.1.

Aurora project implementation and integration: TeamWearFreedomProject with
ChatGPT assistance, building on the credited upstream projects and their
respective licenses. This is not a product of Google, Microsoft or AsteroidOS.

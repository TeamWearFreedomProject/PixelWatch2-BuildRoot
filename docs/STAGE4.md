# Stage 4 — silent-build ARM64 kernel + ARM32 adbd rootfs

**Experimental offline artifact. NEVER use `fastboot boot`, `fastboot flash`, or
`fastboot erase` with this build.** This stage is not a hardware boot test.

## Goal

Compile a new Android boot-header-v4 `boot.img` containing:

- an ARM64 Pixel Watch 2 research kernel;
- a built-in ARM32 Buildroot-musl initramfs containing `/usr/bin/adbd`;
- Linux sound-core configuration **`# CONFIG_SOUND is not set`** to avoid ALSA-driven speaker output in this research kernel.

Both ABI architecture and sound-core state are asserted during the CI build.
The stage intentionally inherits Stage 2's experimental BAM and QUSB SCM
patches, and its **disabled charger, battery and fuel-gauge drivers**, so the
result must **not** be run on hardware.

## ADB status

The image contains an ARM32 `adbd` binary (subject to successful Buildroot
build). It does **not** establish a working USB connection: ConfigFS gadget,
FunctionFS mount, USB UDC enablement, daemon lifecycle and ADB authorization
are not configured or validated. The presence of the binary alone is not a
debug connection. No ADB daemon is configured to start automatically.

## Speaker status

Linux `CONFIG_SOUND=n` removes the kernel's ALSA sound subsystem. This is
a build-policy check, not a guarantee of absolute silence from bootloader,
firmware, vendor services, or additional haptic/audio paths. Hardware haptics
are also **unverified**: no claim that vibration works has been made.

## Battery and USB blockers

See [Stage 3](STAGE3.md). There is no matching out-of-tree Google BMS/gvotable
or QCOM charger stack, no validated QUSB SCM command, and no confirmed display,
touch, UDC or power-management startup. The kernel is *not charge-safe*.
Booting a partially supported power stack may cause shutdown or unexpected
behavior. **Do not perform a watch boot test.**

## CI

The workflow [stage4-silent-adbd.yml](../.github/workflows/stage4-silent-adbd.yml)
starts from the experimental Stage 3 branch. It:

1. Preflight compiles previously failing kernel drivers.
2. Builds/caches the separate ARM32 adbd rootfs, validating the ELF ABI.
3. Switches kernel `CONFIG_SOUND` off **before** embedding the rootfs.
4. Reuses Stage 2's proven compiler/packer and validates Android header v4,
   ARM64 image magic and 64MiB size boundary.
5. Packages logs + research-only image as separate Artifacts for 30 days.

**Exit criterion:** green CI = mechanically assembled research image.
**Not met:** physical boot safety, working ADB, functioning vibration, verified
speaker silence and battery management.

## Next milestone

Stage 5 should address the actual platform drivers and safe logging:
match kernel/vendor module ABI, restore charging and battery data safely,
replace the experimental QUSB SCM implementation, then establish debug input
and USB gadget initialization. That is work for a *separate* reviewed build
before any watch boot attempt.

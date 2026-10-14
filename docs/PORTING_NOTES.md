# Pixel Watch 2: verified references and open issues

This is an **evidence log**, not a flashing guide. Device model is **Pixel Watch 2 Wi-Fi / aurora**, Qualcomm SW5100 / Monaco platform.

## 1. Firmware baseline: UBports Ubuntu Touch

Source: [UBports google-eos README](https://gitlab.com/ubports/porting/community-ports/android13/google-eos/google-eos)

- UBports asks for **TWD9.240405.001** (April 2024, Android 13-based) before their port; mentions **TWD9.240805.001.A2** as less tested.
- Their deployment uses a **Halium/Android compatibility base** with multiple Android-style partitions. It is **not** a recipe for a Buildroot-only Linux.
- Their instructions include repartitioning/erasing `product`, `system_ext` and/or `userdata`. **Do not copy or run those destructive operations for this project.**
- A user's description of simply “TWD9” is not enough to establish the exact bootloader, boot, DTBO and vendor firmware versions. We must inspect the full build ID before making boot compatibility claims.

## 2. Linux/AsteroidOS research by argosphil

Source: [argosphil/aurora README](https://github.com/argosphil/aurora)

Reported observations in the upstream research (not independently reproduced here):

- The Pixel Watch 2 bootloader is reported to accept **Android boot image header v4**, with an **uncompressed ARM64 kernel Image**. The bootloader/firmware is reported to supply DTB information.
- Separately supplied ramdisks can be overridden or fail to reach `/init` reliably. The author tried a **built-in kernel initramfs** and an intermediate **barebox** boot path.
- A modified **Linux 5.15.104 ARM64** configuration exists in their `defconfig`, and their Git submodules reference Google/Qualcomm EOS kernel trees and out-of-tree modules. Match kernel versions and module ABI exactly.
- Upstream reports a working ADB prompt using built-in modules. Display is still difficult: **continuous-splash framebuffer**, IOMMU mapping and cache coherency issues, with partial/flickering output. Do not assume an available DTBO automatically enables the panel.
- USB enumeration may be intermittent; `pstore` / `ramoops` was reported useful.

These findings strongly favor **first generating an independent rootfs**, then solving the precise initramfs/kernel integration and diagnostic transport; **not** immediately flashing an arbitrary image.

## 3. DTB / DTBO research

Owner-provided DTB and DTBO were analyzed separately in this conversation, yielding Monaco/MonacoP base DTBs and multiple Aurora/Eos board revision overlays. The **exact overlay and panel variant must be selected by matching hardware identifiers** before any kernel/device-tree experiments. Binary DTBs extracted from firmware are not copied into this repository.

## 4. Buildroot Stage 1 limitations

The `aurora_minimal_defconfig` intentionally produces just **arm64/musl/BusyBox rootfs.tar and rootfs.cpio.gz**.

This initial configuration **does not** build a bootable `boot.img`, Linux kernel, vendor modules, touchscreen driver, display driver, charging controls, Wi-Fi, watch UI or persistent storage.

For future work:
1. Capture exact firmware build, Android boot-image layout, `fastboot getvar` facts and partition/slot state (read-only).
2. Choose a matching kernel source+config; determine **built-in initramfs vs barebox** first.
3. Make USB/debug logging deterministic, then display and touch.
4. Only after verified boot + input + charging/power safety, develop an original HarmonyOS-inspired UI.

## 5. License and attribution

- Upstream Linux/driver sources carry their own licenses.
- Source links are references only; no upstream files copied here at bootstrap stage.
- Avoid using unreleasable vendor firmware blobs in the public repository.

# Stage 23 — inventory the display and input path on the working kernel

Stage 22 reached the real watch's USB shell with kernel build #22. A complete
dmesg snapshot at uptime 19.15 contained KASAN initialization, no report of
the earlier qnoc/provider use-after-free, and later registration of DISP,
GCC and GPU clocks. The user subsequently confirmed return to Fastboot.
This is one boot observation, not long-term stability validation.

Stage 23 reuses that exact boot-stage22.img and its unchanged 90-second
deadline. It adds a pinned artifact audit and a Windows paste-only diagnostic
that inventories FB/DRM, input, selected live DT properties and platform
bindings. It builds no new boot image and changes no kernel or rootfs.
The next hardware action is described in stage23/WINDOWS-CAPTURE.md.

## What the existing image contains

| Item | Actual Stage 22 artifact | Meaning |
| --- | --- | --- |
| Userspace | ARM32 musl + BusyBox | Not an Alpine/OpenWrt/Termux rootfs |
| Package management | No pkg/opkg/apk/apt/dpkg/rpm/dnf/pacman command paths | Add packages in the host Buildroot config and rebuild the rootfs |
| DRM common layer | CONFIG_DRM=y; DRM_MIPI_DSI=y | Infrastructure is available; does not establish controller binding |
| In-tree MSM DRM | CONFIG_DRM_MSM is not set | That in-tree display driver is not selected |
| Simple framebuffer/DRM | FB_SIMPLE and DRM_SIMPLEDRM not set | No generic splash framebuffer driver enabled through these options |
| Framebuffer console | FRAMEBUFFER_CONSOLE not set | Kernel console text is not configured for a framebuffer |
| Input | INPUT_EVDEV and INPUT_TOUCHSCREEN enabled | The latter is a menu/category option, not proof of a touchscreen driver |
| Modules and firmware | No .ko or lib/firmware files in the initramfs | External drivers/firmware were not supplied in this userspace |
| Sound and KASAN | SOUND=n; KASAN=y | Preserved from the tested Stage 22 image |

Buildroot creates the root filesystem from software selected on the build
host; it does not provide a configured target package repository here.
Manually copied compatible binaries can run, but RAM-only changes disappear
on reboot. Installing opkg/apk itself would not make arbitrary distribution
packages compatible or create persistent storage or a package feed.

## Source references and next implementation decision

The argosphil/aurora research, pinned at
e3d5fc73b4c97ea19ae5a0fd1d4eee1324703ad0, records continuous-splash handoff,
IOMMU mapping and non-coherent framebuffer problems. Its display-driver
gitlink points to de60505351e76a27be346eb381e460eb746c52a9; touch points to
c4b2d5c1e5b4c54e175725dc27b2d34954fdfe26. These are research references,
not an assertion of module ABI or panel compatibility with our new kernel.

In that separate Google display tree, msm/msm_drv.c registers a platform
driver called msm_drm with OF matches including qcom,mdss and qcom,sde-kms.
Its build uses an external module tree. Therefore DRM_MSM=n in our kernel
config alone does not describe every possible vendor-driver integration.
The Stage 22 build scripts integrate the USB shim, thermal patch and Monaco
unwind patch; they do not build or link this external display/touch tree.

Before choosing driver integration or framebuffer handoff, collect the
actual bootloader-selected DT nodes/panel names, current FB/DRM device nodes,
input devices and controller binding. A reserved splash region does not
by itself establish a usable framebuffer. Do not invent framebuffer geometry
or infer a working display from clock-provider registration.

The diagnostic reads sysfs/procfs and prints to USB. It does not mount Android
partitions or debugfs, load modules, read /dev/mem, change brightness, write
framebuffer pixels, issue a modeset or change the existing restart timer.
The PowerShell process writes only its PC log file. COM5 is the observed port
on this user's PC, not a universal port number.

## Validation and capture interpretation

Host fixture tests cover absent/present devices, NUL-separated DT properties,
unchanged fixture contents, rejection of unmarked test roots, complete and
incomplete markers, echoed marker text, lost bytes, inventory limits, wrong
kernel builds, and KASAN initialization versus actual error reports.
Each command is a complete shell line of at most 1024 bytes, below the TTY
canonical-line limit. The Windows code waits for the existing shell banner
and prompt and sends commands 500ms apart while continuing to drain serial.
The host buffer is enlarged; missing-byte notices and marker loss remain
evidence of an incomplete capture, not evidence of health.

CI checks shell/Python syntax, the fixture tests, generated-document parity,
PowerShell parsing and the pinned Stage 22 artifact audit. These are host
checks, not a new display/touch hardware test. No panel or input behavior
is declared working before a user capture and a later explicit functional
test. The capture analyzer does not infer Fastboot return from disconnect.

## References

- Buildroot package management: https://buildroot.org/downloads/manual/manual.html#faq-no-binary-packages
- Source research: https://github.com/argosphil/aurora/tree/e3d5fc73b4c97ea19ae5a0fd1d4eee1324703ad0
- Display driver: https://android.googlesource.com/kernel/msm-extra/display-drivers/+/de60505351e76a27be346eb381e460eb746c52a9/msm/msm_drv.c
- Existing candidate: https://github.com/TeamWearFreedomProject/PixelWatch2-BuildRoot/actions/runs/39373072577/artifacts/12242497802

Integration and diagnostics: TeamWearFreedomProject with ChatGPT assistance,
building on the Google/Qualcomm, argosphil/AsteroidOS and Buildroot work
credited by earlier stages. Existing source copyrights and licenses apply.

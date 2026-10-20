# Stage 22 — fix Monaco interconnect probe error unwind

Stage 21 reached the real watch's USB shell with Stage 20, but reported
KASAN use-after-free in __list_add_valid -> icc_provider_add -> qnoc_probe
during deferred probing. This candidate changes the kernel error-unwind
paths for the pinned Monaco interconnect provider. It must be hardware
tested separately; the Stage 21 success does not validate the new kernel.

## Change and limits

After successful bus-clock enable, a regmap error now disables those clocks.
After provider registration, QoS clock-acquisition or enable failure now
unregisters the provider before returning and releasing devm allocations.
Node-creation failures still remove all created nodes and disable the QoS
clocks; common labels unregister the provider and disable the bus clocks.
Original error values, including -EPROBE_DEFER, are preserved. The successful
probe path is unchanged.

The rootfs is copied byte-for-byte from the hardware-tested Stage 20
artifact. The dedicated ARM32 userspace, USB gadget identity, sound-disabled
configuration, cmdline and 90-second software restart request are preserved.
KASAN remains enabled. The userspace banner and prompt still say Stage 20;
identify the new kernel by build #22 and the startup banner aurora-ci@stage22.
No Android storage partitions are mounted by this diagnostic userspace.

This fix does not supply missing clock/regulator/charger drivers or prove
display, touch, battery management, thermal protection or long-term stability.
It does not change or validate the production qnoc_remove/unbind path.
Do not lengthen the session or suppress KASAN to claim the fault is fixed.

## Executable regression evidence

The host test extracts the actual qnoc_probe function and actual
icc_provider_add/del functions from SHA-checked pinned source. It compiles
them with AddressSanitizer and UndefinedBehaviorSanitizer. Surrounding kernel
APIs, allocations, clocks and nodes are modeled by the fixture, not a real
kernel or a concurrency test.

The original source is the negative control: a QoS clock-acquisition defer
is followed by devres release and retry. ASan must report heap-use-after-free
through the stale provider list. The patched code must pass 18 scenarios:
success with and without QoS clocks, missing match data, allocation failures,
bus clock lookup/enable, regmap and provider registration failures, QoS
lookup/defer/enable failures, partial node creation, and repeated failures
followed by success. Cases assert that no provider/node registrations or
enabled clocks remain after failed probes. Host leak-sanitizer scanning is
disabled for proc/ptrace portability; resource accounting is explicit.

This deterministic reproduction strongly supports the error-unwind diagnosis,
but the incomplete Stage 21 allocation/free trace does not establish that
every hardware KASAN report has the same cause. A new real-watch trace is
required to confirm the observed report disappears.

The workflow also preserves all kernel config options, checks the unchanged
rootfs inside final vmlinux, verifies PMIC thermal and USB shim linkage,
checks the new boot payload/header and enforces the historical 64-MiB limit.
The complete artifact is uploaded only after these checks succeed.

## Hardware comparison on the existing restricted Windows PC

Use WINDOWS-CAPTURE.md. Its code is pasted directly into interactive
PowerShell; no additional software, driver installation, .ps1 execution or
execution-policy change is required by the procedure. Other PC restrictions
can still prevent access. COM5 is the port observed in Stage 21; verify it
again if enumeration changes.

Keep the physical return-to-Fastboot route available. The software deadline
is not a hardware watchdog and cannot recover an early or completely wedged
kernel. Use one temporary fastboot boot test with the new image and collect
the kernel version, uptime and full dmesg. The capture includes markers and
writes stage22-serial.log on the PC. Do not flash partitions, change slots,
erase data or downgrade bootloader/radio to run this test.

Compare the saved log for:

- Linux build #22; unchanged Stage 20 shell banner is expected.
- Complete output between the Stage 22 dmesg markers, including any KASAN
  allocation/free context. A capture without the end marker is incomplete.
- Whether the specific qnoc/provider-list UAF returns; missing clock or
  deferred-probe messages can remain even when the unwind fault is fixed.
- Return to Fastboot around the unchanged deadline, reported separately from
  kernel/shell success. A silent/disconnected serial port alone is insufficient.

## Sources

- Kernel revision: 99c2312e4f131f45993d7f4d741e61d647e7ed10.
- Driver: https://android.googlesource.com/kernel/msm/+/99c2312e4f131f45993d7f4d741e61d647e7ed10/drivers/interconnect/qcom/monaco.c
- Provider list: https://android.googlesource.com/kernel/msm/+/99c2312e4f131f45993d7f4d741e61d647e7ed10/drivers/interconnect/core.c
- Stage 20 input run: https://github.com/TeamWearFreedomProject/PixelWatch2-BuildRoot/actions/runs/39363419356
- Hardware observations: docs/STAGE21.md and stage21/hardware-result.json.
- Windows policy behavior: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies

Integration and diagnostics: TeamWearFreedomProject with ChatGPT assistance,
building on the Google/Qualcomm kernel, upstream USB shim and Buildroot work
credited in earlier stages. Existing source copyrights and licenses apply.

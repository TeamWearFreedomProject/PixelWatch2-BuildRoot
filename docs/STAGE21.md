# Stage 21 — first hardware boot and USB shell reached

On 2026-10-20 (JST), the user temporarily booted the unchanged Stage 20
candidate on a Pixel Watch 2. Their pasted serial capture contains the
Stage 20 banner and successful shell commands. This is hardware evidence
reported by the user, not an operation performed by CI or the assistant.

## Observed result

| Item | Evidence | Scope |
| --- | --- | --- |
| Device | Fastboot product aurora; unlocked yes; is-userspace no; slot b | Current user-supplied preflight |
| Bootloader | eos-0.4-11366482 | Matches the historical Stage 20 reference |
| Boot capacity | boot, boot_a and boot_b: 0x4000000 | Candidate is 64,143,360 bytes |
| Kernel | 5.15.137-g99c2312e4f13-dirty, aurora-ci@stage20, build #20 | Actual serial kernel banner |
| USB | Windows exposed USB Serial Device on COM5 | No added driver installation was reported |
| Userspace | AURORA_STAGE20_USB_SHELL and aurora-stage20# prompt | The candidate contains ARM32 BusyBox userspace |
| Command execution | uname -a returned aarch64 GNU/Linux; /proc/uptime returned 9.74 29.41 | aarch64 describes the kernel, not the BusyBox ELF ABI |
| Exit route | User reported automatic return to Fastboot at approximately 90 seconds | Consistent with the PID 1 deadline; no exact guest/host timing trace |

Candidate identity:

- Source commit: c7c0886ea1a0af126cbb639f65374fade359b03c.
- Expected image SHA256: cbb2331ff00febf39f0332aa7f04b657ba5da30cb7f81cbaa28a636687d3be65.
- The user's hash display was truncated and its visible prefix matched. The
  suggested initial boot command compared the full hash, but the user did
  not supply a complete hash/guard-result transcript. The runtime banner
  identifies the Stage 20 build.
- Build: https://github.com/TeamWearFreedomProject/PixelWatch2-BuildRoot/actions/runs/39363419356
- Artifact: https://github.com/TeamWearFreedomProject/PixelWatch2-BuildRoot/actions/runs/39363419356/artifacts/12239385178

This establishes a first kernel/userspace/USB-shell milestone. It does not
establish a stable watch OS, display, touch, charging, battery management,
validated thermal protection, or a recovery guarantee for future images.
No new image or kernel change is introduced by this evidence commit.

## Windows without additional software

The user's PC cannot install software/drivers and rejects .ps1 execution.
The existing Fastboot driver worked, and the candidate's CDC ACM interface
was recognized as COM5. A PowerShell command block pasted directly into the
interactive console opened System.IO.Ports.SerialPort with DTR/RTS enabled,
sent uname and uptime commands, and read their responses. No execution-policy
change was requested or reported. COM5 is this PC's observation, not a fixed
port number for every PC or future enumeration.

## Remaining KASAN defect

At guest time 7.170585, KASAN reported a use-after-free in __list_add_valid,
with this relevant call chain:

    __list_add_valid -> icc_provider_add -> qnoc_probe
        -> platform_probe -> deferred_probe_work_func

The preceding log includes an interconnect clock error with return -517.
The shell subsequently executed at uptime 9.74 seconds, so this report did
not immediately prevent that command execution. It remains a real memory
safety finding; shell access does not establish runtime stability.

The pinned source has a plausible error-unwind defect in
drivers/interconnect/qcom/monaco.c: qnoc_probe registers its devm-allocated
provider with icc_provider_add, then directly returns if
devm_clk_bulk_get_all fails. The QoS clock-enable failure also returns
without removing the provider. Probe failure can free the devm allocation
while the global interconnect provider list still refers to it, matching
the kind of stale-list access seen on a later probe attempt.

This is a source-backed diagnosis candidate, not a completed causal proof:
the supplied capture contains '[missed 8279 bytes]' and omits the full
allocation/free stack traces. Stage 22 should audit all post-registration
failure paths and balanced clock cleanup, exercise failure/deferred-probe
cases, retain KASAN, then compare a new hardware trace. Do not merely hide
the report or extend the diagnostic session to claim stability.

The candidate also has CONFIG_U_SERIAL_CONSOLE=y and the built-in cmdline
' loglevel=3 console=ttyGS0'. Kernel output and the shell therefore share
the serial connection; the observed interleaving is consistent with this
configuration. A later capture should retain the complete KASAN report.

## References and provenance

- Selected user-capture excerpts: stage21/first-boot-excerpts.txt.
- Structured observation: stage21/hardware-result.json.
- Exact kernel source: https://android.googlesource.com/kernel/msm/+/99c2312e4f131f45993d7f4d741e61d647e7ed10/
- Provider driver: https://android.googlesource.com/kernel/msm/+/99c2312e4f131f45993d7f4d741e61d647e7ed10/drivers/interconnect/qcom/monaco.c
- Provider list implementation: https://android.googlesource.com/kernel/msm/+/99c2312e4f131f45993d7f4d741e61d647e7ed10/drivers/interconnect/core.c
- KASAN report interpretation: https://docs.kernel.org/dev-tools/kasan.html
- PowerShell policy documentation: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies

AsteroidOS boot/init_boot/vendor_kernel_boot/rootfs files were also visible
in the user's screenshot. Their filenames alone do not verify origin,
checksums, compatibility, or hardware behavior. The reported fastboot boot
test supplied boot-stage20.img. The preflight did not dump other partitions,
so their current contents and prior flashing history are not established here.

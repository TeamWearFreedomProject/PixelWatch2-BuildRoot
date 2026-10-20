# Stage 19 — conditional thermal Kbuild routing and final linkage proof

Stage 17 demonstrated a compiled alarm object after unconditionally appending
`qcom/` to the thermal parent Makefile. Stage 18 resolved the PMIC thermal
resources in the user's OEM DT candidates. This stage replaces that temporary
parent rule with a source patch and verifies the final linked kernel.

## Change

`0001-thermal-reach-spmi-alarm.patch` replaces the single TSENS-only directory
gate with one conditional traversal when **TSENS or the SPMI alarm** is `y`
or `m`. The existing child Makefile still selects each driver independently.
There is one directory traversal even if both symbols are enabled, and none
when both are disabled. This is a targeted fix for these two symbols, not a
complete redesign of every Qualcomm thermal driver's parent routing.

The original parent, child, Kconfig and driver hashes must match Stage 18's
immutable EOS source pins before applying the patch. The build uses the same
two BAM/SCM compatibility changes used by Stage 17; their full diff is included
in the diagnostics. The underlying source revision remains
`99c2312e4f131f45993d7f4d741e61d647e7ed10`.

## Evidence required by CI

1. GNU make evaluates the actual patched parent and child Makefiles for all
   nine `n/m/y` combinations. This is routing/tristate expansion coverage;
   it does not claim a real module build for every matrix cell.
2. A full **AArch64 Image + vmlinux** build enables
   `CONFIG_QCOM_SPMI_TEMP_ALARM=y`, while keeping `QCOM_TSENS=n`.
3. `aarch64-linux-gnu-nm` must find the compiled object's driver, probe,
   match table and registration function in the final vmlinux. Exactly one
   corresponding initcall must be linked. The required linked symbols must
   agree in name, type and address with System.map. ELF64/AArch64 object and
   executable types, Image magic and file hashes are checked.
4. A negative control disables only `QCOM_SPMI_TEMP_ALARM` and rebuilds Image
   and vmlinux in the **same output directory**. All alarm symbols must be
   absent from that final kernel despite stale object files possibly remaining.
5. The ON/OFF normalized configs must differ in exactly that one symbol.
   Sound remains disabled. Stage 7's original initramfs and recorded source
   pin are checksum-verified; Stage 17's report and configs are verified too.

Run the local verifier tests with:

```sh
python3 -m unittest discover -s stage19 -p 'test_*.py' -v
```

`stage19/build-linked-kernel.sh` needs the pinned Stage 7 and Stage 17 Actions
inputs, a matching Linux runner checkout path and an AArch64 GCC toolchain.
The workflow performs those preparations and runs the full experiment.

## Outputs and limits

The Actions artifact contains `thermal-link-evidence.json`, individual ON/OFF
reports, configs, the nine-case routing report, source patches, input source
references, checksums and build logs. The raw kernels, vmlinux and object are
temporary build outputs; this stage does not package an Android boot.img or
replace the Stage 7 image. The final scratch output directory contains the
**OFF negative-control build**, not the enabled variant.

Linked registration code proves inclusion in the kernel, not that a device
has probed. Actual PMIC/ADC values, interrupts, battery/charger policy,
firmware-selected overlay, USB console and recovery still need their own
validation. The stored power modules and their no-autoload policy are not
changed. No watch operation occurs in this stage.

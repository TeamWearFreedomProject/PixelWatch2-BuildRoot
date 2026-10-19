# Stage 18 — PMIC temperature-alarm probe and actual OEM DT resources

Stage 17 compiled `qcom-spmi-temp-alarm.o` only after a scratch Kbuild parent
route was added. Stage 18 follows the next dependency: what that driver
expects from the device tree, and what the user's OEM tree declares.

## Findings

The original `vendor_kernel_boot(2).img` and `dtbo(5).img` were recovered
locally and their SHA256 hashes matched Stage 12's TWD9 metadata exactly.
The two base DTBs and eleven overlays produced **22 successful hypothetical
libfdt merges**. All 22 have the same **reduced PMIC thermal resource graph**.
This does not identify the overlay selected on the watch or establish that
all combinations are applicable to its hardware. Other devices in the tree
are outside this equivalence claim.

| Resource | OEM DT declaration, common to the examined candidates |
| --- | --- |
| Sensor | `/soc/qcom,spmi@1c40000/qcom,pm5100@0/qcom,temp-alarm@a00` |
| Compatible / register base | `qcom,spmi-temp-alarm` / `0xa00` |
| Parent | PM5100 `qcom,spmi-pmic`, under `qcom,spmi-pmic-arb` |
| IRQ controller | SPMI arbiter, **not** the root GIC |
| First IRQ cells | `<0 0x0a 0 3>`; this is a DT specifier, not a Linux IRQ number |
| Named IIO channel | `thermal`, ADC5 Gen3 `vadc@8000`, channel argument `3` |
| Thermal zone | `/soc/thermal-zones/pm5100-tz`, sensor ID 0 |
| Declared trips | 95000 m°C `passive`; 115000 / 145000 m°C `critical` |

These are **PMIC die-temperature declarations**, not battery temperature or
charging limits. No trip point is changed. No physical reading is available.

## Exact source contract

`stage18/pins.json` pins the successful Stage 17 report, original/research
config checksums via that report, kernel revision
`99c2312e4f131f45993d7f4d741e61d647e7ed10`, and four upstream source hashes.
The generated report includes reviewed source anchors with line URLs.

The alarm probe requires its parent's regmap, `reg`, IRQ index 0, valid
peripheral type/subtype and thermal sensor registration. It registers sensor
ID 0 and requests a threaded IRQ. Initialization performs PMIC register
writes, so compilation cannot establish runtime behavior.

The named `thermal` IIO channel is **optional to this driver's probe**:
`-EPROBE_DEFER` is returned for retry; other acquisition errors lead to the
non-ADC estimate path. IIO itself remains a Kconfig dependency. The 37000 m°C
default and alarm-stage estimates are not ADC measurements or battery readings.
The OEM graph does declare a named ADC channel, but neither its declaration
nor an enabled ADC config proves that measurements work.

Stage 17 still needed the parent Makefile routing change because the original
thermal Makefile reaches `qcom/` through `CONFIG_QCOM_TSENS`, which is disabled.
Stage 18 records this; it does not change any kernel configuration or image.

## Reproduction and scope

Run the graph and provenance tests:

```sh
python3 -m unittest discover -s stage18 -p 'test_*.py' -v
```

To independently repeat extraction, supply the same **local, private** OEM
images to `stage18/extract_oem.py` with `--vendor-kernel-boot`, `--dtbo`,
`--metadata stage12/twd9-dtb-derived.json`, an installed `fdtoverlay` path via
`--fdtoverlay`, and a separate `--output` JSON path. Wrong firmware hashes
are rejected. Intermediate base and merged trees live in a temporary folder.
The output contains reduced declarations and hashes only. Do not commit the
original images or merged DTBs.

CI downloads the exact Stage 17 evidence, verifies its report and configs,
retrieves four hash-pinned EOS source files, and compares the reviewed probe
contract with the committed **historical local extraction**. CI has no OEM
firmware bytes and does not repeat the firmware extraction. The fixture tests
cover SPMI interrupt-parent inheritance, extended IRQs, optional ADC absence,
provider availability, sensor IDs, malformed FDTs and provenance failures.

Outputs: `thermal-probe-contract.json` and `oem-thermal-graphs.json` in the
Stage 18 Actions artifact. No boot image, module load, charging experiment,
or watch operation is performed. Runtime PMIC/ADC/IRQ behavior, the chosen
overlay, battery/charger policy, USB console and recovery remain unresolved.

The next concrete kernel task is a conditional Kbuild routing fix and linked
symbol verification, followed by the separate battery/charger and USB paths.

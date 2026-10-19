# Stage 13 — inspect actual EOS driver OF match tables, not just Kconfig

**OFFLINE SOURCES ONLY — NEVER FLASH/BOOT THIS RESEARCH IMAGE ON A WATCH.**

Stage 12 compared user-derived Aurora TWD9 OEM base-FDT/11-DTBO compatible
strings with Stage 7 kernel configuration and observed QBG disabled in both
base FDTs. That was not a source-level driver binding test.

## Evidence and source provenance

This stage fetches exactly the kernel/msm, Google BMS and Google SOC/MSM
source SHAs recorded inside the passing Stage 7 Actions artifact from run
38721433935. Git checkout SHA is checked before scanning. The 16 targets
are the 12 base-FDT compatibles and four overlay battery/charger/extcon
compatibles recorded in stage12/twd9-dtb-derived.json.

The C scan looks for string literals in explicit struct of_device_id
match tables, and separately reports other source string literals.
When an exact table match is found it records the source file, table
name, line number and SHA256. It conservatively looks for a matching
same-directory Kbuild object rule under a CONFIG key and inspects that
CONFIG value in Stage 7's actual kernel.config.

**The scanner is conservative, not a full C parser or build graph.**
Macros, generated code, nested Kbuild objects and indirect module
linking may escape it. Unresolved or mismatched compatible strings
must be investigated; they are not necessarily proof of a broken driver.

This does not compile/boot a new image and does not insert any module.
It does not download OEM firmware binaries or upload the user's OEM data
or serial number to Actions. Stage 12 derived metadata alone is used.

## Meaning of report fields

- OF_TABLE_MATCH_DIRECT_Y_RULE: exact compatible occurs in a source
  of_device_id table and a direct same-directory Kbuild object rule has
  matching CONFIG=y. This is *stronger build evidence*, not proof the
  driver probes and not necessarily proof the rule was ultimately linked.
- OF_TABLE_MATCH_DIRECT_M_RULE: analogous direct evidence with CONFIG=m.
- OF_TABLE_MATCH_BUILD_LINK_UNKNOWN: compatible is present in an OF
  match table, but code-to-config linkage needs further review.
- LITERAL_ONLY_NO_OF_MATCH: found only as a non-matching C string literal,
  **not** reliable DTB driver support.
- NO_SOURCE_OF_MATCH_FOUND: no literal found among examined C sources.
  The exact string could be in a different external module or be
  generated from macros. Do not infer physical missing hardware support.

The output records all provenance and warns that the selected DTBO,
merged FDT, charger safeguards, watchdog, thermal sensors and USB
PHY/UDC behavior are still NOT verified at runtime.

## Engineering constraints

1. Stage 7 stores eight external PMIC/BMS .ko files but does NOT
   autoload them. Even a direct OF table match is not a functional charger.
2. The OEM base FDT marks qcom,qbg disabled; actual overlay selection
   remains unknown.
3. Sound is disabled in the research kernel, and GKI sound config
   warnings are not resolved.
4. CDC ACM in Kconfig is not proof the real charging connector enumerates.
5. Actual recovery and battery/thermal protections have not been
   established, so physical_fastboot_boot_authorization stays BLOCKED.

## How to reproduce (no physical watch)

Use GitHub Actions Stage 13 on the branch. It verifies the pinned Stage 7
source hashes, runs synthetic tests, fetches source-only public trees,
scans OF tables and uploads a JSON report. No watch operations occur.

The next step, after examining source matches, is to review relevant
Kbuild objects, boot-time initialization ordering and compatible
strings in the effective merged OEM overlay, without modifying device
partitions or bypassing any safety controls.

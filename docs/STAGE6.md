# Stage 6: source-level Google battery / Qualcomm power module recovery

**Research-only build; DO NOT LOAD, BOOT, OR FLASH on a Pixel Watch 2.**

The Stage 5 image compiled with CONFIG_SOUND=n and a USB serial getty
but explicitly disabled QCOM_POWER_SUPPLY, QPNP_SMBLITE and QTI_QBG
because misc/gvotable.h is supplied by a separate Google vendor module
tree. Compiling without the charger driver does not mean the watch has
valid charge protection or battery telemetry.

This stage attempts to build the missing Google power stack against
the SAME pinned kernel commit and configuration as the successful
Stage 5 research image from Actions run 38564131552.

Build dependency order:
1. Google BMS misc (gvotable and logbuffer)
2. Google BMS (battery / charger / sw5100)
3. External Qualcomm power supply (qpnp-smblite and qbg)

The selected BMS commit is 51583026f264e7597808a16aa6809fb9279eb8c4.
The soc/msm companion commit is 7a2cd1649e49373ca24bd81d4fe89e7440db4ab5.
Both are references from the AsteroidOS Aurora module recipe.
Each stage consumes Module.symvers from prior stages.

CI verifies Stage 5 artifact SHA256SUMS, checks the exact original kernel
commit, compiles the kernel Image to produce Module.symvers and then
attempts external modules in order. Compiler errors are preserved
in stage6-build.log and do not get ignored or disguised as success.

This is a GCC-based build experiment; Google stock modules and some
AsteroidOS builds use clang. The complete vendor module tree, all symbol
versions, firmware, USB/SCM hardware protocol, battery charging safeguards
and thermal protections are unverified. Even a successful build proves
only that compiler dependencies are satisfied, NOT safe real-world use.

Stage 6 does not alter Stage 5 image, does not install any .ko, and
does not access hardware. Future work needs a compatible module ABI,
boot/device-tree verification, reliable debug console, and careful
power/thermal safety review before considering ANY hardware trial.

Reference: https://github.com/AsteroidOS/meta-smartwatch/blob/master/meta-aurora/recipes-kernel/linux/linux-aurora-modules_5.15.144.bb

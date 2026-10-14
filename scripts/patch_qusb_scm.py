#!/usr/bin/env python3
"""CI-only experimental implementation of a missing QUSB2PHY SCM helper.

Source: Qualcomm-authored Linux proposal by Hiren Gohel, 2022-09-15:
https://lists.openwall.net/linux-kernel/2022/09/15/779

Hardware behavior, platform SCM availability and boot safety are NOT verified.
Fail closed if the source layout differs. Never deploy generated images to a
real device on the strength of this compiler-only workaround.
"""
from pathlib import Path
import sys

FUNCTION = """void qcom_scm_phy_update_scm_level_shifter(u32 val)
{
	int ret;
	struct qcom_scm_desc desc = {
		.svc = QCOM_SCM_SVC_BOOT,
		.cmd = QCOM_SCM_QUSB2PHY_LVL_SHIFTER_CMD_ID,
		.owner = ARM_SMCCC_OWNER_SIP
	};

	desc.args[0] = val;
	desc.args[1] = 0;
	desc.arginfo = QCOM_SCM_ARGS(2);

	ret = qcom_scm_call(__scm->dev, &desc, NULL);
	if (ret)
		pr_err("Failed to update scm level shifter=0x%x\\n", ret);
}
EXPORT_SYMBOL(qcom_scm_phy_update_scm_level_shifter);

"""

def replace_exact(src: str, anchor: str, new: str, file: Path) -> str:
    if src.count(anchor) != 1:
        raise ValueError(f"Expected exactly one anchor in {file}: {anchor!r}, got {src.count(anchor)}")
    return src.replace(anchor, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: patch_qusb_scm.py PATH_TO_KERNEL_SOURCE")
    kernel = Path(sys.argv[1])
    phy = kernel / "drivers/usb/phy/phy-msm-qusb.c"
    scm = kernel / "drivers/firmware/qcom_scm.c"
    private = kernel / "drivers/firmware/qcom_scm.h"
    public = kernel / "include/linux/qcom_scm.h"

    phytxt = phy.read_text()
    call = "qcom_scm_phy_update_scm_level_shifter("
    if call not in phytxt:
        sys.exit("Unexpected QUSB PHY source: missing SCM call")

    scmtext = scm.read_text()
    if "void qcom_scm_phy_update_scm_level_shifter(" not in scmtext:
        if "qcom_scm_call(__scm->dev," not in scmtext:
            sys.exit("Unexpected SCM API; refusing to insert unreviewed function")
        scmtext = replace_exact(
            scmtext, "EXPORT_SYMBOL(qcom_scm_set_remote_state);",
            "EXPORT_SYMBOL(qcom_scm_set_remote_state);\n\n" + FUNCTION.rstrip(), scm,
        )

    private_txt = private.read_text()
    macro = "QCOM_SCM_QUSB2PHY_LVL_SHIFTER_CMD_ID"
    if macro not in private_txt:
        private_txt = replace_exact(
            private_txt, "#define QCOM_SCM_FLUSH_FLAG_MASK\t0x3",
            "#define QCOM_SCM_FLUSH_FLAG_MASK\t0x3\n"
            "#define QCOM_SCM_QUSB2PHY_LVL_SHIFTER_CMD_ID\t0x1B", private,
        )

    public_txt = public.read_text()
    if "void qcom_scm_phy_update_scm_level_shifter(" not in public_txt:
        if not public_txt.rstrip().endswith("#endif"):
            sys.exit("Unexpected public SCM header ending")
        pos = public_txt.rfind("#endif")
        public_txt = public_txt[:pos] + (
            "extern void qcom_scm_phy_update_scm_level_shifter(u32 val);\n\n"
        ) + public_txt[pos:]

    # Write only after ALL source-shape checks pass.
    scm.write_text(scmtext)
    private.write_text(private_txt)
    public.write_text(public_txt)
    print("Applied CI-only experimental QUSB SCM helper from 2022 proposal")


if __name__ == "__main__":
    main()

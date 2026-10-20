#!/usr/bin/env python3
"""Evaluate the actual parent/child Kbuild text using GNU make, not regex."""
import argparse
import itertools
import json
from pathlib import Path
import subprocess


def evaluate(parent, child, tsens, alarm):
    values = {"n": "", "m": "m", "y": "y"}
    text = ("CONFIG_QCOM_TSENS := " + values[tsens] + "\n"
            "CONFIG_QCOM_SPMI_TEMP_ALARM := " + values[alarm] + "\n" + parent + "\n"
            "parent_y := $(obj-y)\nparent_m := $(obj-m)\n"
            "obj-y :=\nobj-m :=\n" + child + "\n"
            ".PHONY: stage19_matrix\nstage19_matrix:\n"
            "\t@printf '%s\\n' 'parent_y:$(parent_y)' 'parent_m:$(parent_m)' 'child_y:$(obj-y)' 'child_m:$(obj-m)'\n")
    output = subprocess.check_output(["make", "--no-print-directory", "-rR", "-f", "-", "stage19_matrix"],
                                     input=text, text=True, timeout=15)
    result = dict((k, v.split()) for k, v in (line.split(":", 1) for line in output.splitlines()))
    count = sum(result[k].count("qcom/") for k in ("parent_y", "parent_m"))
    expected = int(tsens != "n" or alarm != "n")
    if count != expected:
        raise ValueError(f"Parent traversal count {count}, expected {expected}: TSENS={tsens}, ALARM={alarm}")
    obj = "qcom-spmi-temp-alarm.o"
    if result["child_y"].count(obj) != int(alarm == "y") or result["child_m"].count(obj) != int(alarm == "m"):
        raise ValueError("Child does not independently respect alarm tristate")
    return {"tsens": tsens, "alarm": alarm, "qcom_traversals": count,
            "parent_y": result["parent_y"], "parent_m": result["parent_m"],
            "child_alarm_y": result["child_y"].count(obj), "child_alarm_m": result["child_m"].count(obj)}


def matrix(parent, child):
    return [evaluate(parent, child, a, b) for a, b in itertools.product(("n", "m", "y"), repeat=2)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kernel-source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    r = matrix((a.kernel_source / "drivers/thermal/Makefile").read_text(),
               (a.kernel_source / "drivers/thermal/qcom/Makefile").read_text())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps({"method": "GNU_make_expansion_only", "cases": r}, indent=2) + "\n")
    print("STAGE19_KBUILD_TRISTATE_MATRIX_PASS", len(r))


if __name__ == "__main__":
    main()

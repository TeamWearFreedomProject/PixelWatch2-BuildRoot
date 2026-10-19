#!/usr/bin/env python3
"""Stage 14: conservative Kbuild object trace for Stage 13 OF-table hits.

Never confuses a source-compatible entry, CONFIG, or external .ko with a
runtime-probed device. No commands on any watch or power hardware.
"""
import argparse
import json
import pathlib
import re

OBJ = re.compile(r"^\s*obj-(?:\$\((CONFIG_[A-Za-z0-9_]+)\)|([ym]))\s*[:+]?=\s*(.*?)\s*$")
COMPOSITE = re.compile(r"^\s*([A-Za-z0-9_.-]+)-(?:y|objs|\$\((CONFIG_[A-Za-z0-9_]+)\))\s*[:+]?=\s*(.*?)\s*$")
TOKEN = re.compile(r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_.-]+\.o)(?![A-Za-z0-9_./-])")


def rules(directory):
    output = []
    for file in (directory / "Makefile", directory / "Kbuild"):
        if not file.is_file():
            continue
        content = file.read_text(errors="replace").replace("\\\n", " ")
        for lineno, line in enumerate(content.splitlines(), 1):
            m = OBJ.match(line)
            if m:
                output.append(("obj", m.group(1), m.group(2), None,
                               TOKEN.findall(m.group(3)), str(file), lineno))
                continue
            m = COMPOSITE.match(line)
            if m:
                output.append(("composite", m.group(2), None, m.group(1),
                               TOKEN.findall(m.group(3)), str(file), lineno))
    return output


def trace_file(file, root, config):
    directory = file.parent
    source_obj = file.stem + ".o"
    items = rules(directory)
    queue = [(source_obj, [])]
    found = []
    visited = set()
    while queue:
        obj, via = queue.pop(0)
        if obj in visited:
            continue
        visited.add(obj)
        for kind, conf, unconditional, name, members, filename, line in items:
            record = {"kind":kind, "rule_file":str(pathlib.Path(filename).relative_to(root.resolve())),
                      "line":line, "object":obj}
            if kind == "obj" and obj in members:
                ckey = (conf or "")
                value = config.get(ckey.removeprefix("CONFIG_"),
                                   "not in config") if conf else unconditional
                found.append({"evidence":"same-directory obj rule",
                              "config":ckey or "unconditional",
                              "value":value, "steps":via+[record]})
            if kind == "composite" and obj in members:
                parent = name+".o"
                if parent != obj:
                    queue.append((parent, via+[record]))
    statuses = {x["value"] for x in found}
    label = ("POSSIBLE_BUILTIN_LINK" if "y" in statuses
             else "POSSIBLE_MODULE_LINK" if "m" in statuses
             else "DISABLED_OR_NONLINKED_RULE" if found
             else "BUILD_GRAPH_UNRESOLVED")
    return {"source":str(file.relative_to(root.resolve())), "object":source_obj,
            "build_evidence":label, "traces":found,
            "limitation":"Only local Makefile/Kbuild links are traced. Ancestor directory gates, generated objects and external M= builds may differ."}


def audit(stage13, config, source_dirs):
    if stage13.get("stage") != 13 or stage13.get("static_scan_completed") is not True:
        raise ValueError("Stage 13 input does not contain a completed scan")
    if stage13.get("physical_fastboot_boot_authorization") != "BLOCKED":
        raise ValueError("Stage 13 incorrectly approved physical boot")
    target = []
    for entry in stage13["nodes"]:
        matches = []
        for candidate in entry["candidate_hits"]:
            label = candidate["source_repository"]
            if label not in source_dirs:
                raise ValueError("No sources for "+label)
            root = source_dirs[label]
            path = (root/candidate["source"]).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                raise ValueError("Unsafe or missing matched source: "+str(path))
            evidence = trace_file(path,root,config)
            evidence["source_repo"]=label
            evidence["of_table"]=candidate["table"]
            matches.append(evidence)
        target.append({"compatible":entry["compatible"], "category":entry["category"],
                       "stock_base_status":entry["stock_base_status"],
                       "match_source_count":len(matches), "build_paths":matches,
                       "runtime_driver_probe":"UNTESTED"})
    focus = {x["compatible"]:x for x in target}
    checks = {}
    for name in ("qcom,qpnp-pm5100-smblite", "qcom,qbg",
                 "qcom,spmi-temp-alarm", "qcom,dwc-usb3-msm",
                 "snps,dwc3", "qcom,usb-hsphy-snps-femto"):
        x = focus[name]
        checks[name] = {
            "OF_table_found": x["match_source_count"] > 0,
            "possible_built_in": any(p["build_evidence"]=="POSSIBLE_BUILTIN_LINK" for p in x["build_paths"]),
            "possible_module": any(p["build_evidence"]=="POSSIBLE_MODULE_LINK" for p in x["build_paths"]),
            "source_or_link_unknown": not any(p["build_evidence"] in
                ("POSSIBLE_BUILTIN_LINK","POSSIBLE_MODULE_LINK") for p in x["build_paths"]),
        }
    safety = {
        "CONFIG_SOUND":config.get("SOUND","unknown"),
        "CONFIG_QCOM_SPMI_TEMP_ALARM":config.get("QCOM_SPMI_TEMP_ALARM","unknown"),
        "CONFIG_QCOM_POWER_SUPPLY":config.get("QCOM_POWER_SUPPLY","unknown"),
        "CONFIG_USB_DWC3":config.get("USB_DWC3","unknown"),
        "CONFIG_USB_DWC3_MSM":config.get("USB_DWC3_MSM","unknown"),
        "CONFIG_USB_GADGET":config.get("USB_GADGET","unknown"),
        "CONFIG_USB_CONFIGFS_ACM":config.get("USB_CONFIGFS_ACM","unknown"),
    }
    if safety["CONFIG_SOUND"]!="n":
        raise ValueError("Research kernel audio state unexpectedly changed")
    return {"stage":14,"static_kbuild_tracing":"COMPLETED",
            "stage13_commit_sources":stage13["source_revisions"],
            "source_tables_examined":len(target),
            "critical_checks":checks,
            "kconfig_safety_relevant":safety,
            "all_compatible_traces":target,
            "blocking_risks":[
                "External charger/gauge power modules exist only as non-autoloaded files in Stage 7 initramfs",
                "Stage 7 QCOM SPMI thermal alarm and other protections have not been functionally validated",
                "Source-level match, Kbuild presence and module ABI do not prove DT overlay selection or runtime probe",
                "No active battery-monitor, safe shutdown, USB serial or recovery demonstrated on physical watch",
            ],
            "hardware_tested":False,
            "fastboot_boot_authorized":False,
            "physical_fastboot_boot_authorization":"BLOCKED"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--stage13-report",type=pathlib.Path,required=True)
    p.add_argument("--kernel-config",type=pathlib.Path,required=True)
    p.add_argument("--kernel-source",type=pathlib.Path,required=True)
    p.add_argument("--bms-source",type=pathlib.Path,required=True)
    p.add_argument("--soc-source",type=pathlib.Path,required=True)
    p.add_argument("--output",type=pathlib.Path,required=True)
    a=p.parse_args()
    from sys import path
    path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"stage13"))
    from audit_of_matches import parse_config
    source_dirs={"kernel":a.kernel_source,"bms":a.bms_source,"soc":a.soc_source}
    data=json.loads(a.stage13_report.read_text())
    result=audit(data,parse_config(a.kernel_config.read_text()),source_dirs)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    for key,value in result["critical_checks"].items():
        print(key, json.dumps(value))
    print("STAGE14_KBUILD_SOURCE_AUDIT_COMPLETE; PHYSICAL BOOT BLOCKED")


if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""Audit an AArch64 kernel *object*, not a bootable system."""
import argparse
import hashlib
import json
import pathlib
import struct
import subprocess

def parse_config(path):
    config = {}
    for line in path.read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            k, v = line.split("=", 1)
            config[k.removeprefix("CONFIG_")] = v
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            config[line[len("# CONFIG_"):-len(" is not set")]] = "n"
    return config

def compare(baseline, variant):
    base, candidate = parse_config(baseline), parse_config(variant)
    changes = {name:{"stage7":base.get(name,"missing"),
                     "research_variant":candidate.get(name,"missing")}
               for name in sorted(set(base)|set(candidate))
               if base.get(name)!=candidate.get(name)}
    for required in ("ARM64", "THERMAL", "SPMI", "REGMAP_SPMI"):
        if base.get(required)!="y" or candidate.get(required)!="y":
            raise ValueError("Expected unchanged kernel prerequisite CONFIG_"+required)
    if base.get("QCOM_SPMI_TEMP_ALARM")!="n" or candidate.get("QCOM_SPMI_TEMP_ALARM")!="y":
        raise ValueError("Target thermal config was not changed n->y")
    for keep in ("SOUND","TRIM_UNUSED_KSYMS","QCOM_POWER_SUPPLY"):
        if base.get(keep)!=candidate.get(keep):
            raise ValueError("Unintended change to "+keep)
    return changes

def report(baseline, variant, obj, source, kernel_image):
    difference=compare(baseline,variant)
    kernel=kernel_image.read_bytes()
    if len(kernel)<64 or struct.unpack_from("<I",kernel,56)[0]!=0x644D5241:
        raise ValueError("Build did not produce a real ARM64 kernel Image")
    data=obj.read_bytes()
    if not (len(data)>64 and data[:6]==b"\x7fELF\x02\x01"):
        raise ValueError("Compiled object is not ELF64 little-endian")
    if struct.unpack_from("<H",data,18)[0]!=183:
        raise ValueError("Not compiled for AArch64")
    if struct.unpack_from("<H",data,16)[0]!=1:
        raise ValueError("Not a relocatable kernel object")
    rev=subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip()
    if len(rev)!=40:
        raise ValueError("Invalid kernel source revision")
    return {
        "stage":17, "scope":"OFFLINE_AARCH64_SINGLE_THERMAL_DRIVER_OBJECT",
        "source_git_revision":rev, "object_source":"drivers/thermal/qcom/qcom-spmi-temp-alarm.c",
        "object_elf_architecture":"ELF64-little-endian-AArch64",
        "object_bytes":len(data), "object_sha256":hashlib.sha256(data).hexdigest(),
        "baseline_config_sha256":hashlib.sha256(baseline.read_bytes()).hexdigest(),
        "research_config_sha256":hashlib.sha256(variant.read_bytes()).hexdigest(),
        "changed_config_symbols":difference,
        "thermal_alarm_kconfig_baseline":"n",
        "thermal_alarm_kconfig_research_variant":"y",
        "compile_object_verified":True,
        "research_kernel_image_created":True,
        "research_kernel_image_bytes":len(kernel),
        "research_kernel_image_sha256":hashlib.sha256(kernel).hexdigest(),
        "kernel_image_not_uploaded":True,
        "research_boot_image_created":False,
        "module_protection_or_thermal_runtime_proven":False,
        "charging_safe_on_hardware":"NOT_TESTED",
        "device_tree_driver_probe":"NOT_TESTED",
        "watch_used":False,
        "physical_fastboot_boot_authorization":"BLOCKED",
        "note":"An offline compiled PMIC temperature alarm object does not prove real-world thermal limits, IRQ wiring or charger safety."
    }

def main():
    p=argparse.ArgumentParser()
    for arg in ("baseline","variant","object","kernel-source","kernel-image","output"):
        p.add_argument("--"+arg,type=pathlib.Path,required=True)
    a=p.parse_args()
    output=report(a.baseline,a.variant,a.object,a.kernel_source,a.kernel_image)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(output,indent=2)+"\n")
    print("STAGE17_AARCH64_THERMAL_OBJECT_COMPILED")
    for name,oldnew in output["changed_config_symbols"].items():
        print("CONFIG_CHANGE",name,oldnew)
    print("PHYSICAL_BOOT: BLOCKED")

if __name__=="__main__":
    main()

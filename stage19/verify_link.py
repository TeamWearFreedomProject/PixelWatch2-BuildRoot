#!/usr/bin/env python3
"""Prove the PMIC alarm is in final AArch64 vmlinux, with an OFF control."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage17.report_compile import parse_config

REQUIRED = ("qpnp_tm_probe", "qpnp_tm_driver", "qpnp_tm_driver_init", "qpnp_tm_match_table")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check_elf(path, expected_type):
    with path.open("rb") as f:
        data = f.read(64)
    if len(data) != 64 or data[:6] != b"\x7fELF\x02\x01":
        raise ValueError("Expected ELF64 little endian: " + str(path))
    if struct.unpack_from("<HH", data, 16) != (expected_type, 183):
        raise ValueError("Wrong ELF type/architecture: " + str(path))


def parse_nm(text):
    result = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        name, kind, address = fields[:3]
        if name.startswith("qpnp_tm_") or (name.startswith("__initcall") and "qpnp_tm_driver_init" in name):
            if name in result:
                raise ValueError("Duplicate relevant symbol: " + name)
            result[name] = {"type": kind, "address": int(address, 16)}
    return result


def parse_map(text):
    # System.map uses address, type, name; nm --format=posix uses name first.
    return parse_nm("\n".join(" ".join((p[2], p[1], p[0]))
                              for p in (line.split() for line in text.splitlines()) if len(p) == 3))


def check_symbols(symbols, system_map, mode, object_symbols=None):
    if mode == "off":
        if symbols or system_map:
            raise ValueError("Alarm symbols unexpectedly remain in OFF control")
        return []
    for name in REQUIRED:
        if name not in symbols or symbols[name]["type"].lower() not in ("t", "d", "r"):
            raise ValueError("Missing/nondefined linked alarm symbol: " + name)
        if object_symbols is None or name not in object_symbols:
            raise ValueError("Linked symbol not found in compiled alarm object: " + name)
    registrations = [s for s in symbols if s.startswith("__initcall") and "qpnp_tm_driver_init" in s]
    if len(registrations) != 1:
        raise ValueError("Expected exactly one linked alarm initcall")
    for name in (*REQUIRED, *registrations):
        if name not in system_map or system_map[name] != symbols[name]:
            raise ValueError("System.map disagrees with vmlinux: " + name)
        if symbols[name]["address"] == 0:
            raise ValueError("Unexpected zero-address linked symbol")
    return registrations


def report(out, mode, nm):
    config = parse_config(out / ".config")
    expected_alarm = "y" if mode == "on" else "n"
    for key, expected in {"ARM64": "y", "THERMAL": "y", "SPMI": "y", "IIO": "y", "REGMAP_SPMI": "y",
                          "QCOM_TSENS": "n", "QCOM_SPMI_TEMP_ALARM": expected_alarm, "SOUND": "n", "LTO_NONE": "y"}.items():
        if config.get(key) != expected:
            raise ValueError("Unexpected config " + key)
    vmlinux = out / "vmlinux"
    # arm64's CONFIG_RELOCATABLE links with -shared -Bsymbolic: ET_DYN,
    # even though this is the final kernel, not a loadable kernel module.
    elf_type = 3 if config.get("RELOCATABLE") == "y" else 2
    check_elf(vmlinux, elf_type)
    symbols = parse_nm(subprocess.check_output([nm, "--defined-only", "--format=posix", str(vmlinux)], text=True))
    system_map = parse_map((out / "System.map").read_text())
    image = out / "arch/arm64/boot/Image"
    with image.open("rb") as f:
        header = f.read(64)
    if len(header) != 64 or header[56:60] != b"ARM\x64":
        raise ValueError("Missing ARM64 Image magic")
    object_symbols, obj = None, None
    if mode == "on":
        obj = out / "drivers/thermal/qcom/qcom-spmi-temp-alarm.o"
        check_elf(obj, 1)
        object_symbols = parse_nm(subprocess.check_output([nm, "--defined-only", "--format=posix", str(obj)], text=True))
    registrations = check_symbols(symbols, system_map, mode, object_symbols)
    return {"stage": 19, "mode": mode, "architecture": "AArch64", "alarm_config": expected_alarm,
            "vmlinux_elf_type": "ET_DYN" if elf_type == 3 else "ET_EXEC",
            "vmlinux_sha256": digest(vmlinux), "image_sha256": digest(image),
            "image_bytes": image.stat().st_size, "config_sha256": digest(out / ".config"),
            "system_map_sha256": digest(out / "System.map"), "object_sha256": digest(obj) if obj else None,
            "relevant_linked_symbols": symbols, "linked_initcalls": registrations,
            "proof": "DRIVER_AND_INITCALL_LINKED" if mode == "on" else "NO_ALARM_SYMBOLS_IN_LINKED_KERNEL",
            "boot_image_created": False, "runtime_probe": "NOT_TESTED"}


def summarize(folder):
    on = json.loads((folder / "link-on.json").read_text())
    off = json.loads((folder / "link-off.json").read_text())
    base, variant = parse_config(folder / "control-off.config"), parse_config(folder / "linked-on.config")
    changes = {s: {"off": base.get(s), "on": variant.get(s)} for s in set(base) | set(variant)
               if base.get(s) != variant.get(s)}
    if changes != {"QCOM_SPMI_TEMP_ALARM": {"off": "n", "on": "y"}}:
        raise ValueError("ON/OFF config differs beyond the one alarm symbol")
    if on["proof"] != "DRIVER_AND_INITCALL_LINKED" or off["proof"] != "NO_ALARM_SYMBOLS_IN_LINKED_KERNEL":
        raise ValueError("Missing positive/negative linkage evidence")
    if on["vmlinux_sha256"] == off["vmlinux_sha256"]:
        raise ValueError("ON/OFF vmlinux unexpectedly identical")
    return {"stage": 19, "positive_link_proof": True, "negative_control_pass": True,
            "changed_config_symbols": changes, "on": on, "off": off,
            "physical_fastboot_boot_authorization": "BLOCKED",
            "runtime_probe": "NOT_TESTED", "stage7_image_changed": False, "module_autoload_changed": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path)
    p.add_argument("--mode", choices=("on", "off"))
    p.add_argument("--nm", default="aarch64-linux-gnu-nm")
    p.add_argument("--summary-dir", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.summary_dir:
        r = summarize(a.summary_dir)
    else:
        if a.out is None or a.mode is None:
            p.error("--out and --mode are required without --summary-dir")
        r = report(a.out, a.mode, a.nm)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(r, indent=2, sort_keys=True) + "\n")
    print("STAGE19", r.get("proof", "POSITIVE_AND_NEGATIVE_LINK_CONTROLS_PASS"))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Local-only extraction from the user's hash-matched TWD9 images.

Publishes a reduced thermal graph, never the firmware or merged DTBs.
Every base/overlay pair is a hypothetical candidate, not bootloader selection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage9.inspect_stock import align, parse_dtbo, parse_vendor_boot
from stage18.thermal_graph import graph


def extract(vendor, dtbo, metadata, overlay_tool):
    expected = metadata["provenance"]
    for label, data in (("vendor_kernel_boot", vendor), ("dtbo", dtbo)):
        if hashlib.sha256(data).hexdigest() != expected[label + "_sha256"]:
            raise ValueError("OEM input does not match Stage 12: " + label)
    v, d = parse_vendor_boot(vendor), parse_dtbo(dtbo)
    hdr_size = struct.unpack_from("<I", vendor, 2096)[0]
    start = align(hdr_size, v["page_size"]) + align(v["vendor_ramdisk_bytes"], v["page_size"])
    pos, graphs, bases, variants = start, {}, [], []

    def remember(data):
        g = graph(data)
        graphs[g["dtb_sha256"]] = g
        return g["dtb_sha256"]

    with tempfile.TemporaryDirectory(prefix="aurora-thermal-") as directory:
        work = Path(directory)
        for i, base in enumerate(v["dtbs"]):
            raw = vendor[pos:pos + base["bytes"]]
            pos += base["bytes"]
            base_path = work / "base.dtb"
            base_path.write_bytes(raw)
            bases.append({"index": i, "graph_sha256": remember(raw)})
            for j, overlay in enumerate(d["entries"]):
                overlay_path, merged = work / "overlay.dtbo", work / "merged.dtb"
                overlay_path.write_bytes(dtbo[overlay["offset"]:overlay["offset"] + overlay["size"]])
                run = subprocess.run([str(overlay_tool), "-i", str(base_path), "-o", str(merged), str(overlay_path)],
                                     capture_output=True, text=True, timeout=30)
                record = {"base_index": i, "overlay_index": j,
                          "board_id": hex(overlay["board_id"]), "revision": hex(overlay["revision"]),
                          "selected_on_watch": "UNKNOWN"}
                if run.returncode:
                    record.update({"merge": "FAILED", "diagnostic": run.stderr.strip()[:500]})
                else:
                    record.update({"merge": "SUCCEEDED_OFFLINE", "graph_sha256": remember(merged.read_bytes())})
                variants.append(record)
    return {"stage": 18, "method": "local_hash_verified_OEM_extraction_and_libfdt_overlay_application",
            "input_sha256": {"vendor_kernel_boot": v["sha256"], "dtbo": d["sha256"]},
            "overlay_tool_version": subprocess.check_output([str(overlay_tool), "-V"], text=True).strip(),
            "base_dtbs": bases, "candidate_combinations": variants, "graphs": graphs,
            "selected_overlay": "UNKNOWN", "firmware_binaries_published": False,
            "physical_fastboot_boot_authorization": "BLOCKED"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("vendor-kernel-boot", "dtbo", "metadata", "fdtoverlay", "output"):
        p.add_argument("--" + arg, type=Path, required=True)
    a = p.parse_args()
    report = extract(a.vendor_kernel_boot.read_bytes(), a.dtbo.read_bytes(),
                     json.loads(a.metadata.read_text()), a.fdtoverlay.resolve())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n")
    print("Base DTBs:", len(report["base_dtbs"]), "candidate pairs:", len(report["candidate_combinations"]))
    print("Offline merges:", sum(x["merge"] == "SUCCEEDED_OFFLINE" for x in report["candidate_combinations"]))


if __name__ == "__main__":
    main()

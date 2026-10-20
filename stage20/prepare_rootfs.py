#!/usr/bin/env python3
"""Derive a dedicated diagnostic initramfs from the pinned Stage 7 archive."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import stat
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage7.pack_modules import read_records, encode, fresh, add


def prepare(data, overlay, helper):
    if len(helper) < 52 or helper[:6] != b"\x7fELF\x01\x01" or struct.unpack_from("<HH", helper, 16) != (2, 40):
        raise ValueError("Recovery helper must be a static ARM32 ET_EXEC binary")
    original = read_records(gzip.decompress(data))
    paths = [r[2].removeprefix("./") for r in original]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate input initramfs path")
    replacements = {str(p.relative_to(overlay)): p.read_bytes() for p in overlay.rglob("*") if p.is_file()}
    replacements["usr/sbin/aurora-return"] = helper
    removed, records = [], []
    for record in original:
        name = record[2].removeprefix("./")
        discard = (name in replacements or name in ("etc/inittab", "etc/fstab", "usr/bin/adbd", "usr/sbin/aurora-acm", "etc/aurora/dev-acm-enabled")
                   or name.startswith(("lib/modules/", "usr/lib/modules/", "etc/init.d/")) or name.endswith(".ko"))
        if discard:
            removed.append(name)
        else:
            records.append((record[0], record[1], name, record[3]))
    registry = {r[2]: r for r in records}
    ino = max(r[1][0] for r in original)
    for name, body in sorted(replacements.items()):
        ino = add(records, registry, name, body, stat.S_IFREG | 0o755, ino)
    blob = b"".join(encode(r) for r in records) + encode(fresh("TRAILER!!!", b"", 0, ino + 1))
    check = {r[2]: r[3] for r in read_records(blob)}
    for name, body in replacements.items():
        if check[name] != body:
            raise ValueError("Replacement changed: " + name)
    if any(name.endswith(".ko") or "/modules/" in name for name in check):
        raise ValueError("Old ABI module remains in diagnostic rootfs")
    if any(name in check for name in ("etc/inittab", "etc/fstab", "usr/bin/adbd")):
        raise ValueError("Generic startup/ADB unexpectedly retained")
    result = gzip.compress(blob, mtime=0)
    return result, {"stage": 20, "input_rootfs_sha256": hashlib.sha256(data).hexdigest(),
                    "rootfs_sha256": hashlib.sha256(result).hexdigest(), "rootfs_bytes": len(result),
                    "dedicated_pid1": True, "old_ko_removed": sum(x.endswith(".ko") for x in removed),
                    "retained_ko_count": 0, "generic_rc_startup": False,
                    "software_deadline_seconds": 90, "hardware_watchdog": False,
                    "runtime_on_watch": "NOT_TESTED", "overlay_files": sorted(replacements)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("input", "overlay", "helper", "output", "report"):
        p.add_argument("--" + arg, type=Path, required=True)
    a = p.parse_args()
    data, report = prepare(a.input.read_bytes(), a.overlay, a.helper.read_bytes())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(data)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

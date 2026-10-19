#!/usr/bin/env python3
"""Stage 13: source-level OF match-table evidence for OEM DT compatibles.

Read-only comparison. A literal in C source, an of_device_id match, or a
Kconfig=y is NOT a guarantee that the driver probes on a real Pixel Watch 2.
"""
import argparse
import hashlib
import json
import pathlib
import re

TABLE_RE = re.compile(
    r"\bstruct\s+of_device_id\s+([A-Za-z_]\w*)\s*\[[^\]]*\]\s*=\s*\{(.*?)\n\s*\};",
    re.DOTALL,
)
COMPAT_RE = re.compile(r'\.\s*compatible\s*=\s*"([^"]{1,200})"')
LITERAL_RE = re.compile(r'"([^"\n]{1,200})"')
RULE_RE = re.compile(r"^\s*obj-\$\(CONFIG_([A-Z0-9_]+)\)\s*[+:]?=\s*(.*)$")
SUBRULE_RE = re.compile(r"^\s*([A-Za-z0-9_-]+)-(?:y|objs|\$\(CONFIG_[A-Z0-9_]+\))\s*[+:]?=\s*(.*)$")

def strip_comments(text):
    # Preserve quoted literals, but remove all C comments before matching.
    regex = re.compile(r'("(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*)',re.S)
    return regex.sub(lambda m: "" if m.group(0).startswith(("/",)) else m.group(0), text)

def lookup_makefiles(source_file, root, config):
    """Conservative direct obj-Kconfig to basename.o correlation only."""
    parent = source_file.parent
    stem = source_file.stem + ".o"
    matches = []
    for name in ("Makefile", "Kbuild"):
        f = parent / name
        if not f.is_file():
            continue
        contents = f.read_text(errors="replace").replace("\\\n", " ")
        for line in contents.splitlines():
            m = RULE_RE.match(line)
            if not m:
                continue
            objects = re.findall(r"\b[A-Za-z0-9_.-]+\.o\b", m.group(2))
            if stem in objects:
                option = m.group(1)
                matches.append({
                    "makefile":str(f.relative_to(root)),
                    "config":"CONFIG_"+option,
                    "stage7_config":config.get(option, "not in config"),
                    "rule":line.strip()[:350],
                    "linkage":"direct object name in CONFIG rule; still not proof of runtime probe"
                })
    return matches

def collect_sources(root):
    candidates = []
    for directory in ("drivers", "arch/arm64", "usb_shim"):
        folder = root / directory
        if not folder.is_dir():
            continue
        candidates.extend(folder.rglob("*.c"))
    return sorted(set(candidates))

def scan(root, config, interested):
    of_map = {name: [] for name in interested}
    stray = {name: [] for name in interested}
    count = 0
    for file in collect_sources(root):
        if file.stat().st_size > 3_000_000:
            continue
        raw = file.read_text(errors="replace")
        text = strip_comments(raw)
        count += 1
        tables = list(TABLE_RE.finditer(text))
        in_table = set()
        for table in tables:
            compatibles = set(COMPAT_RE.findall(table.group(2)))
            for name in compatibles.intersection(interested):
                line = text.count("\n", 0, table.start()) + 1
                entry = {
                    "source": str(file.relative_to(root)),
                    "line": line,
                    "table": table.group(1),
                    "source_sha256":hashlib.sha256(file.read_bytes()).hexdigest(),
                    "makefile_direct_rules":lookup_makefiles(file, root, config),
                    "interpretation":"exact literal in source of_device_id table, NOT tested binding"
                }
                of_map[name].append(entry)
                in_table.add(name)
        if any('"' + name + '"' in text for name in interested):
            literals = set(LITERAL_RE.findall(text))
            for name in literals.intersection(interested):
                if name in in_table:
                    continue
                if len(stray[name]) < 15:
                    stray[name].append(str(file.relative_to(root)))
    return {"scanned_c_sources":count, "of_matches":of_map, "other_literal_files":stray}

def parse_config(text):
    result = {}
    for line in text.splitlines():
        m = re.match(r"^CONFIG_([A-Za-z0-9_]+)=(.*)$", line)
        if m:
            result[m.group(1)] = m.group(2)
        m = re.match(r"^# CONFIG_([A-Za-z0-9_]+) is not set$", line)
        if m:
            result[m.group(1)] = "n"
    return result

def validate_sources(src, inputs):
    for label, path in src.items():
        if not path.is_dir():
            raise ValueError("Source directory missing: "+label)
        rev = path / ".git"
        if not rev.exists():
            raise ValueError("Source revision not verifiable for: "+label)
        revision = inputs.get(label)
        if revision is None or not re.fullmatch(r"[0-9a-f]{40}",revision):
            raise ValueError("Expected SHA40 source revision: "+label)
        import subprocess
        actual = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        if actual != revision:
            raise ValueError("Source revision mismatch: "+label)

def audit(manifest, config, source_dirs, pinned_revisions):
    validate_sources(source_dirs,pinned_revisions)
    target = manifest["target_compatibles"]
    target += [{"category":"overlay","compatible":name,"base_status":"overlay unknown",
                "config_hints":[]}
               for name in manifest["overlay_required_compatibles"]]
    interested = set(x["compatible"] for x in target)
    found = {name:{"matches":[],"literal_files":[]} for name in interested}
    scanned = {}
    for label, root in source_dirs.items():
        result=scan(root,config,interested)
        scanned[label]=result["scanned_c_sources"]
        for name in interested:
            for match in result["of_matches"][name]:
                match["source_repository"]=label
                found[name]["matches"].append(match)
            for file in result["other_literal_files"][name]:
                found[name]["literal_files"].append({"repository":label,"source":file})

    nodes = []
    for node in target:
        name = node["compatible"]
        matches = found[name]["matches"]
        exact_with_y = any(any(m["stage7_config"] == "y" for m in match["makefile_direct_rules"])
                           for match in matches)
        exact_with_m = any(any(m["stage7_config"] == "m" for m in match["makefile_direct_rules"])
                           for match in matches)
        state = ("OF_TABLE_MATCH_DIRECT_Y_RULE" if exact_with_y
                 else "OF_TABLE_MATCH_DIRECT_M_RULE" if exact_with_m
                 else "OF_TABLE_MATCH_BUILD_LINK_UNKNOWN" if matches
                 else "LITERAL_ONLY_NO_OF_MATCH" if found[name]["literal_files"]
                 else "NO_SOURCE_OF_MATCH_FOUND")
        nodes.append({
            "category":node["category"],"compatible":name,
            "stock_base_status":node["base_status"],
            "source_of_table_match":state,
            "candidate_hits":matches,
            "other_literal_only_files":found[name]["literal_files"][:8],
            "kconfig_search_hints":{
                key:config.get(key,"not in config") for key in node["config_hints"]},
            "actual_merged_fdt_status":"UNKNOWN",
            "driver_runtime_probe":"UNTESTED",
            "charger_thermal_safety":"UNTESTED",
        })

    return {
        "stage":13,
        "static_scan_completed":True,
        "kernel_sha_from_stage7_artifact":pinned_revisions["kernel"],
        "source_revisions":pinned_revisions,
        "c_files_scanned":scanned,
        "source_match_counts":{
            "with_of_table":sum(bool(n["candidate_hits"]) for n in nodes),
            "without_of_table":sum(not n["candidate_hits"] for n in nodes),
        },
        "nodes":nodes,
        "no_stock_binaries_uploaded":True,
        "boot_image_unchanged":True,
        "modules_autoload_changed":False,
        "hardware_runtime_verified":False,
        "physical_fastboot_boot_authorization":"BLOCKED",
        "limitations":[
            "This is a conservative source-text scan; macros, included tables and generated code may escape the parser.",
            "CONFIG_y with direct Makefile object match is stronger build evidence, but not a verified ELF symbol or probe result.",
            "External power drivers compiled in Stage 7 have not been inserted or shown to match the final FDT.",
            "The watch's selected DTBO and merged DTB, runtime voltage, temperature and PMIC behavior are unknown.",
            "No fastboot boot, flash, erase or device operation is performed."
        ]
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--metadata",type=pathlib.Path,required=True)
    ap.add_argument("--kernel-config",type=pathlib.Path,required=True)
    ap.add_argument("--kernel-source",type=pathlib.Path,required=True)
    ap.add_argument("--bms-source",type=pathlib.Path,required=True)
    ap.add_argument("--soc-source",type=pathlib.Path,required=True)
    ap.add_argument("--revisions",type=pathlib.Path,required=True)
    ap.add_argument("--output",type=pathlib.Path,required=True)
    args=ap.parse_args()
    manifest=json.loads(args.metadata.read_text())
    pins=json.loads(args.revisions.read_text())
    report=audit(manifest,parse_config(args.kernel_config.read_text()),
                 {"kernel":args.kernel_source,"bms":args.bms_source,
                  "soc":args.soc_source},pins)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print("STAGE13_SOURCE_LEVEL_AUDIT_COMPLETED")
    for entry in report["nodes"]:
        print("OF_AUDIT", entry["compatible"], entry["source_of_table_match"],
              "of_hits="+str(len(entry["candidate_hits"])))
    print("PHYSICAL_FASTBOOT_BOOT:",report["physical_fastboot_boot_authorization"])

if __name__=="__main__":
    main()

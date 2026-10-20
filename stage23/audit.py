#!/usr/bin/env python3
"""Inspect immutable Stage 22 artifacts; do not infer runtime binding from config."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from stage7.pack_modules import read_records
from stage13.audit_of_matches import parse_config

MANAGERS = ('pkg', 'opkg', 'apk', 'apt', 'apt-get', 'dpkg', 'rpm', 'dnf', 'pacman')
OPTIONS = ('DRM', 'DRM_MSM', 'DRM_MIPI_DSI', 'DRM_FBDEV_EMULATION', 'FB',
           'FB_SIMPLE', 'DRM_SIMPLEDRM', 'FRAMEBUFFER_CONSOLE', 'INPUT_EVDEV',
           'INPUT_TOUCHSCREEN', 'FW_LOADER', 'KASAN', 'SOUND')


def inspect(directory):
    pins = json.loads((ROOT / 'stage23/pins.json').read_text())
    for name, expected in pins['files'].items():
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('Immutable Stage 22 input mismatch: ' + name)
    boot = json.loads((directory / 'boot-report.json').read_text())
    if boot['project_commit'] != pins['stage22_commit'] or boot['kernel_build'] != 22:
        raise ValueError('Not the expected Stage 22 build')
    config = parse_config((directory / 'kernel.config').read_text())
    records = read_records(gzip.decompress((directory / 'rootfs.cpio.gz').read_bytes()))
    names = [r[2].removeprefix('./') for r in records]
    manager_paths = [n for n in names if Path(n).name in MANAGERS]
    modules = [n for n in names if n.endswith('.ko')]
    firmware = [n for n in names if n.startswith(('lib/firmware/', 'usr/lib/firmware/'))]
    return {
        'stage': 23, 'method': 'pinned_artifact_inspection',
        'boot_image_reused': 'boot-stage22.img', 'boot_sha256': pins['files']['boot-stage22.img'],
        'software_deadline_seconds': boot['software_deadline_seconds'],
        'config_options': {k: config.get(k, 'NOT_PRESENT') for k in OPTIONS},
        'rootfs': {'package_manager_command_paths': manager_paths,
                   'searched_manager_names': list(MANAGERS), 'module_paths': modules,
                   'firmware_paths': firmware,
                   'package_addition_method': 'Buildroot host selection and rootfs rebuild; no configured target package manager'},
        'findings': [
            'DRM common infrastructure is enabled; the in-tree DRM_MSM option is disabled.',
            'FB_SIMPLE, DRM_SIMPLEDRM and FRAMEBUFFER_CONSOLE are disabled.',
            'No external .ko files or firmware files are packaged in this initramfs.',
            'The Stage 22 build scripts do not integrate the separate display/touch driver trees.',
            'Display-clock registration is not display-controller or panel binding.',
            'INPUT_TOUCHSCREEN=y is a category option, not proof of a bound touchscreen driver.'
        ],
        'upstream_research': pins['reference'],
        'runtime_inventory': 'AWAITING_USER_CAPTURE',
        'panel_variant': 'UNKNOWN_UNTIL_LIVE_DT_CAPTURE',
        'new_image_built': False, 'display_test_or_hardware_writes_performed': False
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Conservatively summarize the marked Stage 23 inventory, including capture loss."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def marked(lines, begin, end):
    starts = [i for i, line in enumerate(lines) if line.strip() == begin]
    ends = [i for i, line in enumerate(lines) if line.strip() == end]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError('Missing, duplicated or out-of-order markers: ' + begin)
    return lines[starts[0] + 1:ends[0]]


def analyze(text):
    lines = text.replace('\r\n', '\n').replace('\r', '\n').splitlines()
    body = marked(lines, 'AURORA_STAGE23_BEGIN', 'AURORA_STAGE23_END')
    dmesg_lines = marked(body, 'AURORA_STAGE23_DMESG_BEGIN', 'AURORA_STAGE23_DMESG_END')
    dmesg = '\n'.join(dmesg_lines)
    report = {
        'stage': 23, 'method': 'user_capture_analysis', 'marker_complete': True,
        'capture_loss_notices': [s for s in body if re.search(r'\[missed \d+ bytes\]', s)],
        'kernel_build_22_observed': bool(re.search(r'Linux .*#22\b', '\n'.join(body))),
        'kasan_initialized_observed': 'kasan: KernelAddressSanitizer initialized (generic)' in dmesg,
        'memory_fault_reports': [s for s in dmesg_lines if re.search(
            r'BUG:\s*KASAN:|\buse-after-free\b|Kernel panic|(?:^|\]\s*)Oops:|Call trace:', s)],
        'framebuffer_entries': [s for s in body if s.startswith('FB ')],
        'class_device_entries': [s for s in body if s.startswith('DEVICE ')],
        'input_event_entries': [s for s in body if s.startswith('EVENT ')],
        'live_dt_entries': [s for s in body if s.startswith('DT ')],
        'panel_description_entries': [s for s in body if s.startswith('PANEL ')],
        'platform_binding_entries': [s for s in body if s.startswith('PLATFORM ')],
        'dt_inventory_limited': 'DT_NODE_LIMIT_REACHED' in body,
        'return_to_fastboot': 'NOT_INFERRED_FROM_CAPTURE',
        'display_or_touch_functionality': 'NOT_PROVEN_BY_DEVICE_NODE_PRESENCE'
    }
    report['capture_usable_for_comparison'] = bool(report['kernel_build_22_observed'] and
        not report['capture_loss_notices'] and not report['dt_inventory_limited'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = args.capture.read_bytes()
    result = analyze(data.decode('utf-8-sig'))
    result['input_sha256'] = hashlib.sha256(data).hexdigest()
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Execute the actual pinned probe/provider functions with host fault injection.

Kernel APIs outside these functions are simulated. This verifies probe unwind
and a deterministic stale-list negative control, not hardware or concurrency.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

CASES = ('success', 'zero-qos', 'no-desc', 'alloc-qp', 'alloc-data',
         'alloc-bus', 'bus-get', 'bus-enable', 'map', 'provider-add',
         'qos-get-defer', 'qos-get-eio', 'alloc-qos', 'qos-enable',
         'node-first', 'node-second', 'retry-qos-get', 'retry-qos-enable')


def function(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        if source[end] == '{': depth += 1
        if source[end] == '}': depth -= 1
        end += 1
    return source[start:end] + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original', 'patched', 'core', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    pins = json.loads((here / 'pins.json').read_text())
    for label, path in [('original', args.original), ('patched', args.patched), ('core', args.core)]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == pins['sources'][label], label

    core = args.core.read_text()
    providers = ('#define icc_provider_add pinned_provider_add\n'
                 '#define icc_provider_del pinned_provider_del\n' +
                 function(core, 'int icc_provider_add(struct icc_provider *provider)') +
                 function(core, 'int icc_provider_del(struct icc_provider *provider)') +
                 '#undef icc_provider_add\n#undef icc_provider_del\n'
                 'static int icc_provider_add(struct icc_provider *p) {\n'
                 '    return fails("provider-add") ? -EIO : pinned_provider_add(p);\n}\n'
                 'static int icc_provider_del(struct icc_provider *p) { return pinned_provider_del(p); }\n')
    # LSan needs proc/ptrace access unavailable in some hosts. These cases use
    # explicit provider/node/clock accounting; ASan still checks every access.
    env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:halt_on_error=1',
           'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    report = {'stage': 22, 'method': 'actual_pinned_functions_with_simulated_kernel_APIs',
              'sanitizers': ['address', 'undefined'], 'hardware_or_concurrency_test': False}
    with tempfile.TemporaryDirectory(prefix='aurora-qnoc-') as temp:
        root = Path(temp)
        binaries = {}
        for label, path in [('original', args.original), ('patched', args.patched)]:
            cfile = root / (label + '.c')
            cfile.write_text('#include "probe_fixture.h"\n' + providers +
                             function(path.read_text(), 'static int qnoc_probe(struct platform_device *pdev)') +
                             '#include "probe_scenarios.c"\n')
            binary = root / label
            subprocess.run(['gcc', '-std=gnu11', '-O1', '-g', '-no-pie',
                            '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                            '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                            '-Wno-unused-function', '-I', str(here), str(cfile), '-o', str(binary)], check=True)
            binaries[label] = binary
        negative = subprocess.run([str(binaries['original']), 'retry-qos-get'],
                                  env={**env, 'AURORA_NEGATIVE_CONTROL': '1'},
                                  capture_output=True, text=True, timeout=15)
        assert negative.returncode != 0 and 'heap-use-after-free' in negative.stderr, negative.stderr
        report['negative_control'] = {'original_reproduces_heap_use_after_free': True,
                                      'exit_code': negative.returncode,
                                      'asan_excerpt': negative.stderr.splitlines()[:18]}
        results = []
        for case in CASES:
            result = subprocess.run([str(binaries['patched']), case], env=env,
                                    capture_output=True, text=True, timeout=15)
            assert result.returncode == 0 and result.stdout.strip() == 'PASS', (case, result.stderr)
            results.append({'case': case, 'passed': True})
        report['patched_cases'] = results
        report['passed_cases'] = len(results)
        report['source_sha256'] = pins['sources']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"Original ASan UAF reproduced; {len(CASES)} patched probe cases passed")


if __name__ == '__main__':
    main()

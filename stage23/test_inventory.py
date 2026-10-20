import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_capture import analyze
from make_capture import commands

HERE = Path(__file__).resolve().parent


class InventoryTests(unittest.TestCase):
    def write(self, root, name, data):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode())

    def run_inventory(self, root):
        return subprocess.run(['sh', str(HERE / 'inventory.sh')],
            env={**os.environ, 'AURORA_STAGE23_TEST_ROOT': str(root)},
            capture_output=True, text=True, timeout=15)

    def fixture(self, root):
        self.write(root, '.aurora-stage23-fixture', '')
        self.write(root, 'proc/uptime', '19.15 66.98\n')
        self.write(root, 'proc/fb', '')
        self.write(root, 'proc/bus/input/devices', 'N: Name="power button"\n')
        self.write(root, 'proc/modules', '')
        self.write(root, 'fixture-dmesg', '[0] Linux version fixture #22\n[0] kasan: KernelAddressSanitizer initialized (generic)\n')

    def test_unmarked_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_inventory(Path(tmp)).returncode, 64)

    def test_absent_display_does_not_become_a_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            result = self.run_inventory(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = analyze(result.stdout)
            self.assertEqual(report['framebuffer_entries'], [])
            self.assertEqual(report['live_dt_entries'], [])
            self.assertEqual(report['display_or_touch_functionality'], 'NOT_PROVEN_BY_DEVICE_NODE_PRESENCE')

    def test_available_nodes_and_nul_dt_are_read_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            files = {'sys/class/graphics/fb0/name': 'fixture-fb\n',
                'sys/class/graphics/fb0/virtual_size': '384,384\n',
                'sys/class/drm/card0-DSI-1/status': 'connected\n',
                'sys/class/input/event0/device/name': 'fixture-touch\n',
                'sys/firmware/devicetree/base/soc/display/compatible': b'qcom,sde-kms\0qcom,mdss\0',
                'sys/firmware/devicetree/base/soc/display/status': b'okay\0',
                'sys/firmware/devicetree/base/soc/display/reg': b'\0\0\0\1'}
            files['sys/firmware/devicetree/base/panel/qcom,mdss-dsi-panel-name'] = b'panel-without-compatible\0'
            for name, data in files.items(): self.write(root, name, data)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            result = self.run_inventory(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('compatible=qcom,sde-kms qcom,mdss ', result.stdout)
            self.assertIn('status=okay', result.stdout)
            report = analyze(result.stdout)
            self.assertEqual(len(report['framebuffer_entries']), 1)
            self.assertEqual(len(report['class_device_entries']), 1)
            self.assertEqual(len(report['input_event_entries']), 1)
            self.assertEqual(len(report['live_dt_entries']), 1)
            self.assertEqual(len(report['panel_description_entries']), 1)
            after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before, after)

    def test_command_lines_fit_canonical_tty(self):
        for command in commands():
            self.assertLessEqual(len(command.encode()), 1024)
            subprocess.run(['sh', '-n', '-c', command], check=True)


class CaptureTests(unittest.TestCase):
    def sample(self, extra=''):
        return ('AURORA_STAGE23_BEGIN\nLinux aurora #22 SMP\n'
                + extra + '\nAURORA_STAGE23_DMESG_BEGIN\n'
                'kasan: KernelAddressSanitizer initialized (generic)\n'
                'ramoops: registered\nAURORA_STAGE23_DMESG_END\nAURORA_STAGE23_END\n')

    def test_initialization_is_not_a_kasan_fault(self):
        report = analyze(self.sample())
        self.assertEqual(report['memory_fault_reports'], [])
        self.assertTrue(report['capture_usable_for_comparison'])
        self.assertEqual(report['return_to_fastboot'], 'NOT_INFERRED_FROM_CAPTURE')

    def test_dropped_bytes_make_comparison_incomplete(self):
        self.assertFalse(analyze(self.sample('[missed 200 bytes]'))['capture_usable_for_comparison'])

    def test_dt_limit_is_not_complete_inventory(self):
        self.assertFalse(analyze(self.sample('DT_NODE_LIMIT_REACHED'))['capture_usable_for_comparison'])

    def test_missing_duplicated_or_swapped_markers_are_rejected(self):
        for data in [self.sample().replace('AURORA_STAGE23_END', ''),
                     self.sample() + 'AURORA_STAGE23_BEGIN\n',
                     self.sample().replace('AURORA_STAGE23_BEGIN', 'AURORA_STAGE23_END', 1)]:
            with self.assertRaises(ValueError): analyze(data)

    def test_echoed_command_markers_do_not_count(self):
        with self.assertRaises(ValueError): analyze("printf 'AURORA_STAGE23_BEGIN\\nAURORA_STAGE23_END'\n")

    def test_fault_and_wrong_kernel_remain_visible(self):
        text = self.sample().replace('ramoops: registered', 'BUG: KASAN: use-after-free in qnoc_probe')
        report = analyze(text)
        self.assertEqual(len(report['memory_fault_reports']), 1)
        self.assertFalse(analyze(self.sample().replace('#22', '#20'))['capture_usable_for_comparison'])


if __name__ == '__main__': unittest.main()

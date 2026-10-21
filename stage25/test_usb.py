import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

from package import combined_boot, image_parts, legacy_streams, make_overlay, static_arm64
from stage7.pack_modules import read_records

HERE = Path(__file__).resolve().parent


def helper():
    b = bytearray(120)
    b[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HH', b, 16, 2, 183)
    struct.pack_into('<Q', b, 32, 64)
    struct.pack_into('<HH', b, 54, 56, 1)
    struct.pack_into('<I', b, 64, 1)
    return bytes(b)


def template():
    b = bytearray(4096)
    b[:8] = b'ANDROID!'
    struct.pack_into('<I', b, 20, 1584)
    struct.pack_into('<I', b, 40, 4)
    return bytes(b)


class Packaging(unittest.TestCase):
    def test_combined_image_preserves_exact_payloads_and_rejects_bounds(self):
        k = bytearray(9001); k[56:60] = b'ARM\x64'
        r = b'ramdisk'*1000
        b = combined_boot(template(), bytes(k), r)
        self.assertEqual(image_parts(b), (bytes(k), r))
        self.assertIn(b'rdinit=/aurora-stage25-init', b[:4096])
        with self.assertRaises(ValueError): image_parts(b[:5000])
        with self.assertRaises(ValueError): combined_boot(template(), bytes(k), bytes(67108864))

    def test_recovery_helper_rejects_wrong_abi_and_dynamic_interpreter(self):
        static_arm64(helper())
        b = bytearray(helper()); struct.pack_into('<H', b, 18, 40)
        with self.assertRaises(ValueError): static_arm64(b)
        b = bytearray(helper()); struct.pack_into('<I', b, 64, 3)
        with self.assertRaises(ValueError): static_arm64(b)
        with self.assertRaises(ValueError): static_arm64(helper()[:80])

    def test_overlay_has_root_owned_executable_entrypoints_and_pre_mount_null(self):
        records = {r[2]: r for r in read_records(make_overlay(helper()))}
        for name in ('init', 'aurora-stage25-init', 'usr/sbin/aurora-return'):
            self.assertEqual(records[name][1][1:4], [0o100755, 0, 0])
        self.assertEqual(records['init'][3], records['aurora-stage25-init'][3])
        self.assertEqual(records['dev/null'][1][9:11], [1, 3])
        self.assertFalse(any(n.endswith('.ko') for n in records))

    def test_lz4_rejects_truncated_or_unknown_stream(self):
        for b in (b'x', struct.pack('<II', 0x184c2102, 100)+b'bad', struct.pack('<I', 0x184c2102)):
            with self.assertRaises(ValueError): legacy_streams(b)


class Gadget(unittest.TestCase):
    def setup_root(self, root, controllers=()):
        (root/'.aurora-test-root').touch()
        (root/'sys/class/udc').mkdir(parents=True)
        (root/'sys/kernel/config/usb_gadget').mkdir(parents=True)
        for name in controllers: (root/'sys/class/udc'/name).mkdir()

    def run_gadget(self, root):
        return subprocess.run(['sh', str(HERE/'overlay/usr/sbin/aurora-acm25')],
                              env={**os.environ, 'AURORA_TEST_ROOT': str(root)}, capture_output=True)

    def test_acm_descriptors_and_controller_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.setup_root(root, ['test-udc'])
            r = self.run_gadget(root)
            self.assertEqual(r.returncode, 0, r.stderr)
            gadget = root/'sys/kernel/config/usb_gadget/aurora_stage25'
            expected = {'idVendor': '0x1d6b', 'idProduct': '0x0104', 'bDeviceClass': '0x02',
                        'bDeviceSubClass': '0x02', 'bDeviceProtocol': '0x01', 'UDC': 'test-udc'}
            for f, value in expected.items(): self.assertEqual((gadget/f).read_text().strip(), value)
            self.assertEqual((gadget/'configs/c.1/acm.GS0').resolve(), gadget/'functions/acm.GS0')

    def test_missing_multiple_and_owned_udcs_refused(self):
        for controllers, owner, expected in (([], False, 2), (['a','b'], False, 3), (['a'], True, 4)):
            with self.subTest(controllers=controllers, owner=owner), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); self.setup_root(root, controllers)
                if owner:
                    p = root/'sys/kernel/config/usb_gadget/existing/UDC'
                    p.parent.mkdir(); p.write_text('a\n')
                self.assertEqual(self.run_gadget(root).returncode, expected)
                self.assertFalse((root/'sys/kernel/config/usb_gadget/aurora_stage25').exists())

    def test_unmarked_fixture_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_gadget(Path(tmp)).returncode, 64)


if __name__ == '__main__': unittest.main()

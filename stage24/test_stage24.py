import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tarfile
import tempfile
import unittest


HERE = Path(__file__).resolve().parent


def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


audit = module('audit')
fetch = module('fetch')


def arm_elf(bits=1):
    data = bytearray(24)
    data[:6] = b'\x7fELF' + bytes([bits, 1])
    struct.pack_into('<H', data, 18, 40 if bits == 1 else 183)
    return bytes(data)


def write_tar(path, files):
    mode = 'w:gz' if path.name.endswith('.gz') else 'w:xz'
    with tarfile.open(path, mode) as t:
        for name, data, uid, gid, permissions in files:
            entry = tarfile.TarInfo(name)
            entry.uid, entry.gid, entry.mode = uid, gid, permissions
            if data is None:
                entry.type = tarfile.DIRTYPE
                t.addfile(entry)
            else:
                entry.size = len(data)
                t.addfile(entry, io.BytesIO(data))


class Inputs(unittest.TestCase):
    def test_inputs_are_pinned_and_arm32_is_explicit(self):
        pins = json.loads((HERE / 'pins.json').read_text())
        self.assertEqual(pins['target']['userspace'], 'armhf')
        self.assertEqual(pins['target']['kernel_arch'], 'arm64')
        for pin in pins['repositories'].values():
            self.assertRegex(pin['revision'], r'^[0-9a-f]{40}$')
        for pin in pins['downloads'].values():
            self.assertRegex(pin['sha256'], r'^[0-9a-f]{64}$')
            self.assertGreater(pin['size'], 0)
            self.assertNotIn('lastSuccessfulBuild', pin['url'])

    def test_work_directory_escape_is_rejected(self):
        root = Path('/tmp/stage24-fixture').resolve()
        for name in ['../outside', '/etc/passwd', '.']:
            with self.assertRaises(ValueError):
                fetch.destination(root, name)

    def test_wrong_userspace_abi_is_rejected(self):
        audit.arm32(arm_elf())
        with self.assertRaises(ValueError):
            audit.arm32(arm_elf(2))


class Boot(unittest.TestCase):
    def image(self, kernel=True):
        data = bytearray(8192)
        data[:8] = b'ANDROID!'
        struct.pack_into('<II', data, 8, 64 if kernel else 0, 0 if kernel else 64)
        struct.pack_into('<I', data, 20, 1584)
        struct.pack_into('<I', data, 40, 4)
        data[4096+56:4096+60] = b'ARMd'
        return data

    def test_split_v4_images_and_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'boot.img'
            for kernel in [True, False]:
                p.write_bytes(self.image(kernel))
                audit.boot_image(p, kernel, 16384)
            with self.assertRaises(ValueError):
                audit.boot_image(p, True, 16384)
            with self.assertRaises(ValueError):
                audit.boot_image(p, False, 4096)

    def test_truncated_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'boot.img'
            data = self.image()
            struct.pack_into('<I', data, 8, 100000)
            p.write_bytes(data)
            with self.assertRaises(ValueError):
                audit.boot_image(p, True, 67108864)


@unittest.skipUnless(os.geteuid() == 0, 'numeric ownership integration test requires root')
class Filesystem(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / 'ownership'
            probe.touch()
            try:
                os.chown(probe, 32011, 9998)
            except OSError:
                self.skipTest('host filesystem cannot represent target numeric UID/GID')

    def test_assembly_keeps_uid_setuid_symlink_and_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            inputs = base / 'inputs'
            inputs.mkdir()
            write_tar(inputs / 'ubuntu-touch-android9plus-rootfs-armhf.tar.gz', [
                ('etc', None, 0, 0, 0o755),
                ('usr/lib/os-release', b'ID=ubuntu\nVERSION_ID="20.04"\n', 0, 0, 0o644),
                ('usr/bin/apt', arm_elf(), 0, 0, 0o755),
                ('usr/bin/dpkg', arm_elf(), 0, 0, 0o755),
                ('usr/bin/owned-fixture', b'test', 32011, 9998, 0o4755),
            ])
            write_tar(inputs / 'halium_halium_arm.tar.xz', [
                ('system/var/lib/lxc/android/android-rootfs.img', b'fixture', 0, 0, 0o644),
            ])
            device = base / 'device_eos.tar.xz'
            write_tar(device, [
                ('system/opt/halium-overlay/etc/deviceinfo/devices/halium.yaml', b'eos:\n', 0, 0, 0o644),
            ])
            # Exercise an absolute symlink found in the real rootfs.
            root_tar = inputs / 'ubuntu-touch-android9plus-rootfs-armhf.tar.gz'
            with tarfile.open(root_tar, 'r:gz') as t:
                entries = [(m, t.extractfile(m).read() if m.isfile() else None) for m in t]
            with tarfile.open(root_tar, 'w:gz') as t:
                for m, data in entries:
                    t.addfile(m, io.BytesIO(data) if data is not None else None)
                e = tarfile.TarInfo('vendor')
                e.type, e.linkname = tarfile.SYMTYPE, '/android/vendor'
                t.addfile(e)
            (base / 'sources.json').write_text(json.dumps({'target': {'system_partition_size': 64 * 1024 * 1024}}))
            out = base / 'out'
            r = subprocess.run(['bash', str(HERE / 'assemble.sh'), str(base), str(device), str(out)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)
            image = out / 'ubuntu.img'
            report = audit.audit_rootfs(image)
            self.assertTrue(report['writable_image_marker'])
            stat = audit.debugfs(image, 'stat /usr/bin/owned-fixture').decode()
            self.assertRegex(stat, r'User:\s+32011\s+Group:\s+9998')
            self.assertRegex(stat, r'Mode:\s+04755')
            self.assertIn(b'/android/vendor', audit.debugfs(image, 'stat /vendor'))
            # Missing target files must fail verification, even though debugfs exits zero.
            with self.assertRaises(ValueError):
                audit.debugfs(image, 'cat /not-present')


if __name__ == '__main__':
    unittest.main()

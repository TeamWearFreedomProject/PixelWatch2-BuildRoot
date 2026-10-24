import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sdk_tools', Path(__file__).with_name('sdk_tools.py'))
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


def elf(path, size=128, malformed=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = bytearray(64)
    header[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<Q', header, 40, size + 64 if malformed else 64)
    struct.pack_into('<HHH', header, 58, 64, 1, 0)
    with path.open('wb') as output:
        output.write(header)
        output.truncate(size)
    path.chmod(0o755)


def fixture(root):
    for name, size in tools.RESIDUES.items():
        path = root / name
        elf(path, size, True)
        elf(path.with_name(path.name[1:].rsplit('.', 1)[0]))


class SDKInputs(unittest.TestCase):
    def test_only_pinned_staging_residues_are_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            valid, skipped = tools.executables(root)
            self.assertEqual(set(skipped), set(tools.RESIDUES))
            self.assertEqual(len(valid), len(tools.RESIDUES))

    def test_corrupt_real_tool_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            elf(root / 'usr/bin/cmake', 128, True)
            with self.assertRaisesRegex(ValueError, 'Unexpected malformed SDK ELF'):
                tools.executables(root)

    def test_unknown_hidden_corruption_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root)
            elf(root / 'usr/bin/.unknown', 128, True)
            with self.assertRaisesRegex(ValueError, 'Unexpected malformed SDK ELF'):
                tools.executables(root)


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import struct
import unittest

from prepare import archive
from configure import configure
from hook import patch
from assemble import boot_image,config_delta
from qemu_check import check
from stage7.pack_modules import read_records
from stage25.package import image_parts


def elf():
    b=bytearray(120);b[:6]=b'\x7fELF\x02\x01';struct.pack_into('<HH',b,16,2,183)
    struct.pack_into('<Q',b,32,64);struct.pack_into('<HH',b,54,56,1);struct.pack_into('<I',b,64,1)
    return bytes(b)


class Embedded(unittest.TestCase):
    def test_private_archive_survives_external_root_name_conflicts(self):
        applets='sh getty mount sleep cat ln modprobe grep dmesg uname ls mkdir head'.split()
        files={r[2]:r for r in read_records(archive(elf(),elf(),applets))}
        for n in ('aurora26/pid1','aurora26/busybox','aurora26/init','aurora26/console','aurora26/acm','aurora26/info'):
            self.assertEqual(files[n][1][1:4],[0o100755,0,0])
        self.assertEqual(files['aurora26/bin/sh'][3],b'../busybox')
        for n in ('aurora26/init','aurora26/console','aurora26/acm','aurora26/info'):
            self.assertTrue(files[n][3].startswith(b'#!/aurora26/busybox sh\n'))
        self.assertIn(b'exec /aurora26/busybox sh -i',files['aurora26/console'][3])
        self.assertNotIn('init',files);self.assertNotIn('bin/sh',files)
        self.assertEqual(files['dev/console'][1][9:11],[5,1])
        self.assertEqual(files['dev/null'][1][9:11],[1,3])
        self.assertEqual(files['dev/kmsg'][1][9:11],[1,11])
        self.assertFalse(any(n.endswith('.ko') for n in files))

    def test_missing_modprobe_or_escaping_applet_rejected(self):
        apps='sh getty mount sleep cat ln modprobe grep dmesg uname ls mkdir head'.split()
        with self.assertRaises(ValueError):archive(elf(),elf(),[a for a in apps if a!='modprobe'])
        with self.assertRaises(ValueError):archive(elf(),elf(),apps+['../escape'])

    def test_kernel_boot_has_no_external_ramdisk(self):
        k=bytearray(10101);k[56:60]=b'ARM\x64'
        b=boot_image(bytes(k));self.assertEqual(image_parts(b),(bytes(k),b''))
        self.assertIn(b'rdinit=/aurora26/pid1',b[:4096])
        with self.assertRaises(ValueError):boot_image(b'wrong kernel')

    def test_config_is_limited_to_initramfs_and_dedicated_entry(self):
        original='CONFIG_CMDLINE="console=tty0"\nCONFIG_CMDLINE_EXTEND=y\nCONFIG_MODVERSIONS=y\nCONFIG_INITRAMFS_SOURCE=""\n# CONFIG_INITRAMFS_COMPRESSION_GZIP is not set\n'
        new=configure(original,'/tmp/diagnostic.cpio')
        delta=config_delta(original,new)
        self.assertEqual(set(delta),{'CMDLINE','INITRAMFS_SOURCE','INITRAMFS_COMPRESSION_GZIP'})
        with self.assertRaises(ValueError):config_delta(original,new.replace('CONFIG_MODVERSIONS=y','CONFIG_MODVERSIONS=n'))
        with self.assertRaises(ValueError):configure(new,'/tmp/double.cpio')

    def test_configuration_hook_rejects_upstream_drift(self):
        source='before\nmake O="$OUT" $MAKEOPTS $deviceinfo_kernel_defconfig\nafter\n'
        new=patch(source);self.assertIn('stage26/configure.py',new);self.assertIn('olddefconfig',new)
        with self.assertRaises(ValueError):patch('unexpected upstream script')
        with self.assertRaises(ValueError):patch(source+source)

    def test_runtime_check_requires_shell_deadline_and_machine_reset(self):
        log='\n'.join(('AURORA_STAGE26_TIMER_ARMED seconds=90','AURORA_STAGE26_SHELL_STARTED',
                        'AURORA_STAGE26_DEADLINE','AURORA_STAGE26_RESTART2_BOOTLOADER'))
        check(log,0)
        for text,rc in ((log,-1),(log.replace('AURORA_STAGE26_DEADLINE',''),0),(log+'WRONG_EXTERNAL_INIT_EXECUTED',0)):
            with self.assertRaises(ValueError):check(text,rc)


if __name__=='__main__':unittest.main()

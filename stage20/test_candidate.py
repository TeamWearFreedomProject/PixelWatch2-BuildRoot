import gzip
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stage7.pack_modules import fresh, encode, read_records
from prepare_rootfs import prepare
from package_boot import package, CMDLINE
from verify_embedded import locate, verify

HERE = Path(__file__).resolve().parent


def fake_helper():
    b = bytearray(64)
    b[:6] = b'\x7fELF\x01\x01'
    struct.pack_into('<HH',b,16,2,40)
    return bytes(b)


class ArchiveTests(unittest.TestCase):
    def test_dedicated_init_and_old_abi_modules_removed(self):
        names = [('bin',b'',stat.S_IFDIR|0o755),('bin/busybox',b'ARM32 fixture',stat.S_IFREG|0o755),
                 ('etc',b'',stat.S_IFDIR|0o755),('etc/fstab',b'/dev/root / ext2 rw 0 1',stat.S_IFREG|0o644),
                 ('etc/inittab',b'mount -a',stat.S_IFREG|0o644),('etc/init.d/S01old',b'old',stat.S_IFREG|0o755),
                 ('usr/bin/adbd',b'old',stat.S_IFREG|0o755),('lib/modules/old/extra/battery.ko',b'old',stat.S_IFREG|0o644)]
        data = gzip.compress(b''.join(encode(fresh(n,b,m,i+1)) for i,(n,b,m) in enumerate(names))+encode(fresh('TRAILER!!!',b'',0,100)))
        result, report = prepare(data,HERE/'overlay',fake_helper())
        lookup = {r[2]:r for r in read_records(gzip.decompress(result))}
        self.assertNotIn('etc/inittab',lookup)
        self.assertNotIn('usr/bin/adbd',lookup)
        self.assertNotIn('etc/fstab',lookup)
        self.assertFalse(any(n.endswith('.ko') for n in lookup))
        self.assertIn(b'PID 1',lookup['init'][3])
        self.assertTrue(lookup['init'][1][1]&stat.S_IXUSR)
        self.assertTrue(stat.S_ISCHR(lookup['dev/null'][1][1]))
        self.assertEqual(lookup['dev/null'][1][9:11],[1,3])
        self.assertEqual(report['old_ko_removed'],1)

    def test_host_helper_rejected(self):
        with self.assertRaises(ValueError):
            prepare(b'',HERE/'overlay',b'x86 helper')


class BootTests(unittest.TestCase):
    def template(self):
        t=bytearray(8192);t[:8]=b'ANDROID!'
        struct.pack_into('<4I',t,8,64,0,0,1584);struct.pack_into('<I',t,40,4)
        return t

    def test_new_kernel_exactly_embedded_with_bounded_cmdline(self):
        k=bytearray(512);k[56:60]=b'ARM\x64'
        b=package(self.template(),k)
        self.assertEqual(b[4096:4608],k)
        self.assertEqual(struct.unpack_from('<I',b,8)[0],len(k))
        self.assertEqual(b[44:1580].split(b'\0')[0],CMDLINE)
        self.assertEqual(len(b)%4096,0)

    def test_signed_or_wrong_header_and_compressed_kernel_rejected(self):
        k=bytearray(64);k[56:60]=b'ARM\x64'
        for offset,value in ((1580,1),(40,3),(12,1)):
            t=self.template();struct.pack_into('<I',t,offset,value)
            with self.assertRaises(ValueError): package(t,k)
        with self.assertRaises(ValueError): package(self.template(),b'gzip')


class RuntimeScriptTests(unittest.TestCase):
    def sandbox(self,d):
        r=Path(d);(r/'.aurora-test-root').touch();return r

    def run_script(self,name,r):
        env={**os.environ,'AURORA_TEST_ROOT':str(r)}
        return subprocess.run(['sh',str(HERE/'overlay/usr/sbin'/name)],env=env,capture_output=True,text=True,timeout=5)

    def test_single_udc_creates_cdc_function_and_binds(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.sandbox(d);(r/'sys/class/udc/test-udc').mkdir(parents=True)
            result=self.run_script('aurora-acm20',r)
            self.assertEqual(result.returncode,0,result.stderr)
            g=r/'sys/kernel/config/usb_gadget/aurora_stage20'
            self.assertEqual((g/'UDC').read_text(),'test-udc\n')
            self.assertEqual((g/'bDeviceClass').read_text(),'0x02\n')
            self.assertEqual((g/'bDeviceSubClass').read_text(),'0x02\n')
            self.assertTrue((g/'configs/c.1/acm.GS0').is_symlink())

    def test_no_udc_or_multiple_udcs_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.sandbox(d)
            self.assertEqual(self.run_script('aurora-acm20',r).returncode,2)
            for n in ('one','two'): (r/'sys/class/udc'/n).mkdir(parents=True)
            self.assertEqual(self.run_script('aurora-acm20',r).returncode,3)
            self.assertFalse((r/'sys/kernel/config/usb_gadget').exists())

    def test_unmarked_test_prefix_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_script('aurora-acm20',Path(d)).returncode,64)
            self.assertEqual(self.run_script('aurora-timeout',Path(d)).returncode,64)

    def test_deadline_requests_mock_reboot_without_host_reboot(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.sandbox(d);p=r/'usr/sbin/aurora-return';p.parent.mkdir(parents=True)
            p.write_text('#!/bin/sh\nprintf "%s" "$1" > "'+str(r)+'/called"\n');p.chmod(0o755)
            result=self.run_script('aurora-timeout',r)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((r/'called').read_text(),'--request')


class EmbeddedTests(unittest.TestCase):
    def elf(self,payload):
        data=bytearray(4096)+payload
        data[:6]=b'\x7fELF\x02\x01'
        struct.pack_into('<Q',data,32,64)
        struct.pack_into('<HH',data,54,56,1)
        struct.pack_into('<IIQQQQQQ',data,64,1,4,4096,0xFFFF0000,0,len(payload),len(payload),4096)
        return bytes(data)

    def test_final_elf_payload_compared_with_current_archive(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);payload=gzip.compress(b'new stage20 cpio')
            (r/'rootfs').write_bytes(payload);(r/'vmlinux').write_bytes(self.elf(payload))
            with patch('verify_embedded.subprocess.check_output',return_value='__initramfs_start R ffff0000 0\n'):
                self.assertEqual(verify(r/'vmlinux',r/'rootfs')['initramfs_in_final_vmlinux'],'MATCH')
                (r/'rootfs').write_bytes(gzip.compress(b'old archive'))
                with self.assertRaises(ValueError): verify(r/'vmlinux',r/'rootfs')

    def test_missing_or_out_of_bounds_load_segment_fails(self):
        data=self.elf(gzip.compress(b'test'))
        with self.assertRaises(ValueError): locate(data,0x1234)
        with self.assertRaises(ValueError): locate(data[:-2],0xFFFF0000)


if __name__=='__main__': unittest.main()

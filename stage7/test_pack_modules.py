#!/usr/bin/env python3
"""Fast smoke test, independent of a real watch, compiler, or kernel."""
import gzip
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest
import pack_modules as p

class Stage7PackerTests(unittest.TestCase):
    def test_usrmerge_archive_with_seven_unloaded_modules(self):
        with tempfile.TemporaryDirectory() as td:
            d=pathlib.Path(td)
            data=[
                ('init',b'#!/bin/sh',stat.S_IFREG|0o755),
                ('bin',b'',stat.S_IFDIR|0o755),
                ('bin/busybox',b'ARM32',stat.S_IFREG|0o755),
                ('etc',b'',stat.S_IFDIR|0o755),
                ('etc/inittab',b'ttyGS0::respawn:...',stat.S_IFREG|0o644),
                ('usr',b'',stat.S_IFDIR|0o755),
                ('usr/bin',b'',stat.S_IFDIR|0o755),
                ('usr/bin/adbd',b'ARM32',stat.S_IFREG|0o755),
                ('usr/sbin',b'',stat.S_IFDIR|0o755),
                ('usr/sbin/aurora-acm',b'test',stat.S_IFREG|0o755),
                ('lib',b'usr/lib',stat.S_IFLNK|0o777),
                ('usr/lib',b'',stat.S_IFDIR|0o755),
            ]
            records=[p.fresh(name,body,mode,index)
                     for index,(name,body,mode) in enumerate(data,1)]
            original=b''.join(p.encode(x) for x in records)
            original+=p.encode(p.fresh('TRAILER!!!',b'',0,len(records)+1))
            (d/'input.gz').write_bytes(gzip.compress(original))
            (d/'mods').mkdir()
            (d/'meta').mkdir()
            fake_elf=(b'\x7fELF'+bytes((2,1,1,0))+b'\0'*8
                      +b'\0'*2+(183).to_bytes(2,'little')+b'M'*80)
            for name in p.REQUIRED:
                (d/'mods'/name).write_bytes(fake_elf)
            (d/'meta'/'modules.dep').write_text('extra/gvotable.ko:\n')
            command=[sys.executable,str(pathlib.Path(p.__file__)),
                '--input',str(d/'input.gz'),'--output',str(d/'output.gz'),
                '--modules',str(d/'mods'),'--metadata',str(d/'meta'),
                '--kernel-release','5.15.test','--report',str(d/'report.json')]
            subprocess.run(command,check=True,stdout=subprocess.DEVNULL)
            members={r[2]:r for r in
                p.read_records(gzip.decompress((d/'output.gz').read_bytes()))}
            self.assertIn('usr/lib/modules/5.15.test/extra/gvotable.ko',members)
            self.assertIn('usr/lib/modules/5.15.test/modules.dep',members)
            self.assertNotIn('etc/modules-load.d/stage7.conf',members)
            self.assertIn(b'ttyGS0',members['etc/inittab'][3])

if __name__=='__main__':
    unittest.main()

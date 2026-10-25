import hashlib,struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from patch_compositor import OLD,NEW,redirect

def fixture(offset=256,duplicate=False):
    b=bytearray(640);b[:6]=b'\x7fELF\x01\x01';struct.pack_into('<H',b,18,40);struct.pack_into('<I',b,32,64);struct.pack_into('<HHH',b,46,40,3,2)
    struct.pack_into('<10I',b,104,1,1,2,0,256,128,0,0,1,0)
    names=b'\0.rodata\0.shstrtab\0';struct.pack_into('<10I',b,144,9,3,0,0,450,len(names),0,0,1,0);b[450:450+len(names)]=names
    b[offset:offset+len(OLD)]=OLD
    if duplicate:b[330:330+len(OLD)]=OLD
    return bytes(b)
class RedirectTests(unittest.TestCase):
    def test_wrong_version_rejected(self):
        with self.assertRaises(ValueError):redirect(fixture())
    def test_only_entry_data_is_changed(self):
        b=fixture();out,report=redirect(b,hashlib.sha256(b).hexdigest())
        self.assertEqual(out[:256],b[:256]);self.assertEqual(out[256+len(OLD):],b[256+len(OLD):]);self.assertEqual(len(out),len(b));self.assertIn(NEW,out);self.assertFalse(report['machine_code_modified'])
    def test_ambiguous_entry_rejected(self):
        b=fixture(duplicate=True)
        with self.assertRaises(ValueError):redirect(b,hashlib.sha256(b).hexdigest())
    def test_code_section_entry_rejected(self):
        b=fixture(offset=520)
        with self.assertRaises(ValueError):redirect(b,hashlib.sha256(b).hexdigest())
if __name__=='__main__':unittest.main()

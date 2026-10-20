from pathlib import Path
import tempfile
import unittest

from check_routing import matrix
from verify_link import check_elf, check_symbols, parse_map, parse_nm, REQUIRED

PARENT = """ifneq ($(filter y m,$(CONFIG_QCOM_TSENS) $(CONFIG_QCOM_SPMI_TEMP_ALARM)),)
obj-y += qcom/
endif
"""
CHILD = "obj-$(CONFIG_QCOM_SPMI_TEMP_ALARM) += qcom-spmi-temp-alarm.o\n"


class RoutingTests(unittest.TestCase):
    def test_nine_tristate_combinations(self):
        cases = matrix(PARENT, CHILD)
        self.assertEqual(len(cases), 9)
        self.assertEqual(sum(c['qcom_traversals'] for c in cases), 8)

    def test_original_tsens_gate_fails_alarm_only(self):
        with self.assertRaises(ValueError):
            matrix('obj-$(CONFIG_QCOM_TSENS) += qcom/\n', CHILD)

    def test_duplicate_or_unconditional_parent_is_rejected(self):
        for parent in (PARENT + 'obj-y += qcom/\n', 'obj-y += qcom/\n'):
            with self.assertRaises(ValueError):
                matrix(parent, CHILD)

    def test_child_must_keep_tristate_gate(self):
        with self.assertRaises(ValueError):
            matrix(PARENT, 'obj-y += qcom-spmi-temp-alarm.o\n')


class LinkTests(unittest.TestCase):
    def setUp(self):
        self.nm = '\n'.join(name + ' ' + ('t' if name in ('qpnp_tm_probe','qpnp_tm_driver_init') else 'd') + ' ffff000000000100 10' for name in REQUIRED)
        self.nm += '\n__initcall_qpnp_tm_driver_init6 d ffff000000000200 8\n'
        self.symbols = parse_nm(self.nm)
        self.map = parse_map('\n'.join(f"{x['address']:x} {x['type']} {name}" for name,x in self.symbols.items()))

    def test_linked_driver_and_initcall_match_map(self):
        self.assertEqual(check_symbols(self.symbols, self.map, 'on', self.symbols), ['__initcall_qpnp_tm_driver_init6'])

    def test_object_alone_does_not_prove_linkage(self):
        with self.assertRaises(ValueError):
            check_symbols({}, {}, 'on', self.symbols)

    def test_missing_registration_or_wrong_address_fails(self):
        missing = {k:v for k,v in self.symbols.items() if not k.startswith('__initcall')}
        with self.assertRaises(ValueError):
            check_symbols(missing, missing, 'on', self.symbols)
        wrong = dict(self.map)
        wrong['qpnp_tm_probe'] = {'address': 1, 'type': 't'}
        with self.assertRaises(ValueError):
            check_symbols(self.symbols, wrong, 'on', self.symbols)

    def test_off_requires_all_alarm_symbols_absent(self):
        self.assertEqual(check_symbols({}, {}, 'off'), [])
        with self.assertRaises(ValueError):
            check_symbols(self.symbols, self.map, 'off')

    def test_undefined_or_duplicate_symbol_fails(self):
        bad = dict(self.symbols)
        bad['qpnp_tm_probe'] = {'type': 'U', 'address': 1}
        with self.assertRaises(ValueError):
            check_symbols(bad, bad, 'on', bad)
        with self.assertRaises(ValueError):
            parse_nm(self.nm + self.nm)

    def test_elf_type_and_architecture_are_checked(self):
        import struct
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'vmlinux'
            header = bytearray(64)
            header[:6] = b'\x7fELF\x02\x01'
            struct.pack_into('<HH', header, 16, 2, 183)
            p.write_bytes(header)
            check_elf(p, 2)
            with self.assertRaises(ValueError):
                check_elf(p, 1)
            struct.pack_into('<H', header, 18, 62)
            p.write_bytes(header)
            with self.assertRaises(ValueError):
                check_elf(p, 2)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
import pathlib
import tempfile
import unittest
import trace_kbuild as audit

class TracerTests(unittest.TestCase):
    def test_composite_and_direct_link(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            p=root/"drivers"/"test"
            p.mkdir(parents=True)
            (p/"sensor.c").write_text("int test;\n")
            (p/"Makefile").write_text(
                "obj-$(CONFIG_TEST_WATCH) += wrapper.o\n"
                "wrapper-y += sensor.o other.o\n")
            found=audit.trace_file(p/"sensor.c",root,{"TEST_WATCH":"y"})
            self.assertEqual(found["build_evidence"],"POSSIBLE_BUILTIN_LINK")
            self.assertEqual(found["traces"][0]["config"],"CONFIG_TEST_WATCH")
            self.assertEqual(found["traces"][0]["value"],"y")

    def test_explicit_disabled_driver(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            p=root/"drivers"/"test"
            p.mkdir(parents=True)
            (p/"alarm.c").write_text("int test;\n")
            (p/"Makefile").write_text("obj-$(CONFIG_QCOM_SPMI_TEMP_ALARM) += alarm.o\n")
            hit=audit.trace_file(p/"alarm.c",root,{"QCOM_SPMI_TEMP_ALARM":"n"})
            self.assertEqual(hit["build_evidence"],"DISABLED_OR_NONLINKED_RULE")

    def test_missing_rules_not_implicitly_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            p=root/"drivers"/"test"
            p.mkdir(parents=True)
            (p/"power.c").write_text("int test;\n")
            hit=audit.trace_file(p/"power.c",root,{"MODULES":"y"})
            self.assertEqual(hit["build_evidence"],"BUILD_GRAPH_UNRESOLVED")

if __name__=="__main__":
    unittest.main()

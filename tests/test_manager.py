#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
import sys
import unittest

SPEC = importlib.util.spec_from_file_location(
    "deepin_uki_manager", "deepin_uki_manager.py"
)
manager = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = manager
SPEC.loader.exec_module(manager)


SAMPLE = r"""
menuentry 'current' {
  linux /boot/immutable/abc.0/vmlinuz root=UUID=abcd ostree=/ostree/data/abc.0/checkout quiet
  initrd /boot/immutable/abc.0/initrd.img
}
submenu 'advanced' {
menuentry 'duplicate' {
  linux /boot/immutable/abc.0/vmlinuz root=UUID=abcd ostree=/ostree/data/abc.0/checkout quiet
  initrd /boot/immutable/abc.0/initrd.img
}
}
menuentry 'rollback' --class os {
  linux /boot/immutable/def.0/vmlinuz root=UUID=abcd ostree=/ostree/data/def.0/checkout
  initrd /boot/immutable/def.0/initrd.img
}
"""


class ParseTests(unittest.TestCase):
    def test_only_top_level_entries_are_returned(self):
        entries = manager.parse_top_level_entries(SAMPLE)
        self.assertEqual([entry.title for entry in entries], ["current", "rollback"])
        self.assertEqual(entries[0].deployment_id, "abc.0")
        self.assertEqual(entries[0].cmdline, "root=UUID=abcd ostree=/ostree/data/abc.0/checkout quiet")

    def test_unexpanded_grub_variable_is_removed_or_rejected(self):
        config = SAMPLE.replace("quiet\n", "DEEPIN_GFXMODE=$DEEPIN_GFXMODE quiet\n", 1)
        entries = manager.parse_top_level_entries(config)
        self.assertNotIn("$", entries[0].cmdline)


if __name__ == "__main__":
    unittest.main()

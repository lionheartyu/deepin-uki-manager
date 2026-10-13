#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "deepin_uki_manager", "deepin_uki_manager.py"
)
manager = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = manager
SPEC.loader.exec_module(manager)


SAMPLE = r"""
menuentry 'current' {
  linux /boot/immutable/abc.0/vmlinuz-6.6 root=UUID=abcd ostree=auto quiet
  initrd /boot/immutable/abc.0/initrd.img
}
submenu 'advanced' {
menuentry 'duplicate' {
  linux /boot/immutable/abc.0/vmlinuz-6.6 root=UUID=abcd ostree=auto quiet
  initrd /boot/immutable/abc.0/initrd.img
}
}
menuentry 'rollback' --class os {
  linux /boot/immutable/def.0/vmlinuz-6.6 root=UUID=abcd ostree=auto
  initrd /boot/immutable/def.0/initrd.img
}
"""


class ParseTests(unittest.TestCase):
    def test_only_top_level_entries_are_returned(self):
        entries = manager.parse_top_level_entries(SAMPLE)
        self.assertEqual([entry.title for entry in entries], ["current", "rollback"])
        self.assertEqual(entries[0].deployment_id, "abc.0")
        self.assertEqual(entries[0].ostree, "/ostree/data/abc.0/checkout")
        self.assertEqual(
            entries[0].cmdline,
            "root=UUID=abcd ostree=/ostree/data/abc.0/checkout quiet",
        )
        self.assertEqual(entries[1].deployment_id, "def.0")
        self.assertEqual(entries[1].ostree, "/ostree/data/def.0/checkout")

    def test_unexpanded_grub_variable_is_removed_or_rejected(self):
        config = SAMPLE.replace("quiet\n", "DEEPIN_GFXMODE=$DEEPIN_GFXMODE quiet\n", 1)
        entries = manager.parse_top_level_entries(config)
        self.assertNotIn("$", entries[0].cmdline)

    def test_explicit_ostree_argument_is_preserved(self):
        config = SAMPLE.replace(
            "ostree=auto",
            "ostree=/ostree/data/explicit.1/checkout",
            1,
        )
        entry = manager.parse_top_level_entries(config)[0]
        self.assertEqual(entry.ostree, "/ostree/data/explicit.1/checkout")

    def test_auto_requires_deployment_in_kernel_path(self):
        config = SAMPLE.replace("/boot/immutable/abc.0/vmlinuz-6.6", "/boot/vmlinuz-6.6", 1)
        with self.assertRaises(manager.ManagerError):
            manager.parse_top_level_entries(config)


class PublishTests(unittest.TestCase):
    def test_pair_is_published_and_replaced_together_on_success(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            (destination / "deepin-current.efi").write_bytes(b"old-current")
            (destination / "deepin-rollback.efi").write_bytes(b"old-rollback")
            staging = destination / "staging"
            staging.mkdir()
            current = staging / "deepin-current.efi"
            rollback = staging / "deepin-rollback.efi"
            current.write_bytes(b"new-current")
            rollback.write_bytes(b"new-rollback")

            manager._publish_pair(
                {"deepin-current.efi": current, "deepin-rollback.efi": rollback},
                destination,
            )

            self.assertEqual(
                (destination / "deepin-current.efi").read_bytes(), b"new-current"
            )
            self.assertEqual(
                (destination / "deepin-rollback.efi").read_bytes(), b"new-rollback"
            )
            self.assertEqual(
                list(destination.glob(".deepin-uki-recovery-*")), []
            )

    def test_unchanged_pair_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            current = destination / "deepin-current.efi"
            rollback = destination / "deepin-rollback.efi"
            current.write_bytes(b"same-current")
            rollback.write_bytes(b"same-rollback")
            staging = destination / "staging"
            staging.mkdir()
            staged_current = staging / "deepin-current.efi"
            staged_rollback = staging / "deepin-rollback.efi"
            staged_current.write_bytes(b"same-current")
            staged_rollback.write_bytes(b"same-rollback")

            manager._publish_pair(
                {
                    "deepin-current.efi": staged_current,
                    "deepin-rollback.efi": staged_rollback,
                },
                destination,
            )

            self.assertEqual(current.read_bytes(), b"same-current")
            self.assertEqual(rollback.read_bytes(), b"same-rollback")


if __name__ == "__main__":
    unittest.main()

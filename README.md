# deepin-uki-manager

Small host-side manager that turns the top-level OSTree boot entries in
`/boot/grub/grub.cfg` into separate Unified Kernel Images (UKIs). It is intended
as an initial Deepin integration prototype; it does not perform OSTree upgrades
or change the system bootloader.

## Requirements

- Python 3.10+
- `ukify` from systemd
- A mounted XBOOTLDR filesystem at `/boot/xbootldr`
- Root privileges when writing UKIs to the boot partition

The manager reads the GRUB configuration as data; it never evaluates it as a
GRUB or shell program. It currently recognizes top-level `menuentry` blocks
containing one `linux`/`linuxefi` line, one or more `initrd`/`initrdefi` paths,
and exactly one `ostree=` kernel argument. Nested submenu entries are ignored.
The `DEEPIN_GFXMODE=$DEEPIN_GFXMODE` GRUB-only argument is omitted because a UKI
does not expand GRUB variables.

## Try it

```sh
sudo install -D -m 0644 deepin_uki_manager.py \
  /usr/lib/deepin-uki-manager/deepin_uki_manager.py
sudo python3 /usr/lib/deepin-uki-manager/deepin_uki_manager.py reconcile
sudo python3 /usr/lib/deepin-uki-manager/deepin_uki_manager.py status
```

`reconcile` validates the referenced deployment, kernel, and initrd before
building. It writes a temporary UKI in the destination directory, verifies the
PE sections and embedded `.cmdline`, then atomically installs a uniquely named
file. It does not delete old UKIs. UKIs are not signed unless both
`--secure-boot-key` and `--secure-boot-certificate` are supplied.

The supplied path/service units provide a prototype trigger:

```sh
sudo install -D -m 0644 deepin-uki-manager.path \
  /etc/systemd/system/deepin-uki-manager.path
sudo install -D -m 0644 deepin-uki-manager.service \
  /etc/systemd/system/deepin-uki-manager.service
sudo systemctl daemon-reload
sudo systemctl enable --now deepin-uki-manager.service deepin-uki-manager.path
```

The path unit only reacts to changes in `grub.cfg`. A production integration
should also run `reconcile` at boot and after the OSTree deployment transaction,
and should validate signing policy, deployment readiness, and retention before
automatically selecting or deleting UKIs.

## Development checks

```sh
python3 -m unittest discover -s tests -v
python3 -B -m py_compile deepin_uki_manager.py tests/test_manager.py
```

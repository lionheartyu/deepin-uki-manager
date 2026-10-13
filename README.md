# deepin-uki-manager

`deepin-uki-manager` 是一个面向 Deepin 不可变系统的 UKI 管理工具。
它读取 `/boot/grub/grub.cfg` 中的顶层 `menuentry`，为每个包含内核、
initrd 和 `ostree=` 参数的启动项生成一份独立的 Unified Kernel Image（UKI），
并将 UKI 保存到 XBOOTLDR 分区的 `/boot/xbootldr/EFI/Linux/` 目录。

本工具不负责执行 OSTree 更新，也不会修改 GRUB 配置或删除旧 UKI。
它的作用是把已经由系统更新器生成的 GRUB 启动项同步为 UKI。

## 工作方式

工具不会执行 `grub.cfg` 中的 shell/GRUB 代码，只把它当作配置文件解析。
当前支持顶层 `menuentry` 中的：

- 一条 `linux` 或 `linuxefi` 行；
- 一条或多条 `initrd` 或 `initrdefi` 行；
- 一个 `ostree=` 内核参数。

嵌套在 `submenu` 中的启动项会被忽略。

当菜单项包含：

```text
ostree=auto
```

工具会从同一个菜单项的内核路径中提取 deployment ID。例如：

```text
/boot/immutable/3a61...d263a.0/vmlinuz-6.6.0-amd64-desktop
```

会转换为：

```text
ostree=/ostree/data/3a61...d263a.0/checkout
```

这样 current 和 rollback UKI 会分别绑定到各自的 OSTree deployment，
不会都依赖同一个 `ostree=auto`。

Deepin 运行系统中，checkout 可能实际位于：

```text
/persistent/ostree/data/<deployment-id>/checkout
```

工具会同时兼容 `/ostree/data/` 和 `/persistent/ostree/data/` 两种布局。
GRUB 专用的 `DEEPIN_GFXMODE=$DEEPIN_GFXMODE` 参数会被忽略，因为 UKI
不会展开 GRUB 变量。

## 使用条件

使用前需要确认：

- 系统以 UEFI 模式启动；
- `/boot/xbootldr` 已挂载到 FAT32 XBOOTLDR 分区；
- 已安装 `ukify`；
- `/boot/grub/grub.cfg` 可读；
- 当前 GRUB 菜单项引用的内核和 initrd 文件存在；
- 执行生成和安装操作时具有 root 权限。

检查命令：

```bash
command -v ukify
findmnt -M /boot/xbootldr
sudo test -r /boot/grub/grub.cfg && echo "grub.cfg 可读"
```

## 安装工具

在仓库目录执行：

```bash
sudo install -D -m 0755 \
  deepin_uki_manager.py \
  /usr/lib/deepin-uki-manager/deepin_uki_manager.py
```

安装 systemd 服务和监听器：

```bash
sudo install -D -m 0644 \
  deepin-uki-manager.service \
  /etc/systemd/system/deepin-uki-manager.service

sudo install -D -m 0644 \
  deepin-uki-manager.path \
  /etc/systemd/system/deepin-uki-manager.path

sudo systemctl daemon-reload
```

## 第一次手动生成 UKI

建议先手动执行一次，确认 current 和 rollback deployment 都能被识别：

```bash
sudo systemctl start deepin-uki-manager.service
```

也可以直接调用程序：

```bash
sudo python3 \
  /usr/lib/deepin-uki-manager/deepin_uki_manager.py \
  reconcile
```

查看生成结果：

```bash
sudo ls -lh /boot/xbootldr/EFI/Linux/
sudo journalctl -u deepin-uki-manager.service -n 100 --no-pager
```

成功时会为不同 deployment 生成不同文件，例如：

```text
deepin-3a61...d263a.0-<hash>.efi
deepin-f845...a7c68.0-<hash>.efi
```

文件名中的 hash 由 cmdline、内核、initrd 和 os-release 内容计算。
内容没有变化时，重复执行不会无条件生成新文件。

## 检查 UKI 的启动参数

逐个查看 UKI 中嵌入的 `.cmdline`：

```bash
for f in /boot/xbootldr/EFI/Linux/deepin-*.efi; do
    echo "===== $f ====="
    tmp=$(mktemp)
    sudo objcopy --dump-section .cmdline="$tmp" "$f"
    sudo tr '\0' ' ' < "$tmp"
    printf '\n'
    rm -f "$tmp"
done
```

current 和 rollback UKI 应该分别出现不同的参数：

```text
ostree=/ostree/data/<current-deployment>/checkout
ostree=/ostree/data/<rollback-deployment>/checkout
```

查看 UKI 文件列表：

```bash
sudo python3 \
  /usr/lib/deepin-uki-manager/deepin_uki_manager.py \
  status
```

## 启用 `grub.cfg` 实时监听

启用 path 单元后，`/boot/grub/grub.cfg` 发生变化会启动 reconcile 服务：

```bash
sudo systemctl enable --now deepin-uki-manager.path
```

如果希望每次开机都先主动 reconcile 一次，也可以启用服务：

```bash
sudo systemctl enable deepin-uki-manager.service
```

查看运行状态：

```bash
systemctl status deepin-uki-manager.path
systemctl status deepin-uki-manager.service
```

实时查看日志：

```bash
sudo journalctl \
  -u deepin-uki-manager.path \
  -u deepin-uki-manager.service \
  -f
```

服务失败后会等待 5 秒重试，最多在 1 分钟内重试 3 次。
这可以覆盖 GRUB 配置已经写完、但新内核或 initrd 尚未完全落盘的短暂窗口。

## 模拟一次 GRUB 配置更新

测试前先记录 UKI 的时间和文件名：

```bash
sudo ls -l --time-style=full-iso \
  /boot/xbootldr/EFI/Linux/deepin-*.efi
```

然后用相同内容安全地替换 `grub.cfg`，模拟更新器重新生成该文件：

```bash
sudo install -m 0644 \
  /boot/grub/grub.cfg \
  /boot/grub/grub.cfg.tmp

sudo mv \
  /boot/grub/grub.cfg.tmp \
  /boot/grub/grub.cfg
```

查看监听器是否触发：

```bash
sudo journalctl -u deepin-uki-manager.service -n 100 --no-pager
sudo ls -lh --time-style=full-iso \
  /boot/xbootldr/EFI/Linux/deepin-*.efi
```

如果菜单项的内核、initrd 或 cmdline 发生变化，工具会生成带有新 hash
的新 UKI。旧 UKI 默认不会删除，以便在新 UKI 生成失败时保留可启动版本。

## 真实更新流程

真实的系统更新流程应当是：

```text
Lastore/OSTree 完成 deployment 更新
        ↓
新内核和 initrd 写入 /boot/immutable/
        ↓
更新器重新生成 /boot/grub/grub.cfg
        ↓
deepin-uki-manager.path 被触发
        ↓
工具解析新的 current/rollback 菜单项
        ↓
生成对应的新 UKI
```

如果 OSTree 更新完成后没有重新写入 `grub.cfg`，path 单元不会被触发。
因此生产集成时，更新器还应在 deployment 事务完成后主动执行：

```bash
sudo systemctl start deepin-uki-manager.service
```

或者：

```bash
sudo python3 \
  /usr/lib/deepin-uki-manager/deepin_uki_manager.py \
  reconcile
```

工具只负责生成 UKI，不负责把某个 UKI 设为 systemd-boot 默认项，
也不负责创建或修改 UEFI NVRAM 启动项。这些操作应由安装器或启动管理流程负责。

## Secure Boot 签名

默认生成的 UKI 不签名。需要签名时，同时提供私钥和证书：

```bash
sudo python3 \
  /usr/lib/deepin-uki-manager/deepin_uki_manager.py \
  reconcile \
  --secure-boot-key /path/to/db.key \
  --secure-boot-certificate /path/to/db.crt
```

## 开发检查

```bash
python3 -m unittest discover -s tests -v
python3 -B -m py_compile deepin_uki_manager.py tests/test_manager.py
```

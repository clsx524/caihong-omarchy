#!/usr/bin/env python3
"""Read-only boot identity and lifecycle regression tests; no block devices needed."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import os
import shutil
import struct
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]


def load(name, relative):
    module = types.ModuleType(name)
    source = PROJECT / relative
    exec(compile(source.read_text(), str(source), 'exec'), module.__dict__)
    return module


BOOT = load('boot_state', 'packaging/linux-caihong/boot-state')
LIFECYCLE = load('caihong_lifecycle', 'packaging/omarchy-caihong/lifecycle')


class BootVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.package = self.root / 'usr/lib/linux-caihong'
        self.partitions = self.root / 'dev/disk/by-partlabel'
        self.runtime = self.root / 'usr/lib/modules'
        self.sysblock = self.root / 'sys/class/block'
        self.sysblock.mkdir(parents=True)
        self.partitions.mkdir(parents=True)
        self.package.mkdir(parents=True)
        self.release = '7.4.0-caihong-test'
        (self.package / 'kernel-release').write_text(self.release + '\n')
        self.cmdline = self.root / 'cmdline'
        self.cmdline.write_text('root=PARTLABEL=userdata rootfstype=ext4 slot_suffix=_b rw\n')
        self.slotfile = self.root / 'boot-slot'
        self.slotfile.write_text('b\n')
        self.offline = self.root / 'offline'
        self.devices = {}
        for name, number in (('boot_a', 1), ('boot_b', 2), ('userdata', 14)):
            device = self.root / f'dev/sda{number}'
            device.write_bytes(b'Android does not boot this root')
            (self.partitions / name).symlink_to(device)
            self.devices[name] = device
            sysdev = self.root / f'sys/devices/block/sda/sda{number}'
            sysdev.mkdir(parents=True)
            (sysdev / 'partition').write_text(str(number))
            (self.sysblock / device.name).symlink_to(sysdev)
        self.image = self.package / 'boot-userdata.img'
        self.image.write_bytes(self.boot_image())
        self.devices['boot_b'].write_bytes(self.image.read_bytes() + b'\0' * 4096)
        self.private = self.package / 'modules' / self.release
        self.private.mkdir(parents=True)
        for name, data in {
            'kernel/test.ko': b'vermagic=' + self.release.encode() + b' SMP\0',
            'modules.order': b'kernel/test.ko\n',
            'modules.builtin': b'kernel/root.ko\n',
            'modules.builtin.modinfo': b'root.vermagic=' + self.release.encode(),
            'modules.dep': b'kernel/test.ko:\n', 'modules.dep.bin': b'dep-index',
            'modules.alias': b'alias test test\n', 'modules.alias.bin': b'alias-index',
        }.items():
            path = self.private / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        shutil.copytree(self.private, self.runtime / self.release)
        self.attrs = {'1': 'GUID:48,49,51', '2': 'GUID:48,49,50,51'}
        self.calls = []
        stack = ExitStack()
        self.addCleanup(stack.close)
        for key, value in {
            'PACKAGE': self.package, 'PARTITIONS': self.partitions,
            'CMDLINE': self.cmdline, 'SLOT_FILE': self.slotfile,
            'OFFLINE': self.offline, 'SYS_BLOCK': self.sysblock, 'MODULES': self.runtime,
        }.items():
            stack.enter_context(patch.object(BOOT, key, value))
        stack.enter_context(patch.object(BOOT, 'live_platform'))
        stack.enter_context(patch.object(BOOT, 'block_device', side_effect=lambda path: path.resolve()))
        stack.enter_context(patch.object(BOOT, 'command', side_effect=self.read_command))
        # The installed NEXT-BOOT release intentionally differs from uname -r.
        stack.enter_context(patch.object(BOOT.os, 'uname', return_value=SimpleNamespace(
            machine='aarch64', release='7.3.0-old-running-kernel')))

    def boot_image(self, label='userdata', release=None):
        kernel = b'Linux version ' + (release or self.release).encode() + b' build-test\0'
        header = bytearray(2048)
        header[:8] = b'ANDROID!'
        for offset, value in ((8, len(kernel)), (36, 2048), (40, 2), (1644, 1660), (1648, 4)):
            struct.pack_into('<I', header, offset, value)
        cmdline = f'root=PARTLABEL={label} rootfstype=ext4 rootwait rw'.encode()
        header[64:64 + len(cmdline)] = cmdline
        return bytes(header) + kernel.ljust(2048, b'\0') + b'DTB!'

    def read_command(self, *args):
        self.calls.append(args)
        if args[:3] == ('/usr/bin/findmnt', '-nro', 'FSTYPE'):
            return 'ext4'
        if args[:3] == ('/usr/bin/findmnt', '-nro', 'SOURCE'):
            return str(self.devices['userdata'])
        if args[:3] == ('/usr/bin/findmnt', '-nro', 'MAJ:MIN'):
            return '0:0'  # File-backed fixture only; production requires S_ISBLK.
        if args[:2] == ('/usr/bin/blkid', '-s'):
            return 'userdata'
        if args[:2] == ('/usr/bin/sfdisk', '--part-attrs') and len(args) == 4:
            return self.attrs[args[-1]]
        if args[:2] == ('/usr/bin/blockdev', '--getsize64'):
            return str(self.devices['boot_b'].stat().st_size)
        self.fail(f'verifier attempted a non-read-only or unexpected command: {args}')

    def snapshot(self):
        return {str(path.relative_to(self.root)): (path.lstat().st_mode, path.read_bytes())
                for path in self.root.rglob('*') if path.is_file() and not path.is_symlink()}

    def test_next_boot_new_kernel_verified_without_mutation(self):
        before = self.snapshot()
        BOOT.verify()
        self.assertEqual(before, self.snapshot())
        self.assertTrue(any(call[:2] == ('/usr/bin/sfdisk', '--part-attrs') for call in self.calls))

    def test_missing_running_slot_refused_even_when_other_slot_matches_package(self):
        self.slotfile.unlink()
        self.cmdline.write_text('root=PARTLABEL=userdata rootfstype=ext4 rw\n')
        self.devices['boot_a'].write_bytes(self.image.read_bytes())
        self.devices['boot_b'].write_bytes(self.boot_image(release='7.3.0-old-running-kernel'))
        before = self.snapshot()
        with self.assertRaisesRegex(BOOT.Refusal, 'missing running boot slot'):
            BOOT.resolve()
        self.assertEqual(before, self.snapshot())

    def test_running_slot_accepts_either_saved_or_command_line_identity(self):
        self.devices['boot_a'].write_bytes(self.image.read_bytes())
        self.devices['boot_b'].write_bytes(self.boot_image(release='7.3.0-old-running-kernel'))
        for source in ('saved', 'cmdline'):
            with self.subTest(source=source):
                if source == 'saved':
                    self.cmdline.write_text('root=PARTLABEL=userdata rootfstype=ext4 rw\n')
                else:
                    self.slotfile.unlink()
                    self.cmdline.write_text('root=PARTLABEL=userdata rootfstype=ext4 slot_suffix=_b rw\n')
                slot, _label, _image, target, _release = BOOT.resolve()
                self.assertEqual((slot, target), ('b', self.devices['boot_b'].resolve()))

    def test_wrong_boot_bytes_fail_without_mutation(self):
        data = bytearray(self.devices['boot_b'].read_bytes())
        data[2050] ^= 1
        self.devices['boot_b'].write_bytes(data)
        before = self.snapshot()
        with self.assertRaisesRegex(BOOT.Refusal, 'differs from installed'):
            BOOT.verify()
        self.assertEqual(before, self.snapshot())

    def test_wrong_root_payload_refused(self):
        self.image.write_bytes(self.boot_image(label='linux'))
        with self.assertRaisesRegex(BOOT.Refusal, 'payload root'):
            BOOT.verify()

    def test_wrong_kernel_release_refused(self):
        self.image.write_bytes(self.boot_image(release='7.2.0-wrong'))
        with self.assertRaisesRegex(BOOT.Refusal, 'module release'):
            BOOT.verify()

    def test_missing_or_wrong_runtime_module_refused(self):
        module = self.runtime / self.release / 'kernel/test.ko'
        module.unlink()
        with self.assertRaisesRegex(BOOT.Refusal, 'module payload'):
            BOOT.verify()
        module.write_bytes(b'incorrect module')
        with self.assertRaisesRegex(BOOT.Refusal, 'module payload'):
            BOOT.verify()

    def test_missing_dependency_index_refused(self):
        (self.runtime / self.release / 'modules.dep.bin').unlink()
        with self.assertRaisesRegex(BOOT.Refusal, 'dependency index'):
            BOOT.verify()

    def test_next_boot_android_slot_refused(self):
        self.attrs = {'1': 'GUID:50', '2': ''}
        with self.assertRaisesRegex(BOOT.Refusal, 'next boot selects another slot'):
            BOOT.verify()

    def test_ambiguous_missing_and_unbootable_active_slot_refused(self):
        for attrs in ({'1': 'GUID:50', '2': 'GUID:50'}, {'1': '', '2': ''},
                      {'1': '', '2': 'GUID:50,55'}):
            with self.subTest(attrs=attrs):
                self.attrs = attrs
                with self.assertRaises(BOOT.Refusal):
                    BOOT.verify()

    def test_conflicting_saved_and_cmdline_slots_refused(self):
        self.slotfile.write_text('a\n')
        with self.assertRaisesRegex(BOOT.Refusal, 'contradictory'):
            BOOT.verify()

    def test_conflicting_command_line_slots_refused(self):
        self.cmdline.write_text(self.cmdline.read_text() + ' androidboot.slot_suffix=_a')
        with self.assertRaisesRegex(BOOT.Refusal, 'contradictory'):
            BOOT.verify()

    def test_live_platform_refuses_offline_marker(self):
        self.offline.touch()
        original = load('boot_state_original', 'packaging/linux-caihong/boot-state')
        with patch.object(original, 'OFFLINE', self.offline):
            with self.assertRaisesRegex(original.Refusal, 'offline'):
                original.live_platform()

    def test_production_block_guard_refuses_regular_file(self):
        original = load('boot_state_original', 'packaging/linux-caihong/boot-state')
        with self.assertRaisesRegex(original.Refusal, 'not a block device'):
            original.block_device(self.image)


class EntrypointTests(unittest.TestCase):
    def test_readonly_flags_never_activate_modules_even_when_offline_skip_is_set(self):
        source = (PROJECT / 'packaging/linux-caihong/install-current-slot').read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'package'
            package.mkdir()
            mutation = root / 'MUTATED'
            # Instrument only the destructive function, retaining all real flag
            # dispatch/offline control flow. No test can write host module paths.
            source = source.replace('package_dir=/usr/lib/linux-caihong', f'package_dir={package}')
            source = source.replace('$(id -u)', '0')
            source = source.replace('activate_modules()\n{',
                                    f'activate_modules()\n{{\n echo mutation > "{mutation}"; return 0\n')
            entry = root / 'install-current-slot'
            entry.write_text(source)
            helper = package / 'boot-state'
            helper.write_text('#!/bin/sh\nexit 42\n')
            helper.chmod(0o755)
            (package / 'kernel-release').write_text('test\n')
            for mode in ('--verify', '--detect'):
                with self.subTest(mode=mode):
                    result = subprocess.run(['/bin/sh', str(entry), mode], capture_output=True,
                                            env={**os.environ, 'CAIHONG_SKIP_BOOT_FLASH': '1'})
                    self.assertEqual(result.returncode, 42, result.stderr)
                    self.assertFalse(mutation.exists())

    def test_all_unsupported_workflows_refuse_before_changes(self):
        for operation in LIFECYCLE.UNSUPPORTED:
            with self.subTest(operation=operation), patch.object(LIFECYCLE.sys, 'argv', [operation]), \
                 patch.object(LIFECYCLE, 'platform') as platform, \
                 patch.object(LIFECYCLE.subprocess, 'run') as run:
                with self.assertRaisesRegex(LIFECYCLE.Refusal, 'unsupported'):
                    LIFECYCLE.main()
                platform.assert_not_called()
                run.assert_not_called()

    def test_failed_boot_preflight_prevents_service_mutations(self):
        with patch.object(LIFECYCLE, 'verify_boot', side_effect=LIFECYCLE.Refusal('bad boot')), \
             patch.object(LIFECYCLE, 'systemctl') as systemctl:
            with self.assertRaisesRegex(LIFECYCLE.Refusal, 'bad boot'):
                LIFECYCLE.setup_system()
            systemctl.assert_not_called()

    def test_system_setup_enables_board_services_without_restarting_sessions(self):
        with patch.object(LIFECYCLE, 'verify_boot'), patch.object(Path, 'is_file', return_value=True), \
             patch.object(Path, 'exists', return_value=False), \
             patch.object(Path, 'is_symlink', return_value=False), \
             patch.object(LIFECYCLE, 'systemctl', return_value=SimpleNamespace(stdout='disabled\n')) as ctl:
            LIFECYCLE.setup_system()
        mutations = [call.args for call in ctl.call_args_list if call.args[0] != 'is-enabled']
        self.assertEqual(mutations, [('enable', *LIFECYCLE.SYSTEM_UNITS),
                                     ('set-default', 'graphical.target')])
        self.assertFalse(any('--now' in call.args for call in ctl.call_args_list))

    def test_masked_hardware_service_refuses_before_service_mutations(self):
        def status(*args, **kwargs):
            state = 'masked' if args[1] == 'caihong-keyboard.service' else 'disabled'
            return SimpleNamespace(stdout=state + '\n')

        with patch.object(LIFECYCLE, 'verify_boot'), patch.object(Path, 'is_file', return_value=True), \
             patch.object(Path, 'exists', return_value=False), \
             patch.object(Path, 'is_symlink', return_value=False), \
             patch.object(LIFECYCLE, 'systemctl', side_effect=status) as ctl:
            with self.assertRaisesRegex(LIFECYCLE.Refusal, 'masked'):
                LIFECYCLE.setup_system()
        self.assertTrue(all(call.args[0] == 'is-enabled' for call in ctl.call_args_list))

    def test_user_setup_is_idempotent_and_preserves_existing_config(self):
        template = 'hl.config({ input = { touchdevice = { output = "@OUTPUT@" } } })\n'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / '.config/hypr/hyprland.lua'
            config.parent.mkdir(parents=True)
            original = '-- personal configuration\nhl.config({ input = { kb_layout = "us" } })\n'
            config.write_text(original)
            original_is_file = Path.is_file
            original_read_text = Path.read_text

            def is_file(path):
                return str(path) == '/usr/share/omarchy-caihong/hyprland.lua' or original_is_file(path)

            def read_text(path, *args, **kwargs):
                if str(path) == '/usr/share/omarchy-caihong/hyprland.lua':
                    return template
                return original_read_text(path, *args, **kwargs)

            with patch.dict(os.environ, {'HOME': str(root), 'XDG_CONFIG_HOME': str(root / '.config')}), \
                 patch.object(LIFECYCLE, 'trusted_executable'), patch.object(LIFECYCLE, 'internal_output', return_value='DSI-1'), \
                 patch.object(Path, 'is_file', is_file), patch.object(Path, 'read_text', read_text):
                LIFECYCLE.setup_user()
                once = config.read_text()
                LIFECYCLE.setup_user()
            self.assertTrue(once.startswith(original))
            self.assertEqual(once, config.read_text())
            self.assertEqual(once.count('require("hypr.caihong")'), 1)
            self.assertIn('output = "DSI-1"', (root / '.config/hypr/caihong.lua').read_text())

    def test_user_setup_leaves_config_alone_without_an_internal_panel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / '.config/hypr/hyprland.lua'
            config.parent.mkdir(parents=True)
            original = '-- personal configuration\n'
            config.write_text(original)
            original_is_file = Path.is_file

            def is_file(path):
                return str(path) == '/usr/share/omarchy-caihong/hyprland.lua' or original_is_file(path)

            with patch.dict(os.environ, {'HOME': str(root), 'XDG_CONFIG_HOME': str(root / '.config')}), \
                 patch.object(LIFECYCLE, 'trusted_executable'), patch.object(LIFECYCLE, 'internal_output', return_value=None), \
                 patch.object(Path, 'is_file', is_file):
                LIFECYCLE.setup_user()
            self.assertEqual(config.read_text(), original)
            self.assertFalse((root / '.config/hypr/caihong.lua').exists())


if __name__ == '__main__':
    unittest.main()

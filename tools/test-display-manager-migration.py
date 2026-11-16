#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Osilvfe <osilvfe@gmail.com>

from pathlib import Path
import os
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / 'packaging/caihong-platform/switch-display-manager.sh'


SYSTEMCTL = '''\
#!/bin/sh
set -eu
root=
action=
unit=
for argument in "$@"; do
	case $argument in
		--root=*) root=${argument#--root=} ;;
		enable|disable|is-enabled) action=$argument ;;
		*) unit=$argument ;;
	esac
done
[ -n "$root" ] || exit 2
alias=$root/etc/systemd/system/display-manager.service
case $action in
	is-enabled)
		[ -L "$root/etc/systemd/system/graphical.target.wants/$unit" ] ||
			[ -e "$root/etc/systemd/system/graphical.target.wants/$unit" ] ||
			[ -L "$root/etc/systemd/system/multi-user.target.wants/$unit" ] ||
			[ -e "$root/etc/systemd/system/multi-user.target.wants/$unit" ]
		;;
	disable)
		[ "$unit" = plasmalogin.service ] || exit 2
		find "$root/etc/systemd/system" -type l | while IFS= read -r link; do
			case $(readlink "$link") in
				plasmalogin.service|*/plasmalogin.service) rm "$link" ;;
			esac
		done
		printf 'disable %s\\n' "$unit" >> "$COMMAND_LOG"
		;;
	enable)
		[ "$unit" = sddm.service ] || exit 2
		[ -e "$root/usr/lib/systemd/system/$unit" ] || exit 1
		mkdir -p "$root/etc/systemd/system"
		if [ -L "$alias" ]; then
			case $(readlink "$alias") in
				sddm.service|*/sddm.service) ;;
				*) exit 1 ;;
			esac
		else
			ln -s /usr/lib/systemd/system/sddm.service "$alias"
		fi
		printf 'enable %s\\n' "$unit" >> "$COMMAND_LOG"
		;;
	*) exit 2 ;;
esac
'''


class DisplayManagerMigrationTests(unittest.TestCase):
    def setUp(self):
        output = PROJECT.parent / 'build/caihong-display-manager-tests'
        output.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=output)
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.root = self.work / 'root'
        self.bin = self.work / 'bin'
        self.log = self.work / 'commands.log'
        self.root.mkdir()
        self.bin.mkdir()
        self.alias = self.root / 'etc/systemd/system/display-manager.service'
        self.alias.parent.mkdir(parents=True)

        systemctl = self.bin / 'fake-systemctl'
        systemctl.write_text(SYSTEMCTL)
        systemctl.chmod(0o755)
        self.environment = dict(
            os.environ,
            CAIHONG_PLATFORM_ROOT=str(self.root),
            CAIHONG_SYSTEMCTL=str(systemctl),
            COMMAND_LOG=str(self.log),
            CAIHONG_PLATFORM_UPDATE_INSTALL='1',
            CAIHONG_PLATFORM_SKIP_DISPLAY_MANAGER='0',
            CAIHONG_PLATFORM_IMAGE_BUILD='0',
        )

    def install_arch(self):
        pacman = self.root / 'usr/bin/pacman'
        pacman.parent.mkdir(parents=True)
        # Only an executable marker is needed for distribution detection.
        pacman.touch(mode=0o755)

    def install_service(self, unit):
        service = self.root / 'usr/lib/systemd/system' / unit
        service.parent.mkdir(parents=True, exist_ok=True)
        service.write_text('[Unit]\n[Install]\nAlias=display-manager.service\n')

    def select(self, unit):
        if self.alias.is_symlink():
            self.alias.unlink()
        self.alias.symlink_to('/usr/lib/systemd/system/' + unit)

    def directly_enable(self, unit, target='graphical.target'):
        wants = self.alias.parent / (target + '.wants')
        wants.mkdir(parents=True, exist_ok=True)
        link = wants / unit
        link.symlink_to('/usr/lib/systemd/system/' + unit)
        return link

    def commands(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def run_script(self):
        return subprocess.run(
            ['sh', str(SCRIPT)],
            env=self.environment,
            text=True,
            capture_output=True,
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_native_transaction_migrates_plm_without_restarting_sessions(self):
        self.install_arch()
        self.install_service('sddm.service')
        self.install_service('plasmalogin.service')
        self.select('plasmalogin.service')
        links = [self.directly_enable('plasmalogin.service', target)
                 for target in ('graphical.target', 'multi-user.target')]

        self.assert_success(self.run_script())
        self.assertEqual(self.alias.readlink(), Path('/usr/lib/systemd/system/sddm.service'))
        self.assertTrue(all(not link.is_symlink() for link in links))
        self.assertEqual(self.commands(), ['disable plasmalogin.service', 'enable sddm.service'])
        self.assertTrue((self.root / 'usr/lib/systemd/system/plasmalogin.service').exists())

    def test_empty_selection_enables_sddm_without_plm_installed(self):
        self.install_arch()
        self.install_service('sddm.service')

        self.assert_success(self.run_script())
        self.assertEqual(self.alias.readlink(), Path('/usr/lib/systemd/system/sddm.service'))
        self.assertEqual(self.commands(), ['enable sddm.service'])

    def test_existing_sddm_selection_is_preserved_and_plm_is_disabled(self):
        self.install_arch()
        self.install_service('sddm.service')
        self.install_service('plasmalogin.service')
        target = Path('../../../usr/lib/systemd/system/sddm.service')
        self.alias.symlink_to(target)
        link = self.directly_enable('plasmalogin.service')

        for _ in range(2):
            self.assert_success(self.run_script())
            self.assertEqual(self.alias.readlink(), target)
            self.assertFalse(link.is_symlink())
        self.assertEqual(self.commands(), ['disable plasmalogin.service', 'enable sddm.service'] * 2)

    def test_existing_sddm_without_plm_is_preserved(self):
        self.install_arch()
        self.install_service('sddm.service')
        self.select('sddm.service')

        self.assert_success(self.run_script())
        self.assertEqual(self.alias.readlink(), Path('/usr/lib/systemd/system/sddm.service'))
        self.assertEqual(self.commands(), ['enable sddm.service'])

    def test_directly_enabled_plm_with_empty_selection_is_disabled(self):
        self.install_arch()
        self.install_service('sddm.service')
        self.install_service('plasmalogin.service')
        link = self.directly_enable('plasmalogin.service')

        self.assert_success(self.run_script())
        self.assertFalse(link.is_symlink())
        self.assertEqual(self.alias.readlink(), Path('/usr/lib/systemd/system/sddm.service'))

    def test_missing_sddm_dependency_preserves_existing_alias_and_enablement(self):
        self.install_arch()
        self.install_service('plasmalogin.service')
        self.select('plasmalogin.service')
        link = self.directly_enable('plasmalogin.service')

        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('sddm dependency', result.stderr)
        self.assertEqual(self.alias.readlink(), Path('/usr/lib/systemd/system/plasmalogin.service'))
        self.assertTrue(link.is_symlink())
        self.assertEqual(self.commands(), [])

    def test_non_arch_target_is_left_alone(self):
        self.select('plasmalogin.service')

        self.assert_success(self.run_script())
        self.assertEqual(self.alias.readlink(), Path('/usr/lib/systemd/system/plasmalogin.service'))
        self.assertEqual(self.commands(), [])

    def test_administrator_selected_display_manager_is_preserved(self):
        self.install_arch()
        for unit in ('ly.service', 'gdm.service'):
            with self.subTest(unit=unit):
                self.select(unit)
                self.assert_success(self.run_script())
                self.assertEqual(self.alias.readlink(), Path('/usr/lib/systemd/system/' + unit))
                self.assertEqual(self.commands(), [])

    def test_administrator_provided_display_manager_unit_is_preserved(self):
        self.install_arch()
        self.alias.write_text('[Unit]\nDescription=Custom display manager\n')

        self.assert_success(self.run_script())
        self.assertEqual(self.alias.read_text(), '[Unit]\nDescription=Custom display manager\n')
        self.assertEqual(self.commands(), [])

    def test_directly_enabled_third_party_manager_is_preserved(self):
        self.install_arch()
        self.install_service('sddm.service')
        self.install_service('plasmalogin.service')
        plm_link = self.directly_enable('plasmalogin.service')
        for target in ('graphical.target', 'multi-user.target'):
            alternative = self.directly_enable('ly.service', target)
            for selected in ('sddm.service', 'plasmalogin.service', None):
                with self.subTest(target=target, selected=selected):
                    if self.alias.is_symlink():
                        self.alias.unlink()
                    if selected:
                        self.select(selected)
                    self.assert_success(self.run_script())
                    if selected:
                        self.assertEqual(self.alias.readlink(),
                                         Path('/usr/lib/systemd/system/' + selected))
                    else:
                        self.assertFalse(self.alias.is_symlink())
                    self.assertTrue(alternative.is_symlink())
                    self.assertTrue(plm_link.is_symlink())
                    self.assertEqual(self.commands(), [])
            alternative.unlink()

    def test_migration_is_skipped_outside_update_or_during_image_build(self):
        self.install_arch()
        self.install_service('sddm.service')
        self.install_service('plasmalogin.service')
        self.select('plasmalogin.service')
        for key in ('CAIHONG_PLATFORM_UPDATE_INSTALL', 'CAIHONG_PLATFORM_SKIP_DISPLAY_MANAGER',
                    'CAIHONG_PLATFORM_IMAGE_BUILD'):
            original = self.environment[key]
            self.environment[key] = '0' if key == 'CAIHONG_PLATFORM_UPDATE_INSTALL' else '1'
            with self.subTest(key=key):
                self.assert_success(self.run_script())
                self.assertEqual(self.alias.readlink(),
                                 Path('/usr/lib/systemd/system/plasmalogin.service'))
                self.assertEqual(self.commands(), [])
            self.environment[key] = original

    def test_offline_image_build_marker_skips_migration(self):
        self.install_arch()
        self.select('plasmalogin.service')
        marker = self.root / 'run/caihong/offline-rootfs-build'
        marker.parent.mkdir(parents=True)
        marker.touch()

        self.assert_success(self.run_script())
        self.assertEqual(self.alias.readlink(), Path('/usr/lib/systemd/system/plasmalogin.service'))
        self.assertEqual(self.commands(), [])


if __name__ == '__main__':
    unittest.main()

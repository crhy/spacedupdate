#!/usr/bin/python3
"""Behavior tests: command fixtures never install or change host packages."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from test_spaced_update import MODULE, SOURCE


class DiscoveryTests(unittest.TestCase):
    def test_selected_multiarch_packages_keep_their_architecture(self):
        output = ('libexample/ceres 2 amd64 [upgradable from: 1]\n'
                  'libexample/ceres 2 i386 [upgradable from: 1]\n')
        with mock.patch.object(MODULE, 'run_capture', return_value=output):
            items = MODULE.enumerate_apt()
        self.assertEqual([item['package'] for item in items],
                         ['libexample:amd64', 'libexample:i386'])

    def capture(self, command, timeout=60):
        if command[1] == 'list':
            self.assertIn('--all', command)
            return ('org.example.User\tuser\torg.example.User/x86_64/stable\tUser App\n'
                    'org.example.Platform\tsystem\torg.example.Platform/x86_64/50\tPlatform\n'
                    'org.example.Private\textra\torg.example.Private/x86_64/stable\tPrivate App\n')
        if command[1] == 'remotes':
            return 'flathub\nprivate\tno-enumerate\nexpired\nremoved\tdisabled\n'
        if command[1] == 'remote-ls':
            self.assertIn('--all', command)
            self.assertNotIn('removed', command)
            if 'expired' in command:
                raise RuntimeError('summary unavailable')
            if '--user' in command:
                return 'app/org.example.User/x86_64/stable\n'
            if '--system' in command:
                return 'runtime/org.example.Platform/x86_64/50\n'
            if '--installation=extra' in command and 'private' in command:
                return 'app/org.example.Private/x86_64/stable\n'
            return ''
        self.fail(f'Unexpected command: {command}')

    def test_apps_runtimes_private_and_named_installations_with_visible_errors(self):
        warnings = []
        with mock.patch.object(MODULE, 'flatpak_available', return_value=True), \
             mock.patch.object(MODULE, 'run_capture', side_effect=self.capture):
            items = MODULE.enumerate_flatpak(warnings)
        self.assertEqual({item['scope'] for item in items}, {'user', 'system', 'extra'})
        self.assertEqual(len(items), 3)
        self.assertEqual(len(warnings), 3)
        self.assertIn('summary unavailable', warnings[0])

    def test_partial_failure_never_returns_unqualified_success(self):
        with mock.patch.object(MODULE, 'flatpak_available', return_value=True), \
             mock.patch.object(MODULE, 'run_capture', side_effect=self.capture):
            with self.assertRaisesRegex(RuntimeError, 'summary unavailable'):
                MODULE.enumerate_flatpak()

    def test_localized_environment_for_native_and_host_commands(self):
        for sandbox in (False, True):
            with self.subTest(sandbox=sandbox), \
                 mock.patch.dict(os.environ, {'LC_ALL': 'fr_FR.UTF-8',
                     **({'FLATPAK_ID': 'org.spacedlinux.SpacedUpdate'} if sandbox else {})}, clear=True), \
                 mock.patch.object(MODULE.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='', stderr='')) as run:
                MODULE.run_capture(['apt', 'list', '--upgradable'])
                self.assertEqual(run.call_args.kwargs['env']['LC_ALL'], 'C')
                if sandbox:
                    self.assertEqual(run.call_args.args[0][:3], ['flatpak-spawn', '--host', '--env=LC_ALL=C'])

    def test_os_version_timeout_becomes_unknown(self):
        with mock.patch.dict(os.environ, {'FLATPAK_ID': 'test'}), \
             mock.patch.object(MODULE, 'run_capture', side_effect=subprocess.TimeoutExpired('cat', 15)):
            self.assertIsNone(MODULE.read_installed_version())

    def test_authentication_cancellation_is_distinct_from_failure(self):
        with self.assertRaises(MODULE.UpdateCancelled):
            MODULE.check_status(126)
        with self.assertRaisesRegex(RuntimeError, 'status 1'):
            MODULE.check_status(1)
        MODULE.check_status(0)


class WorkerTests(unittest.TestCase):
    def app(self):
        return SimpleNamespace(os_tab=mock.Mock(), run_cmd=mock.Mock(return_value=0),
                               _set_busy=mock.Mock())

    def test_full_update_always_runs_user_flatpaks_after_privileged_helper(self):
        app = self.app()
        with mock.patch.object(MODULE.GLib, 'idle_add', side_effect=lambda f, *args: f(*args)), \
             mock.patch.object(MODULE, 'flatpak_available', return_value=True), \
             mock.patch.object(MODULE, 'enumerate_apt', return_value=[]), \
             mock.patch.object(MODULE, 'read_installed_version', return_value='9.26'):
            MODULE.App._os_update_worker(app)
        self.assertEqual(app.run_cmd.call_args_list[0].args[0], ['pkexec', MODULE.HELPER])
        self.assertEqual(app.run_cmd.call_args_list[1].args[0],
                         ['flatpak', 'update', '--noninteractive', '-y', '--user'])
        app.os_tab.finish_update.assert_called_once_with('9.26', [])
        app._set_busy.assert_called_once_with(False)

    def test_failed_user_flatpak_never_reports_system_complete(self):
        app = self.app()
        app.run_cmd.side_effect = [0, 1]
        with mock.patch.object(MODULE.GLib, 'idle_add', side_effect=lambda f, *args: f(*args)), \
             mock.patch.object(MODULE, 'flatpak_available', return_value=True):
            MODULE.App._os_update_worker(app)
        app.os_tab.finish_update.assert_not_called()
        self.assertEqual(app.os_tab.set_message.call_args.args[1], 'System update failed')
        app._set_busy.assert_called_once_with(False)

    def test_failed_helper_stops_before_user_updates_and_allows_retry(self):
        app = self.app()
        app.run_cmd.return_value = 75
        with mock.patch.object(MODULE.GLib, 'idle_add', side_effect=lambda f, *args: f(*args)):
            MODULE.App._os_update_worker(app)
        self.assertEqual(app.run_cmd.call_count, 1)
        app.os_tab.finish_update.assert_not_called()
        app._set_busy.assert_called_once_with(False)

    def test_check_refreshes_apt_but_keeps_flatpak_results_when_apt_fails(self):
        app = SimpleNamespace(_check_done=mock.Mock())
        packages = [{'kind': 'flatpak'}]
        with mock.patch.object(MODULE.GLib, 'idle_add', side_effect=lambda f, *args: f(*args)), \
             mock.patch.object(MODULE, 'run_capture', side_effect=RuntimeError('offline')) as run, \
             mock.patch.object(MODULE, 'enumerate_apt') as apt, \
             mock.patch.object(MODULE, 'enumerate_flatpak', return_value=packages):
            MODULE.App._check_worker(app)
        self.assertEqual(run.call_args.args[0], ['pkexec', MODULE.HELPER, 'apt-refresh'])
        apt.assert_not_called()
        self.assertEqual(app._check_done.call_args.args[:2], ([], packages))
        self.assertIn('offline', app._check_done.call_args.args[2])

    def test_deferred_packages_are_reported(self):
        app = self.app()
        with mock.patch.object(MODULE.GLib, 'idle_add', side_effect=lambda f, *args: f(*args)), \
             mock.patch.object(MODULE, 'flatpak_available', return_value=False), \
             mock.patch.object(MODULE, 'enumerate_apt', return_value=[{'name': 'held'}]), \
             mock.patch.object(MODULE, 'read_installed_version', return_value='9.26'):
            MODULE.App._os_update_worker(app)
        self.assertIn('remain held or deferred', app.os_tab.finish_update.call_args.args[1][0])


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.helper = self.root / 'spaced-update-helper'
        # Substitute only the lock pathname; all real package commands are
        # replaced by fixture executables in PATH before invoking this copy.
        self.helper.write_text((SOURCE.parent / 'spaced-update-helper').read_text().replace(
            '/run/lock/spaced-update.lock', str(self.root / 'lock')))
        stub = self.root / 'command-stub'
        stub.write_text('''#!/usr/bin/python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['COMMAND_LOG'], 'a') as out:
    out.write(json.dumps([name] + args) + '\\n')
if name == os.environ.get('FAIL_COMMAND') and (not os.environ.get('FAIL_ARG') or os.environ['FAIL_ARG'] in args):
    print('fixture failure: ' + name)
    sys.exit(42)
if name == 'dpkg-query': print('installed', end='')
if name == 'apt-get' and '--simulate' in args: print(os.environ.get('APT_PLAN', 'Inst libexample [1] (2 Devuan:ceres [amd64])'))
if name == 'flatpak' and 'list' in args: print('system\\nextra\\nextra')
if name == 'apt-mark': print(os.environ.get('HELD', ''))
''')
        stub.chmod(0o755)
        for name in ('apt-get', 'dpkg-query', 'dpkg', 'flatpak', 'apt-mark', 'update-initramfs', 'update-grub'):
            (self.root / name).symlink_to(stub)
        self.log = self.root / 'commands.jsonl'
        self.env = {**os.environ, 'PATH': f'{self.root}:/usr/bin:/bin', 'COMMAND_LOG': str(self.log)}

    def run_helper(self, *args, **env):
        result = subprocess.run(['bash', str(self.helper), *args], env={**self.env, **env},
                                capture_output=True, text=True, timeout=10)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, calls

    def test_all_upgrades_download_then_install_without_automatic_removal(self):
        result, calls = self.run_helper('all')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        apt = [call for call in calls if call[0] == 'apt-get']
        self.assertIn('APT::Update::Error-Mode=any', apt[0])
        self.assertIn('DPkg::Lock::Timeout=120', apt[0])
        self.assertIn('Acquire::Retries=3', apt[0])
        transactions = [call for call in apt if 'dist-upgrade' in call]
        self.assertEqual(len(transactions), 3)
        self.assertTrue(all('spaced-meta' in call for call in transactions))
        self.assertIn('--simulate', transactions[0])
        self.assertIn('--download-only', transactions[1])
        self.assertNotIn('--download-only', transactions[2])
        self.assertFalse(any('autoremove' in call or 'clean' in call for call in calls))
        flatpaks = [call for call in calls if call[:2] == ['flatpak', 'update']]
        self.assertEqual(flatpaks, [['flatpak', 'update', '--noninteractive', '-y', '--system'],
                                   ['flatpak', 'update', '--noninteractive', '-y', '--installation=extra']])
        self.assertLess([c[0] for c in calls].index('update-initramfs'), [c[0] for c in calls].index('update-grub'))

    def test_refresh_failure_never_installs_or_claims_success(self):
        result, calls = self.run_helper('all', FAIL_COMMAND='apt-get', FAIL_ARG='update')
        self.assertEqual(result.returncode, 42)
        self.assertEqual(len(calls), 1)
        self.assertNotIn('SPACED_STEP:100:', result.stdout)

    def test_failed_download_does_not_start_package_install(self):
        result, calls = self.run_helper('all', FAIL_COMMAND='apt-get', FAIL_ARG='--download-only')
        self.assertEqual(result.returncode, 42)
        self.assertFalse(any('dist-upgrade' in c and '--simulate' not in c and '--download-only' not in c for c in calls))

    def test_failed_system_flatpak_is_propagated(self):
        result, calls = self.run_helper('all', FAIL_COMMAND='flatpak', FAIL_ARG='update')
        self.assertEqual(result.returncode, 42)
        self.assertNotIn('SPACED_STEP:100:', result.stdout)

    def test_core_removal_and_init_switch_are_refused(self):
        for plan in ('Remv sysvinit-core [3.0]', 'Remv mate-panel [1.26]', 'Inst systemd-sysv (260)', 'Inst systemd (260)'):
            with self.subTest(plan=plan):
                self.log.unlink(missing_ok=True)
                result, calls = self.run_helper('all', APT_PLAN=plan)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Refusing', result.stdout)
                self.assertFalse(any('--download-only' in c for c in calls))

    def test_selected_upgrade_cannot_remove_packages(self):
        result, calls = self.run_helper('apt-install', 'libexample:amd64')
        self.assertEqual(result.returncode, 0, result.stdout)
        for call in calls:
            if 'install' in call:
                self.assertIn('--only-upgrade', call)
                self.assertIn('--no-remove', call)

    def test_rejects_apt_remove_suffix_and_flatpak_option_injection(self):
        for args in (('apt-install', 'apt-'), ('apt-install', '--allow-remove-essential'),
                     ('flatpak-update', '--system', '--commit=bad'),
                     ('flatpak-update', '--user', 'org.example.App/x86_64/stable')):
            with self.subTest(args=args):
                result, _ = self.run_helper(*args)
                self.assertEqual(result.returncode, 2)

    def test_lock_prevents_a_second_transaction(self):
        with (self.root / 'lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result, calls = self.run_helper('all')
        self.assertEqual(result.returncode, 75)
        self.assertEqual(calls, [])

    def test_retry_completes_pending_dpkg_configuration(self):
        result, _ = self.run_helper('all', FAIL_COMMAND='dpkg')
        self.assertEqual(result.returncode, 42)
        self.log.unlink()
        result, calls = self.run_helper('all')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(['dpkg', '--force-confdef', '--force-confold', '--configure', '--pending'], calls)

    def test_admin_holds_are_visible(self):
        result, _ = self.run_helper('all', HELD='linux-image-amd64')
        self.assertEqual(result.returncode, 0)
        self.assertIn('SPACED_WARNING:', result.stdout)
        self.assertIn('linux-image-amd64', result.stdout)


@unittest.skipUnless(MODULE.Gtk.init_check()[0], 'GTK display required')
class InterfaceTests(unittest.TestCase):
    def setUp(self):
        with mock.patch.object(MODULE, 'read_installed_version', return_value='8.26.4'):
            self.app = MODULE.App()
        # Avoid ending an unrelated main loop when disposing this test window.
        self.addCleanup(self.app.hide)

    def test_full_update_is_available_without_release_feed(self):
        self.assertTrue(self.app.os_tab.updatebtn.get_sensitive())
        self.app.os_tab._check_done(None, RuntimeError('GitHub unavailable'))
        self.assertTrue(self.app.os_tab.updatebtn.get_sensitive())

    def test_shared_busy_state_blocks_concurrent_update_and_close(self):
        self.app._set_busy(True)
        self.assertFalse(self.app.os_tab.updatebtn.get_sensitive())
        self.assertFalse(self.app.header_refresh.get_sensitive())
        self.assertTrue(self.app._on_close())
        with mock.patch.object(MODULE.threading, 'Thread') as thread:
            self.app.do_os_update()
            self.app.do_install()
            self.app.do_check()
        thread.assert_not_called()
        self.app._set_busy(False)
        self.assertTrue(self.app.os_tab.updatebtn.get_sensitive())
        self.assertFalse(self.app._on_close())

    def test_late_release_feed_does_not_replace_update_status(self):
        self.app._set_busy(True)
        self.app.os_tab.message_title.set_text('Updating packages')
        self.app.os_tab._check_done('9.26', None)
        self.assertEqual(self.app.os_tab.latest_release, '9.26')
        self.assertEqual(self.app.os_tab.message_title.get_text(), 'Updating packages')


if __name__ == '__main__':
    unittest.main()

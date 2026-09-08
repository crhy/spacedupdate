"""Validate APT's final transaction protocol; no host packages are changed."""
from pathlib import Path
import subprocess
import unittest


GUARD = Path(__file__).parents[1] / 'src/spaced-update-apt-guard'


class ActualTransactionTests(unittest.TestCase):
    def run_guard(self, actions, header='VERSION 2\nAPT::Architecture=amd64\n\n'):
        return subprocess.run(['bash', str(GUARD)], input=header + actions,
                              text=True, capture_output=True, timeout=5)

    def test_protected_removal_is_refused(self):
        for package in ('sysvinit-core', 'spaced-meta', 'mate-panel', 'caja', 'lightdm', 'apt', 'dpkg', 'flatpak', 'network-manager'):
            with self.subTest(package=package):
                result = self.run_guard(f'{package} 1 > - **REMOVE**\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Refusing removal', result.stderr)

    def test_init_install_and_pending_configuration_are_refused(self):
        for package in ('systemd', 'systemd-sysv', 'runit-init', 'openrc'):
            for action in ('/var/cache/apt/archives/init.deb', '**CONFIGURE**'):
                with self.subTest(package=package, action=action):
                    result = self.run_guard(f'{package} - < 1 {action}\n')
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('sysvinit', result.stderr)

    def test_core_upgrades_and_noncore_rolling_removals_are_allowed(self):
        result = self.run_guard('mate-panel 1 < 2 /var/cache/apt/archives/panel_2.deb\n'
                                'mate-panel 1 < 2 **CONFIGURE**\n'
                                'libold 1 > - **REMOVE**\n'
                                'systemd-sysv 1 > - **REMOVE**\n')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_foreign_architecture_does_not_bypass_package_policy(self):
        result = self.run_guard('mate-panel:amd64 1 > - **REMOVE**\n')
        self.assertNotEqual(result.returncode, 0)
        result = self.run_guard('libgraphics:i386 1 < 2 /cache/libgraphics_2_i386.deb\n')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unexpected_protocol_and_truncated_records_fail_closed(self):
        for header, action in (('', ''), ('VERSION 3\n\n', ''), ('VERSION 2\nIncomplete', ''),
                               ('VERSION 2\n\n', 'mate-panel 1 > -\n'),
                               ('VERSION 2\n\n', 'mate-panel 1 ? - **REMOVE**\n'),
                               ('VERSION 2\n\n', 'mate-panel 1 > - **REMOVE** extra\n')):
            with self.subTest(header=header, action=action):
                self.assertNotEqual(self.run_guard(action, header).returncode, 0)


if __name__ == '__main__':
    unittest.main()

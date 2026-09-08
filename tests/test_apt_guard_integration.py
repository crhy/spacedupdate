"""Run real APT against private metadata and a fake dpkg, without root."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

from test_apt_guard import GUARD


@unittest.skipUnless(shutil.which('apt-get') and shutil.which('dpkg-deb'), 'APT tools required')
class AptHookIntegrationTests(unittest.TestCase):
    def test_actual_apt_removal_is_rejected_before_dpkg_changes(self):
        with tempfile.TemporaryDirectory(prefix='spaced-apt-hook-') as directory:
            root = Path(directory)
            stage = root / 'deb/DEBIAN'
            stage.mkdir(parents=True)
            (stage / 'control').write_text(
                'Package: spaced-guard-fixture\nVersion: 1\nArchitecture: all\n'
                'Maintainer: Spaced Tests <tests@example.invalid>\n'
                'Conflicts: mate-panel\nDescription: isolated APT guard fixture\n')
            deb = root / 'fixture.deb'
            subprocess.run(['dpkg-deb', '--build', str(stage.parent), str(deb)],
                           check=True, capture_output=True, text=True)
            status = root / 'status'
            status.write_text('Package: mate-panel\nStatus: install ok installed\n'
                              'Priority: optional\nSection: x11\nArchitecture: all\n'
                              'Version: 1\nDescription: private fixture only\n\n')
            for name in ('empty', 'lists/partial', 'archives/partial', 'log'):
                (root / name).mkdir(parents=True)
            fake_dpkg = root / 'dpkg'
            fake_dpkg.write_text('''#!/bin/sh
case " $* " in
  *" --unpack "*|*" --remove "*|*" --configure "*|*" --purge "*)
    echo unexpected-package-change >> "$SPACED_TEST_DPKG_LOG" ;;
esac
exit 0
''')
            fake_dpkg.chmod(0o755)
            dpkg_log = root / 'dpkg.log'
            options = {
                'Dir': str(root), 'Dir::State::status': str(status),
                'Dir::State::lists': str(root / 'lists'),
                'Dir::State::extended_states': str(root / 'extended-states'),
                'Dir::Cache::archives': str(root / 'archives'),
                'Dir::Cache::pkgcache': '', 'Dir::Cache::srcpkgcache': '',
                'Dir::Etc::main': '/dev/null', 'Dir::Etc::parts': str(root / 'empty'),
                'Dir::Etc::sourcelist': '/dev/null', 'Dir::Etc::sourceparts': str(root / 'empty'),
                'Dir::Etc::preferences': '/dev/null', 'Dir::Etc::preferencesparts': str(root / 'empty'),
                'Dir::Log': str(root / 'log'), 'Dir::Bin::dpkg': str(fake_dpkg),
                'Debug::NoLocking': 'true',
                'DPkg::Pre-Install-Pkgs::': str(GUARD),
                f'DPkg::Tools::Options::{GUARD}::Version': '2',
            }
            command = ['apt-get']
            for key, value in options.items():
                command.extend(['-o', f'{key}={value}'])
            result = subprocess.run(command + ['-y', 'install', str(deb)],
                                    env={**os.environ, 'LC_ALL': 'C', 'APT_CONFIG': '/dev/null',
                                         'SPACED_TEST_DPKG_LOG': str(dpkg_log)},
                                    capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Refusing removal of a core Spaced Linux package: mate-panel', result.stderr)
            self.assertFalse(dpkg_log.exists(), 'APT invoked fake dpkg changes before the guard stopped it')
            self.assertIn('Status: install ok installed', status.read_text())


if __name__ == '__main__':
    unittest.main()

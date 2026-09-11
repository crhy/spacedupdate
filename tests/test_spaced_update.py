#!/usr/bin/python3
import importlib.util
import json
import os
from pathlib import Path
from subprocess import CompletedProcess
import unittest
from unittest import mock
import xml.etree.ElementTree as ET


SOURCE = Path(__file__).resolve().parents[1] / "src" / "spaced-update.py"
SPEC = importlib.util.spec_from_file_location("spaced_update", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CoreTests(unittest.TestCase):
    def test_version_key_orders_release_tags(self):
        self.assertLess(MODULE.version_key("v8.26.4"), MODULE.version_key("8.26.5"))
        self.assertLess(MODULE.version_key("v8.26.9"), MODULE.version_key("9.26"))
        self.assertLess(MODULE.version_key("v9.26"), MODULE.version_key("9.26.1"))
        self.assertEqual(MODULE.version_key(None), (0, 0, 0))

    def test_version_key_orders_across_the_year_boundary(self):
        # The month wraps, so 1.27 opens the line after 12.26. Comparing the
        # numbers as written would make every 2027 release look older than
        # 12.26 and the OS tab would report a year-old system as current.
        self.assertLess(MODULE.version_key("v12.26"), MODULE.version_key("1.27"))
        self.assertLess(MODULE.version_key("v12.26"), MODULE.version_key("2.27"))
        self.assertLess(MODULE.version_key("v12.26"), MODULE.version_key("9.27"))
        self.assertLess(MODULE.version_key("v1.27"), MODULE.version_key("12.27"))
        self.assertLess(MODULE.version_key("v11.26"), MODULE.version_key("12.26"))
        # A newer line is never mistaken for an older one in either direction.
        self.assertGreater(MODULE.version_key("v1.27"), MODULE.version_key("12.26.3"))

    def test_flatpak_reads_installed_version_from_host_once(self):
        completed = CompletedProcess(
            [], 0, stdout='NAME="Spaced Linux"\nVERSION_ID="8.26.9"\n', stderr=""
        )
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed) as run, \
             mock.patch.dict(
                 os.environ,
                 {"FLATPAK_ID": "org.spacedlinux.SpacedUpdate"},
                 clear=True,
             ):
            self.assertEqual(MODULE.read_installed_version(), "8.26.9")

        self.assertEqual(
            run.call_args.args[0],
            ["flatpak-spawn", "--host", "--env=LC_ALL=C", "cat", "/etc/os-release"],
        )

    def test_about_dialog_uses_repository_license(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("about.set_license_type(Gtk.License.MIT_X11)", source)
        self.assertIn(
            'about.set_logo_icon_name("org.spacedlinux.SpacedUpdate")', source
        )
        self.assertNotIn('about.set_logo_icon_name("system-software-update")', source)

    def test_native_and_flatpak_use_the_dedicated_update_icon(self):
        root = SOURCE.parents[1]
        icon_name = "org.spacedlinux.SpacedUpdate"
        native_desktop = (root / "data" / "spaced-update.desktop").read_text()
        flatpak_desktop = (
            root / "flatpak" / "data" / f"{icon_name}.desktop"
        ).read_text()
        manifest = json.loads(
            (root / "flatpak" / f"{icon_name}.json").read_text()
        )
        commands = "\n".join(manifest["modules"][0]["build-commands"])

        self.assertIn(f"Icon={icon_name}", native_desktop)
        self.assertIn(f"Icon={icon_name}", flatpak_desktop)
        self.assertIn(f"hicolor/512x512/apps/{icon_name}.png", commands)
        icon = root / "data" / "icons" / f"{icon_name}.png"
        self.assertTrue(icon.is_file())
        self.assertEqual(icon.read_bytes()[16:24], b"\x00\x00\x02\x00\x00\x00\x02\x00")

    def test_flatpak_uses_supported_runtime(self):
        manifest_path = (
            SOURCE.parents[1]
            / "flatpak"
            / "org.spacedlinux.SpacedUpdate.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["runtime-version"], "50")
        self.assertEqual(
            [module["name"] for module in manifest["modules"]],
            ["spaced-update"],
        )
        self.assertNotIn("--filesystem=home", manifest["finish-args"])
        self.assertNotIn(
            "--system-talk-name=org.freedesktop.PolicyKit1",
            manifest["finish-args"],
        )
        self.assertIn(
            "--talk-name=org.freedesktop.Flatpak",
            manifest["finish-args"],
        )

    def test_flatpak_exports_searchable_appstream_metadata(self):
        root = SOURCE.parents[1]
        manifest = json.loads(
            (root / "flatpak" / "org.spacedlinux.SpacedUpdate.json").read_text(
                encoding="utf-8"
            )
        )
        commands = "\n".join(manifest["modules"][0]["build-commands"])
        metainfo_path = (
            root
            / "flatpak"
            / "data"
            / "org.spacedlinux.SpacedUpdate.metainfo.xml"
        )
        metainfo = ET.parse(metainfo_path).getroot()

        self.assertIn("/app/share/metainfo/org.spacedlinux.SpacedUpdate.metainfo.xml", commands)
        self.assertEqual(metainfo.findtext("id"), "org.spacedlinux.SpacedUpdate")
        self.assertEqual(
            metainfo.find("./releases/release").attrib["version"],
            MODULE.APP_VERSION,
        )

    def test_enumerate_apt_parses_and_sorts(self):
        output = """Listing... Done
zlib1g/ceres 1:1.3.2 amd64 [upgradable from: 1:1.3.1]
apt/ceres 3.1.0 amd64 [upgradable from: 3.0.3]
"""
        with mock.patch.object(MODULE, "run_capture", return_value=output):
            items = MODULE.enumerate_apt()
        self.assertEqual([item["name"] for item in items], ["apt", "zlib1g"])
        self.assertEqual(items[0]["cur"], "3.0.3")
        self.assertEqual(items[0]["new"], "3.1.0")

    def test_enumerate_flatpak_returns_empty_when_unavailable(self):
        with mock.patch.object(MODULE.shutil, "which", return_value=None), \
             mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(MODULE.enumerate_flatpak(), [])



if __name__ == "__main__":
    unittest.main()

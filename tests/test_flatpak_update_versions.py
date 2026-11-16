#!/usr/bin/python3
"""Flatpak update discovery compares versions, not origin remotes (issue #16).

The fixtures are this machine's real answers: ``io.github.crhy.SpacedBazaar``
is installed twice (user ``0.1.14``, system ``0.1.15``), its recorded origin
remote ``spacedbazaar-origin`` exists only in the system scope, and Flatpak's
own update query prints nothing for the shared ``spaced-github`` remote even
though that remote carries ``0.1.15``. Nothing here touches the host's Flatpak
installation: every command is mocked.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "src" / "spaced-update.py"
SPEC = importlib.util.spec_from_file_location(
    "spaced_update_flatpak_versions", SOURCE
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


BAZAAR_USER_ROW = (
    "io.github.crhy.SpacedBazaar\tuser\t"
    "app/io.github.crhy.SpacedBazaar/x86_64/master\tSpacedBazaar\n"
)
BAZAAR_SYSTEM_ROW = (
    "io.github.crhy.SpacedBazaar\tsystem\t"
    "app/io.github.crhy.SpacedBazaar/x86_64/master\tSpacedBazaar\n"
)
# spacedbazaar-origin, the remote the user install records as its origin, is
# absent from this listing, which is why the old ref-matching code found nothing.
USERREMOTES = (
    "brutal-local\tno-gpg-verify\n"
    "flathub\n"
    "spaced-github\n"
    "brutalchess1-origin\tno-enumerate,no-gpg-verify\n"
    "coinkittywallet-origin\tno-enumerate,no-gpg-verify\n"
)
SPACED_GITHUB_CARRIES = "io.github.crhy.SpacedBazaar\tmaster\t0.1.15\n"


class Conversation:
    """Answers the flatpak commands enumerate_flatpak asks, in host shape."""

    def __init__(self, rows="", installs=None, remotes=None, listings=None, failing=()):
        self.rows = rows
        self.installs = installs or {}
        self.remotes = remotes or {}
        self.listings = listings or {}
        self.failing = set(failing)
        self.commands = []
        self.timeouts = []
        self.list_calls = 0

    def run(self, command, timeout=60):
        self.commands.append(command)
        self.timeouts.append(timeout)
        scope = next(
            (arg for arg in command if arg in ("--user", "--system")), "--unknown"
        )
        if command[1] == "list":
            self.list_calls += 1
            if "--columns=application,installation,ref,name" in command:
                return self.rows
            return self.installs.get(scope, "")
        if command[1] == "remotes":
            return self.remotes.get(scope, "")
        if command[1] == "remote-ls":
            key = (scope, command[2])
            if key in self.failing:
                raise RuntimeError("error: Remote origin not found")
            return self.listings.get(key, "")
        raise AssertionError(f"Unexpected command: {command}")


class FlatpakVersionDiscoveryTests(unittest.TestCase):
    def test_newer_version_from_a_remote_that_is_not_the_origin_is_offered(self):
        conversation = Conversation(
            rows=BAZAAR_USER_ROW,
            installs={"--user": "io.github.crhy.SpacedBazaar\tmaster\t0.1.14\n"},
            remotes={"--user": USERREMOTES},
            listings={("--user", "spaced-github"): SPACED_GITHUB_CARRIES},
        )
        with mock.patch.object(MODULE, "flatpak_available", return_value=True), \
             mock.patch.object(MODULE, "run_capture", side_effect=conversation.run):
            items = MODULE.enumerate_flatpak()
        self.assertEqual(
            [(item["name"], item["scope"]) for item in items],
            [("io.github.crhy.SpacedBazaar", "user")],
        )
        self.assertEqual(
            items[0]["ref"], "app/io.github.crhy.SpacedBazaar/x86_64/master"
        )
        self.assertEqual(
            items[0]["display"], "SpacedBazaar"
        )
        self.assertIn(
            [
                "flatpak",
                "remote-ls",
                "spaced-github",
                "--user",
                "--columns=application,branch,version",
            ],
            conversation.commands,
        )
        # The display rows still come from one listing; versions add one listing
        # per installation, never one per application.
        self.assertEqual(conversation.list_calls, 2)

    def test_both_installations_are_compared_against_their_own_remotes(self):
        conversation = Conversation(
            rows=BAZAAR_USER_ROW + BAZAAR_SYSTEM_ROW,
            installs={
                "--user": "io.github.crhy.SpacedBazaar\tmaster\t0.1.14\n",
                "--system": "io.github.crhy.SpacedBazaar\tmaster\t0.1.15\n",
            },
            remotes={"--user": USERREMOTES, "--system": "spaced-github\n"},
            listings={
                ("--user", "spaced-github"): SPACED_GITHUB_CARRIES,
                ("--system", "spaced-github"): SPACED_GITHUB_CARRIES,
            },
        )
        with mock.patch.object(MODULE, "flatpak_available", return_value=True), \
             mock.patch.object(MODULE, "run_capture", side_effect=conversation.run):
            items = MODULE.enumerate_flatpak()
        self.assertEqual([item["scope"] for item in items], ["user"])

    def test_equal_version_is_not_offered(self):
        conversation = Conversation(
            rows=BAZAAR_USER_ROW,
            installs={"--user": SPACED_GITHUB_CARRIES},
            remotes={"--user": "spaced-github\n"},
            listings={("--user", "spaced-github"): SPACED_GITHUB_CARRIES},
        )
        with mock.patch.object(MODULE, "flatpak_available", return_value=True), \
             mock.patch.object(MODULE, "run_capture", side_effect=conversation.run):
            self.assertEqual(MODULE.enumerate_flatpak(), [])

    def test_older_remote_version_is_not_offered(self):
        conversation = Conversation(
            rows=BAZAAR_USER_ROW,
            installs={"--user": "io.github.crhy.SpacedBazaar\tmaster\t0.1.15\n"},
            remotes={"--user": "spaced-github\n"},
            listings={
                ("--user", "spaced-github"): "io.github.crhy.SpacedBazaar\tmaster\t0.1.14\n"
            },
        )
        with mock.patch.object(MODULE, "flatpak_available", return_value=True), \
             mock.patch.object(MODULE, "run_capture", side_effect=conversation.run):
            self.assertEqual(MODULE.enumerate_flatpak(), [])

    def test_unreachable_remote_warns_and_still_offers_other_results(self):
        conversation = Conversation(
            rows=BAZAAR_USER_ROW,
            installs={"--user": "io.github.crhy.SpacedBazaar\tmaster\t0.1.14\n"},
            remotes={"--user": USERREMOTES},
            listings={("--user", "spaced-github"): SPACED_GITHUB_CARRIES},
            failing={("--user", "flathub")},
        )
        warnings = []
        stats = {}
        with mock.patch.object(MODULE, "flatpak_available", return_value=True), \
             mock.patch.object(MODULE, "run_capture", side_effect=conversation.run):
            items = MODULE.enumerate_flatpak(warnings, stats)
        self.assertEqual(
            [item["name"] for item in items], ["io.github.crhy.SpacedBazaar"]
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("user/flathub", warnings[0])
        self.assertIn("Remote origin not found", warnings[0])
        self.assertEqual(stats, {"remotes_total": 5, "remotes_failed": 1})

    def test_unreachable_remote_without_a_warning_list_still_raises(self):
        conversation = Conversation(
            rows=BAZAAR_USER_ROW,
            installs={"--user": "io.github.crhy.SpacedBazaar\tmaster\t0.1.14\n"},
            remotes={"--user": "flathub\n"},
            failing={("--user", "flathub")},
        )
        with mock.patch.object(MODULE, "flatpak_available", return_value=True), \
             mock.patch.object(MODULE, "run_capture", side_effect=conversation.run):
            with self.assertRaisesRegex(RuntimeError, "Remote origin not found"):
                MODULE.enumerate_flatpak()

    def test_disabled_remote_is_never_consulted(self):
        conversation = Conversation(
            rows=BAZAAR_USER_ROW,
            installs={"--user": "io.github.crhy.SpacedBazaar\tmaster\t0.1.14\n"},
            remotes={"--user": "spaced-github\nstale-origin\tdisabled\n"},
            listings={("--user", "spaced-github"): SPACED_GITHUB_CARRIES},
        )
        with mock.patch.object(MODULE, "flatpak_available", return_value=True), \
             mock.patch.object(MODULE, "run_capture", side_effect=conversation.run):
            items = MODULE.enumerate_flatpak()
        self.assertEqual([item["name"] for item in items], ["io.github.crhy.SpacedBazaar"])
        self.assertFalse(
            any("stale-origin" in command for command in conversation.commands)
        )

    def test_remote_versions_reads_application_branch_version(self):
        conversation = Conversation(
            listings={
                ("--user", "spaced-github"): (
                    "io.github.crhy.SpacedBazaar\tmaster\t0.1.15\n"
                    "io.github.crhy.voxa\tmaster\t0.1.8\n"
                )
            }
        )
        with mock.patch.object(MODULE, "run_capture", side_effect=conversation.run):
            versions = MODULE.remote_versions("user", "spaced-github")
        self.assertEqual(
            versions,
            {
                ("io.github.crhy.SpacedBazaar", "master"): "0.1.15",
                ("io.github.crhy.voxa", "master"): "0.1.8",
            },
        )
        self.assertEqual(
            conversation.commands,
            [
                [
                    "flatpak",
                    "remote-ls",
                    "spaced-github",
                    "--user",
                    "--columns=application,branch,version",
                ]
            ],
        )
        self.assertEqual(conversation.timeouts, [90])

    def test_installed_versions_uses_one_listing_per_installation(self):
        conversation = Conversation(
            installs={"--user": "io.github.crhy.SpacedBazaar\tmaster\t0.1.14\n"}
        )
        with mock.patch.object(MODULE, "run_capture", side_effect=conversation.run):
            versions = MODULE.installed_versions("user")
        self.assertEqual(
            versions, {("io.github.crhy.SpacedBazaar", "master"): "0.1.14"}
        )
        self.assertEqual(
            conversation.commands,
            [
                [
                    "flatpak",
                    "list",
                    "--all",
                    "--user",
                    "--columns=application,branch,version",
                ]
            ],
        )

    def test_release_versions_order_as_calendar_then_patch(self):
        self.assertLess(MODULE.version_key("0.1.14"), MODULE.version_key("0.1.15"))
        self.assertLess(MODULE.version_key("9.26"), MODULE.version_key("10.26"))
        self.assertLess(MODULE.version_key("10.26"), MODULE.version_key("1.27"))

    def test_branch_is_read_from_an_installed_ref(self):
        self.assertEqual(
            MODULE.ref_branch("app/io.github.crhy.SpacedBazaar/x86_64/master"),
            "master",
        )
        self.assertEqual(
            MODULE.ref_branch("runtime/org.freedesktop.Platform/x86_64/26.08"),
            "26.08",
        )
        self.assertEqual(
            MODULE.ref_branch("org.example.User/x86_64/stable"), "stable"
        )
        self.assertEqual(MODULE.ref_branch("io.github.crhy.SpacedBazaar"), "")


if __name__ == "__main__":
    unittest.main()

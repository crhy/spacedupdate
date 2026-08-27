# Changelog

## 0.1.5 - 2026-08-27

- Added a dedicated polished silver update icon instead of reusing the generic
  Spaced medallion.
- Use the same update identity in SpacedBazaar, desktop menus, native installs,
  Flatpak exports, and the About dialog.

## 0.1.4 - 2026-08-27

- Add the current OS Release screenshot to AppStream metadata so SpacedBazaar
  can show a real preview before installation.
- Replace the flat update glyph with the canonical silver Spaced emblem at a
  true 512px desktop and software-center size.
- Use that same silver application icon in the About dialog instead of the
  desktop theme's yellow generic updater glyph.

## 0.1.3 - 2026-08-27

### Fixed

- Read the host Spaced Linux release through exactly one Flatpak host bridge,
  so the OS Release tab displays the installed version instead of `Unknown`.

### Added

- Regression coverage for the sandboxed host release-marker command and its
  parsed version.

## 0.1.2 - 2026-08-27

### Fixed

- Export complete AppStream metadata from the Flatpak so SpacedBazaar and
  other stores can index, search, and display Spaced Update from the new
  shared Spaced GitHub repository.

### Added

- Validate the Flatpak application ID and release version directly from the
  exported metainfo in the deterministic test suite.

### Changed

- Adopt an independent semantic version for Spaced Update so application
  releases are clear and no longer confused with Spaced Linux releases.

## 8.26.4.0.2 - 2026-08-15

### Fixed

- The Flatpak build now continues after finding `flatpak` on the host instead
  of returning an empty update list from inside its sandbox.
- Flatpak update discovery now compares normalized refs per installation scope
  and queries remotes independently, so one stale or private remote no longer
  hides updates from every healthy remote.
- Header icon actions now use quiet transparent surfaces with compact
  hover/focus feedback instead of raised square toolbar boxes.
- The About dialog now reports the repository's actual MIT license, and the
  Flatpak documentation accurately describes its required Spaced host helper.

### Added

- Unit coverage for version ordering, APT parsing, native no-Flatpak behavior,
  sandboxed host discovery, per-scope refs, and failed-remote isolation.

### Changed

- Move the Flatpak from the end-of-life GNOME 48 runtime to GNOME 50 and use
  its maintained Python/PyGObject stack instead of bundling a duplicate Python.
- Prefer the native `flatpak-builder` release path when it is available while
  retaining the Builder-app fallback.

## 8.26.4.0.1 - 2026-08-11

### Added

- About button in the header bar showing the Spaced Update version
  (also displayed in the window subtitle).
- The version lives in `VERSION` and `APP_VERSION` in
  `src/spaced-update.py`.

### Changed

- Released as the org.spacedlinux.SpacedUpdate Flatpak (Python 3.13 +
  PyGObject built from source, bundled Spaced themes, flatpak-spawn --host).

## 8.26.3 - 2026-08-10

### Changed

- Rebuilt the GTK interface around a focused Updates / OS Release layout with
  theme-aware cards, clearer status messaging, larger controls, and a single
  primary action.
- Replaced the Progress / CLI mode selector with a polished staged-progress
  view and one collapsed, scrollable Technical details panel.
- Added friendly empty, checking, current, available, success, and error states.
- Improved package rows with update type, human-readable Flatpak names, version
  transitions, precise selection counts, and ellipsized long labels.
- Made repository and release-check failures visible instead of presenting them
  as an up-to-date result.
- Hardened helper modes: reject invalid or empty requests, reject unknown modes,
  and report selected Flatpak failures accurately.

### Fixed

- The OS tab now rereads `/etc/os-release` after a full system update and
  reports the newly installed Spaced Linux release without an app restart.
- A successful APT run no longer claims a release upgrade when the configured
  repository has not delivered the newer `spaced-meta` release marker.
- User Flatpak updates no longer force the interface into a CLI-only view.
- Technical output now has one shared buffer instead of duplicate log panes.
- Scrollbars appear only where content can actually overflow.

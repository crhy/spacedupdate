# Changelog

## Unreleased

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

- User Flatpak updates no longer force the interface into a CLI-only view.
- Technical output now has one shared buffer instead of duplicate log panes.
- Scrollbars appear only where content can actually overflow.

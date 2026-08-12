# Spaced Update issue triage

Reviewed on 2026-08-10 for the Spaced Linux 8.26 stabilization pass.

## Implemented in this pass

- [#3 — graphical install progress](https://github.com/crhy/spacedupdate/issues/3):
  replaced the Progress / CLI selector with a clear staged-progress view. Raw
  command output remains available in a collapsed, scrollable Technical details
  panel. The empty, update-list, current, failure, and OS-release states were
  also redesigned and tested under the current Spaced dark theme.
- [#10 — OS update does not report the updated OS](https://github.com/crhy/spacedupdate/issues/10):
  the OS tab now rereads the installed release marker after APT completes. It
  reports the new version immediately, or clearly says that packages updated
  while the configured repository's release marker remained behind.
- [#12 — No Flatpak?](https://github.com/crhy/spacedupdate/issues/12): the app
  is now released as `org.spacedlinux.SpacedUpdate`, a self-contained Flatpak
  built from `flatpak/org.spacedlinux.SpacedUpdate.json` with Python 3.13,
  PyGObject, and the bundled Spaced themes. APT, Flatpak, and the pkexec
  helper run through `flatpak-spawn --host`, so the sandbox behaves like the
  native app. `flatpak/build.sh` builds the OSTree repository and
  `flatpak/publish.sh` publishes it to GitHub Pages.
- [#11 — stupid boxes on buttons](https://github.com/crhy/spacedupdate/issues/11):
  the app now carries explicit flattened button styling (radius, outline
  borders, hover/disabled states) so buttons match the modern Spaced theme on
  every host theme; the theme's shared rules were also fixed to use
  relocatable imports instead of absolute `/usr/share/themes` paths.

## Deferred feature work

- [#2 — P2P update sharing](https://github.com/crhy/spacedupdate/issues/2),
  [#4 — privacy protection](https://github.com/crhy/spacedupdate/issues/4), and
  [#5 — anonymous file sharing](https://github.com/crhy/spacedupdate/issues/5)
  require a threat model and protocol design before implementation.
- [#6 — theme browser](https://github.com/crhy/spacedupdate/issues/6) and
  [#7 — app suggestions and ratings](https://github.com/crhy/spacedupdate/issues/7)
  are larger product features and are outside the updater's 8.26 visual and
  reliability pass.

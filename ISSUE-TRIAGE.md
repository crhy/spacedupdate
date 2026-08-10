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

## Deferred feature work

- [#2 — P2P update sharing](https://github.com/crhy/spacedupdate/issues/2),
  [#4 — privacy protection](https://github.com/crhy/spacedupdate/issues/4), and
  [#5 — anonymous file sharing](https://github.com/crhy/spacedupdate/issues/5)
  require a threat model and protocol design before implementation.
- [#6 — theme browser](https://github.com/crhy/spacedupdate/issues/6) and
  [#7 — app suggestions and ratings](https://github.com/crhy/spacedupdate/issues/7)
  are larger product features and are outside the updater's 8.26 visual and
  reliability pass.

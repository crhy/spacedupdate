# Spaced Update

The update application for [Spaced Linux](https://spacedlinux.com).

Spaced Update updates Spaced Linux systems through **APT** and **Flathub** in a
single, simple GTK interface. Package and Flatpak operations run as root via
`pkexec` against a small helper script, with a live progress and log view.

## What it does today

- **Check for Updates** lists every available APT package and Flatpak
  application update with a checkbox for each, plus a **Select all** toggle.
- **Install Selected** applies only the packages/apps you check, using the
  helper's `apt-install` and `flatpak-update` subcommands with per-step
  progress. (The default helper run still does a full
  `dist-upgrade` + system Flatpak + boot menu + initramfs refresh.)
- Shows step-by-step progress and a scrollable live log, switchable between a
  **Progress** view and a real **CLI output** view from a drop-down.
- Runs the privileged steps through the Polkit action
  `com.spacedlinux.update` so the helper is policy-controlled.

## Full OS update

The **OS Update** tab checks the `crhy/spaced` release feed for the newest
Spaced Linux version and compares it against the installed `/etc/os-release`
version. Spaced Linux is a rolling release, so OS updates are applied from the
package repositories via the existing update helper — no ISO download is needed.
The tab simply tells you whether your system is current and routes the actual
update through the normal `dist-upgrade` path, with a reboot recommendation
when done.

## Layout

```
bin/spaced-update                # launcher: runs the GTK app
src/spaced-update.py             # GTK3 UI and worker
src/spaced-update-helper         # privileged bash helper (pkexec)
data/spaced-update.desktop       # desktop entry
data/com.spacedlinux.update.policy  # Polkit policy for the helper
```

## How it is installed on Spaced Linux

- `src/spaced-update.py` -> `/usr/lib/spaced-linux/spaced-update.py`
- `src/spaced-update-helper` -> `/usr/lib/spaced-linux/spaced-update-helper`
- `bin/spaced-update` -> `/usr/local/bin/spaced-update`
- `data/spaced-update.desktop` -> `/usr/share/applications/spaced-update.desktop`
- `data/com.spacedlinux.update.policy` -> `/usr/share/polkit-1/actions/com.spacedlinux.update.policy`

## Roadmap

Planned features are tracked as GitHub issues. See the
[issue tracker](https://github.com/crhy/spacedupdate/issues) for:

- Full integration with Spaced Linux OS updates.
- Peer-to-peer updating and Flatpak distribution.
- A beautiful, simplified graphical install progress view (with a real CLI
  available via a drop-down).
- Anonymity and privacy protection for shared data.
- Password-protected anonymous file sharing.
- A browsable, rating-driven theme browser.
- App suggestions, ratings, reviews, and metrics as a Bazaar alternative.

## License

MIT — see [LICENSE](LICENSE).
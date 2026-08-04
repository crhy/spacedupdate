# Spaced Update

The update application for [Spaced Linux](https://spacedlinux.com).

Spaced Update updates Spaced Linux systems through **APT** and **Flathub** in a
single, simple GTK interface. Package and Flatpak operations run as root via
`pkexec` against a small helper script, with a live progress and log view.

## What it does today

- Refreshes APT package lists and applies `dist-upgrade`.
- Removes obsolete APT packages (`autoremove --purge`) and cleans the cache.
- Updates system Flatpaks.
- Repairs boot menu entries (`update-grub`).
- Refreshes the initramfs (`update-initramfs -u -k all`).
- Updates the current user's Flatpak applications.
- Shows step-by-step progress and a scrollable live log.
- Runs the privileged steps through the Polkit action
  `com.spacedlinux.update` so the helper is policy-controlled.

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
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
- Shows a clear overall progress bar and named update stages. The real command
  output remains available in a collapsed, scrollable **Technical details**
  panel when it is useful, without taking over the normal experience.
- Uses one adaptive, theme-aware interface for both light and dark Spaced Linux
  themes, with readable update cards and full-size action targets.
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

## Flatpak release

Spaced Update is also published as a Flatpak (`org.spacedlinux.SpacedUpdate`)
as an alternate UI package for Spaced Linux systems. Inside the sandbox, APT,
Flatpak, and the pkexec helper are reached through `flatpak-spawn --host`, so
the interface behaves exactly like the system app; privileged work still runs
through the host's Polkit policy. The host must therefore carry Spaced Linux's
`spaced-update-helper` and Polkit action; the Flatpak is not a generic updater
for unrelated distributions.

- **Build**: `bash flatpak/build.sh` — produces a static OSTree repository in
  `flatpak-build/repo` (supported GNOME runtime plus bundled Spaced themes so
  the app matches the desktop on any host).
- **Publish**: `bash flatpak/publish.sh` — pushes the repository to the
  `gh-pages` branch for serving at `https://crhy.github.io/spacedupdate/flatpak-repo`.
- **Install from the published remote**:
  ```
  flatpak --user remote-add --if-not-exists --no-gpg-verify spacedupdate \
      https://crhy.github.io/spacedupdate/flatpak-repo
  flatpak --user install spacedupdate org.spacedlinux.SpacedUpdate
  flatpak run org.spacedlinux.SpacedUpdate
  ```
  The repository is unsigned and uses `--no-gpg-verify`, mirroring the
  `[trusted=yes]` Spaced Linux apt repository.

On Spaced Linux, the native package remains the primary install; the Flatpak
is the alternate application-delivery path.

## Development checks

Run the deterministic source tests and syntax checks on a Spaced Linux host:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile src/spaced-update.py tests/test_spaced_update.py
bash -n src/spaced-update-helper install.sh flatpak/build.sh flatpak/publish.sh
```

## Roadmap

Planned features are tracked as GitHub issues. See the
[issue tracker](https://github.com/crhy/spacedupdate/issues) and the current
[triage notes](ISSUE-TRIAGE.md) for:

- Full integration with Spaced Linux OS updates.
- Peer-to-peer updating and Flatpak distribution.
- Further refinements to the graphical install progress experience.
- Anonymity and privacy protection for shared data.
- Password-protected anonymous file sharing.
- A browsable, rating-driven theme browser.
- App suggestions, ratings, reviews, and metrics as a Bazaar alternative.

## License

MIT — see [LICENSE](LICENSE).

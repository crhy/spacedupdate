# Privacy and anonymity threat model for Spaced Update

Scope: this is the threat model required by
[#4 — privacy protection](https://github.com/crhy/spacedupdate/issues/4). It is the
**precondition** for any anonymity or privacy feature in the updater: no peer transport,
anonymity control, or anonymous file-sharing UI may be implemented until the control it
proposes appears in this document and can be tested. It replaces the phrase "anonymous
and untraceable" in that issue with something checkable.

**Status: documentation only.** Nothing described below is implemented. `src/spaced-update.py`
and `src/spaced-update-helper` are unchanged by this document, and the implementation stays
blocked behind it in [#2](https://github.com/crhy/spacedupdate/issues/2) and
[#5](https://github.com/crhy/spacedupdate/issues/5).

Line numbers are as of `origin/HEAD` = `fb849f5`; each call site is also named by function
so it stays findable when the file moves.

## What the updater actually sends, and to whom

The whole outbound surface is three kinds of traffic:

1. one unauthenticated GET to `https://api.github.com/repos/crhy/spaced/releases/latest`
   (`src/spaced-update.py:17`, requested at `:1222-1230`);
2. APT traffic to the origins configured on the node, triggered by the helper's
   `apt-refresh` (`src/spaced-update.py:787` → `src/spaced-update-helper:80`) and by the
   install/upgrade transactions (`:941` → helper `:92`, `:96`);
3. Flatpak traffic to each enabled remote of the installation the app lives in
   (`src/spaced-update.py:282` `enumerate_flatpak`, `:325-335` `remote-ls`, and the update
   paths at `:952` `run_flatpak_update("--user", …)` and `:1058`
   `flatpak update … --user`).

There is no fourth kind. The app opens no other connection, and `install.sh` makes none.
`flatpak/build.sh` and `flatpak/publish.sh` do reach the network, but they run on a
maintainer's machine at release time, not on a user's node, and are out of scope here.

## Observer table

| Observer | What it may learn | Which call site reveals it | What the updater prevents today | What the updater cannot prevent today |
|---|---|---|---|---|
| **Publisher / GitHub** (`api.github.com`) | Your IP address; the exact time you checked for updates; that this machine runs Spaced Update and polls the `crhy/spaced` release feed; the fixed `User-Agent: spaced-update` and `Accept: application/vnd.github+json` headers. It does **not** learn your app selections, package list, version, hostname or any identifier. | `src/spaced-update.py:17` defines the URL; `:1222-1230` (`OSTab._check_worker`) sends one `urllib.request` GET with `timeout=30`, no cookie, no token. | No authentication, no cookie, no session state, no machine identifier, no installed-app list in the request; no telemetry or crash ping; a failed request is reported and never retried silently. | That GitHub keeps its own access logs, or how long it keeps them; that the request's timing is not correlated with your other GitHub traffic; your IP at all — the request has to come from somewhere. |
| **APT origins** (the signed Spaced archive plus any third-party source on the node) | Your IP; the time of every index refresh and download; which distributions, components and package files the machine pulls, and their sizes. | `src/spaced-update.py:787` runs `pkexec … apt-refresh`, which is `apt_run update` at `src/spaced-update-helper:80`; downloads happen in the `apt-install` (`:941` → helper `:92`) and `dist-upgrade spaced-meta` (helper `:96`) transactions. `enumerate_apt` at `:238` runs `apt list --upgradable` at `:239`, which reads the already-refreshed local lists and **makes no request of its own**. | The app never adds, replaces or mirrors a source: traffic goes only to origins the administrator already configured. Timeouts and `Acquire::Retries=3` are bounded, so a stuck origin is not hammered. | Any access log, mirror analytics or request counting the origin performs; the fact that the set of components pulled describes the machine's OS configuration. |
| **Flatpak remote origins** (Flathub, `spaced-github`, any private remote the user added) | Your IP; the time of every query; which remote was queried and any identifying headers flatpak itself sends; and, on the update path, exactly which OSTree refs and commits the machine downloads — which names the apps and runtimes installed there. | `enumerate_flatpak` at `src/spaced-update.py:282` enumerates remotes locally (`flatpak list`, `flatpak remotes`) and then calls `flatpak remote-ls --updates` at `:325-335` per enabled remote; downloads follow at `:952` (`run_flatpak_update("--user", …)`) and `:1058` (`flatpak update … --user`), and in the helper at `:74`, `:125`, `:129` for system and named installations. | Only enabled, non-disabled remotes are queried, and each is queried independently so an offline one is reported rather than retried forever; the app adds no remote and no peer. | That the origin server does not log which refs you pulled — pulling a ref is the whole point of the request. |
| **Future peers, trackers and relays** (#2, #5) | Your IP; your peer identity; that you hold and seed specific artefacts; which chunks you requested and when; your upload volume; membership in a public swarm if DHT or an open tracker is enabled. | No call site exists today — there is no peer transport in this repository. This row is a requirement on #2/#5, not a capability. | Nothing today, because nothing is implemented: the absence of a peer transport is the only protection that currently applies. | Anything at all. Once a peer transport lands, an observer in this row is outside the app's control unless the controls listed below are implemented first. |
| **ISP / network observer** | Which destinations you contact (`api.github.com`, `crhy.github.io`, `flathub.org`, the Spaced APT origin), the volume and timing of each connection, TLS server names via SNI, and — through the home router, NAT or proxy logs — which machine on the network made them. Payload contents are not visible over TLS. | All of the above call sites. Inside the Flatpak, `--share=network` at `flatpak/org.spacedlinux.SpacedUpdate.json:8` is what lets these requests leave the sandbox at all; host commands are re-spawned by `host()` at `src/spaced-update.py:205`. | Nothing. There is no proxy, no Tor, no batching, no request padding, no timing smoothing. | Everything in this row. This observer sees the shape of the traffic no matter what the app sends, and no protocol can verify that an ISP or a router keeps no logs. |
| **Anyone holding a shared file** (#5) | From the artefact: filename, embedded paths, hostname, user id, timestamps, EXIF, OSTree ref names, package names and versions, and a digest that identifies which copies exist. From the channel: size, timing, and how often it is fetched. | No artefact is shared today. The nearest existing channel is the on-screen **Technical details** panel: `logline` at `:685` and `:1201` append raw command output to `LogPanel.append` at `:483`, which contains hostnames, paths and the machine's package set and can be copied into a bug report or screenshot. | The panel is on-screen only: nothing is written to disk, it is collapsed by default, and `LogPanel.clear()` (`:480`) wipes it at the start of each operation. | That a user pastes the panel's contents into an issue, or that a future shared artefact is free of identifying metadata — no scrubbing exists today, because no sharing exists today. |
| **Other accounts on the same machine** | Which user runs updates, and the fact that a transaction is running (the shared lock at `/run/lock/spaced-update.lock`, helper line 45); root's transactions touch system and named installations. | `exec 9>/run/lock/spaced-update.lock` and `flock -n 9` in `src/spaced-update-helper:45-47`; per-user Flatpaks are deliberately updated by the desktop process, never as root. | Per-user Flatpak installations stay per-user: the helper refuses `--user` (`src/spaced-update-helper:29-31`) and the app runs user updates as the signed-in user (`:952`, `:1058`). | Local file ownership and metadata on anything the machine writes, and any observation the other accounts already have. |

## The verifiable boundary

### True in code today, and checkable by reading it

- **No log file.** `logline` (`src/spaced-update.py:685` and `:1201`) only calls
  `LogPanel.append` (`:483`), which inserts text into a `Gtk.TextView` inside a collapsed
  expander. Neither `src/spaced-update.py` nor `src/spaced-update-helper` opens any file for
  writing; the only `open()` in the app reads `/etc/os-release` (`:194`), and the only file
  the helper creates is the empty transaction lock at `/run/lock/spaced-update.lock`
  (`src/spaced-update-helper:45`). No command output is persisted.
- **No machine identifier.** No hostname, machine-id, uid, IP, MAC address, UUID or
  application instance id is read, generated or transmitted. The single outbound request
  carries a fixed `User-Agent: spaced-update` and nothing identifying.
- **One unauthenticated release-feed GET**, with a fixed `User-Agent`, `Accept:
  application/vnd.github+json`, `timeout=30`, no cookie and no token
  (`src/spaced-update.py:1222-1230`).
- **All package traffic goes to configured origins.** The app never adds an APT source,
  a Flatpak remote, a mirror, a tracker or a peer. `apt list --upgradable` (`:239`) is
  local; the network calls are `apt-refresh` (`:787`), the install transactions (`:941`),
  `remote-ls` (`:325-335`) and `flatpak update` (`:952`, `:1058`).
- **The privileged path is consent-gated.** `data/com.spacedlinux.update.policy`
  (`org.freedesktop.policykit.exec.path = /usr/lib/spaced-linux/spaced-update-helper`,
  `allow_active auth_admin_keep`) is the consent control that already exists. It gates
  *privilege*, not *visibility* — do not describe it as a privacy feature.
- **The sandbox does not add identifiers, and does not constrain destinations.**
  `--share=network` (`flatpak/org.spacedlinux.SpacedUpdate.json:8`) is exactly what lets
  the requests above leave the sandbox; `--talk-name=org.freedesktop.Flatpak` (`:12`) plus
  `host()` (`:205`) is what runs APT, Flatpak and the helper on the host.

State these as facts about the current code, not as promises about the future: they are
true because of the lines above, and they stop being true the moment a new call site is
added without updating this document.

### What no protocol can verify for this app

- That an origin server — GitHub, Flathub, a Spaced mirror, any private remote — does
  not keep its own access log, or that its retention policy is what it claims.
- That a peer does not record what you fetched, keep your share list, or re-publish it.
- That timing and volume do not identify the machine. A machine that updates at odd
  hours, in odd increments, with an unusual package set, is identifiable without any
  identifier being sent.
- That the installed-application set is not itself a fingerprint. The set of refs an
  installation pulls is already close to unique, and it is what Flatpak requests exist to
  obtain.
- That the ISP, the home router, a corporate NAT, a DNS resolver or a TLS-interception
  box keeps no record.
- That anything a user pastes from the Technical details panel stays private once pasted.
- That a digest you published somewhere does not let an observer correlate your copies
  with someone else's.

**Therefore "untraceable" is not achievable, and "anonymous" is only achievable in a
narrow, defined sense** (no identifier in the artefact, no identity in the channel).
No UI string in this app may promise anonymity or untraceability that the protocol
cannot verify. Concretely:

- Forbidden in any string, tooltip, dialog or release note: "anonymous", "untraceable",
  "cannot be tracked", "private by default", "encrypted so nobody knows what you
  downloaded", "hides which apps you use".
- Allowed, because they describe the code: "writes no log file", "sends no machine
  identifier", "contacts only the origins you have configured", "this share contains no
  hostname or path".

## Leakage we accept today

Accepted deliberately, until #2 and #5 change the transport:

1. GitHub learns your IP and the timing of each release-feed check.
2. APT origins learn your IP, timing, and which components and files the machine pulls.
3. Flatpak remote origins learn your IP, timing, and which refs and commits the machine
   downloads — which names the apps installed there.
4. The network observer learns destinations, volume, timing and TLS server names.
5. The installed-application set acts as a de facto machine fingerprint, even though no
   identifier is sent.
6. The Technical details panel shows raw command output including hostnames and paths.
   It is never written to disk, but it is copyable by the user.
7. No proxy, Tor, batching, padding or timing smoothing exists; timing is not protected.
8. `--share=network` means the sandbox cannot limit which destination a request reaches;
   the guarantee rests on the code, not on the sandbox.

## Controls that must exist before any peer transport is enabled

Requirements on #2 (peer-to-peer repository transport) and #5 (anonymous file sharing).
None is implemented; each must have a test that fails without it.

1. **Consent prompt before a peer fetch**, distinct from the existing polkit
   authentication prompt, naming the peer set and the expected volume. A "Never contact
   peers" choice must be absolute — never seed, never contact a peer, never accept a
   peer-supplied index — including where honouring it costs convenience. (#2)
2. **Per-peer bandwidth, upload and concurrency limits**, a bounded seed lifetime, and a
   bounded share of any one artefact's chunks accepted from a single peer. (#2)
3. **No machine-identifying metadata in shared artefacts**: no hostname, path, uid,
   timestamp, OSTree ref name, package set, EXIF or digest of a personal file. Stripping
   must be verified on the artefact that leaves the machine, not assumed from the source.
   (#5)
4. **Deterministic origin fallback first**: origin, then a verified peer, then a clear
   refusal; the transport that supplied each artefact is reported. Peers are never added
   as mirrors to APT or Flatpak configuration. (#2)
5. **Allow-listed peers, no public DHT or open tracker by default** for OS content. (#2)
6. **Per-user cache keyed by digest**, so one user's fetches are invisible to another
   user and a name collision cannot alias two artefacts. (#2)
7. **Verification against origin-published digests before a peer's bytes are used**; a
   peer supplies bytes only, never a trust anchor. See the invariants in the transport
   design document `docs/P2P-REPOS.md` in [`crhy/spaced`](https://github.com/crhy/spaced),
   proposed in [crhy/spaced#9](https://github.com/crhy/spaced/issues/9) and not yet on that
   repository's default branch — it owns the transport design these controls depend on. (#2)
8. **Share links must not carry the sharer's identity or machine state**, and the browse
   view in #5 must not disclose who fetched what. (#5)
9. **A privacy statement in the UI that stays inside this boundary** — the wording rules
   above — and a settings surface for these controls behind the app's advanced settings
   rather than in the primary update flow. (#2, #5)

## Keeping this document honest

- When a change adds an outbound call site, add its row here in the same change. The
  enumeration in "What the updater actually sends" must stay complete; a row that names
  no call site is a requirement, not a fact, and must say so.
- Re-check the enumeration with:
  `grep -n "urllib\|http://\|https://\|apt\b\|flatpak\b" src/spaced-update.py src/spaced-update-helper`
- Do not describe behaviour the repository does not have. Where this document says a
  control must exist, the implementation needs a test that fails without it.
- Spaced Linux runs sysvinit only: any future scheduling for a cache sweep or anchor
  refresh is designed as an `/etc/init.d` script plus `cron`/`anacron`, never as an
  always-on background service, and nothing here may add boot-time work.

## Related

- [#2 — Peer2Peer repo and flatpak distribution](https://github.com/crhy/spacedupdate/issues/2)
- [#5 — File sharing](https://github.com/crhy/spacedupdate/issues/5)
- `docs/P2P-REPOS.md` in [`crhy/spaced`](https://github.com/crhy/spaced), proposed in
  [crhy/spaced#9](https://github.com/crhy/spaced/issues/9) and not yet merged there —
  the transport design, trust roots and chunking model these controls attach to.
- [`ISSUE-TRIAGE.md`](../ISSUE-TRIAGE.md) — why #4 stays open pending this model.

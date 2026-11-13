# Project context

This file describes durable implementation context. Read [AGENTS.md](AGENTS.md)
for working rules, [HANDOFF.md](HANDOFF.md) for the latest status, and
[readme.md](readme.md) for installation and controls.

## Purpose and distribution

[PAK Cricket](https://github.com/mabs7/cricket-tray) keeps Pakistan fixtures,
senior men's international cricket, and the six major franchise leagues (PSL, IPL,
BPL, Big Bash League, SA20, and The Hundred) visible while the user works. Windows
uses Tkinter plus pystray; macOS uses rumps. It is a flat Python application,
packaged separately on each OS with PyInstaller. There is no application backend,
database, login, required API key, or analytics service. Preferences/logs are
local, not synchronized via Git.

## Architecture

| Module | Responsibility |
| --- | --- |
| `scraper.py` | Fetch live/recent/upcoming Cricbuzz pages concurrently; decode embedded JSON, Next.js flight chunks, and `typeMatches` category groupings; fall back to HTML scoped by match ID, with JSON-LD fixture metadata. Distinguish active play (`live`) from session/day interruptions (`paused` with `phase` such as `Stumps`, `Lunch`, `Tea`, `Innings Break`, `Rain Delay`). Validate scores and report failures. |
| `filter.py` | Filter by saved feed scope (`scope="team"` for a chosen team and its paired league, or `scope="international"` for senior men's internationals plus `PSL`, `IPL`, `BPL`, `BBL`, `SA20`, `The Hundred`), excluding unrelated domestic/T10/legends/non-Pakistan women's leagues unless viewed in Pakistan team mode. Provide `categories_for_scope()` and `matches_category()` for Match Center filter tabs. Deduplicate by ID, prioritize active `live` then `paused` (ordered International -> League in International mode, or Pakistan/PSL -> International -> League in default mode), then up to twelve scheduled fixtures and eight recent completed matches. |
| `scores.py` | `ScoreService`: worker loop, event-driven manual refresh/stop, instant `set_filter(scope, team)` re-filtering of cached `pools`, locked state, deep-copy snapshots, stale-data preservation and freshness text. |
| `main.py` | Platform-specific `CricketApp`, modernized Match Center popup with persistent feed mode controls (`My Team: <Team>`, `Change Team ▾`, `International`), first-launch team-or-international picker when `scope` is unset, scope-aware category filter pills, one-click match selection for the floating live strip (`Show on Live Strip`), quick `◀`/`▶` strip cycling, update notification queues, and helper command routing. |
| `window_visibility.py` | Windows HWND visibility/topmost restoration without foreground activation, while respecting deliberate hiding. |
| `settings.py` / `app_logging.py` | Validated JSON preferences with temporary-file replacement; bounded rotating local logs. |
| `updater.py` | Stable-release checks, six-hour monitor, trusted GitHub URLs, streamed digest-verified downloads, ZIP validation, staging, helper launch. |
| `update_engine.py` | Parent-process wait, executable replacement/backup, independent restart, health handshake, rollback and conservative staging cleanup. |
| `version.py` | Source of truth for current version and GitHub repository identity. |
| `download_counts.py` | Maintainer-only GitHub release download report, paginated and grouped by platform/version; not called by the widget. |
| `create_icon.py` | Generate Windows ICO or macOS ICNS before packaging. |
| `docs/` | Static GitHub Pages showcase and download landing page (`index.html`, `og-preview.png`, `favicon.svg`, `favicon-48x48.png`, `apple-touch-icon.png`, `sitemap.xml`, `robots.txt`, `.nojekyll`) with interactive Windows/macOS `v2.9.1` previews, FAQ, JSON-LD (`SoftwareApplication` + `FAQPage`), Open Graph / Twitter `summary_large_image` social cards, and links to GitHub Release assets (`PakCricket-Windows.zip`, `PakCricket-Mac.zip`) and the developer's portfolio. |

Data flow: Cricbuzz HTML -> `parse_page` -> match dictionaries -> filtering and
selection -> atomic `ScoreService` snapshot -> platform UI. Scraped data is never
executed as code. The parser is pure and can consume saved fixtures.

### Shared data contracts

- A match includes `id` (string), `href`, `teams`, `team_names`, `team_codes`,
  `series`, `start_time`, `status`, `state`, `phase` (interruption label such as
  `Stumps`, `Lunch`, `Tea`, `Innings Break`, `Rain Delay`, or `""`), `is_live`,
  `is_psl`, `category` (`international`, `league`, `domestic`, `women`, or `""`),
  `competition` (`Pakistan`, `International`, `PSL`, `IPL`, `BPL`, `BBL`, `SA20`,
  `The Hundred`, added by `filter.py`), `scores`, `score` (formatted text), and
  `parser` (`embedded` or `html`).
- Each score row contains `team`, integer `runs`, nullable integer `wickets`, and
  textual `overs`. Embedded Cricbuzz overs such as `19.6` are normalized to `20`;
  overs are cricket ball notation, not decimal fractions. Wickets must be 0-10.
- `start_time` can be Unix milliseconds or timezone-aware ISO text; `parse_date`
  converts it to UTC. Display times and the meaning of "today" use local time.
- Match states: `live`, `paused`, `scheduled`, `completed`, `unknown`. Aggregate
  selection adds `today` and `none`; these are distinct from network/parse health.
  UI surfaces render `state_label(match)`, which displays the specific `phase` in
  uppercase (`STUMPS`, `LUNCH`, `TEA`, `INNINGS BREAK`, `RAIN DELAY`) when a match
  is `paused` instead of showing `LIVE`.
- `get_all_matches()` returns `live`, `recent`, `upcoming` lists and an `errors`
  dictionary identifying failed pools. Empty recognized schedules are valid;
  blocked/unrecognized pages raise `ScrapeError` instead of pretending no matches.
- A service snapshot includes `state`, `matches`, `updated_at`, `errors`,
  `refreshing`, `revision`. A refresh commits only when all pools succeed. Failed
  refreshes, or a previously available live/paused score disappearing, preserve the
  complete previous snapshot and its successful timestamp. Scores are in memory
  only and do not survive app exit.

### Timing and UI ownership

Score network intervals: live 45 seconds; paused 120 seconds (300 seconds when all
paused matches are at Stumps overnight); today/scheduled 300 seconds;
completed/no fixtures 1,800 seconds; failures retry after 60 seconds. Windows
redraws on a one-second timer and checks bar visibility every two seconds. UI
timers consume cached snapshots; they do not fetch a score every second.

Tk owns the Windows main thread; fetching, release checks/downloads, and tray work
run in background threads and send commands through a queue. Recoverable tick
errors are logged and the timer is rescheduled. macOS uses a rumps timer and a
queue for update results. Do not assume the two interfaces have identical feature
parity: Windows provides the floating live strip, Match Center popup, and
portable self-update, while macOS uses the menu bar dropdown and opens the
release page; both interfaces persist feed scope, team, and match selection.

### Preferences and logging

`settings_path()` resolves to `%APPDATA%/PakCricket/settings.json` on Windows, or
`~/.config/PakCricket/settings.json` when APPDATA is absent (including macOS).
Keys: position, hidden, topmost, text_size, selected, notified_version, scope
(`"team"`, `"international"`, or `null`), team (selected team name or `null`).
Logs are adjacent as `app.log`, rotating at 512,000 bytes with two backups. These
are machine-local runtime files. They must not be committed or copied between PCs.

### Portable updater and release contract

Checks use GitHub's latest stable release API at startup, every six hours, or on
manual request. Versions compare numeric components; prereleases/drafts are
excluded. Notification version is remembered locally. Windows shows an update
badge even if details are closed. A failed check does not remove a previously
known available update. macOS/source runs open the release page for installation.

Packaged Windows updates require a user click and confirmation. The expected
asset is `PakCricket-Windows.zip`, containing exactly one root `PakCricket.exe`.
The release metadata must supply a SHA-256 digest and a matching trusted HTTPS
GitHub URL. Downloads are bounded to 150 MiB. ZIP path/layout validation prevents
arbitrary extraction. SHA-256 checks are integrity checks, not code signing.

For a writable app folder, staging lives in a sibling `.pakcricket-update-*`
directory. A copy of the running app acts as the helper via `--apply-update`;
this route must run before creating a GUI. It waits for the old PID to exit,
retains a `*.previous-*.exe` backup, replaces the executable, and restarts with
`--update-health`. The new Tk app writes a readiness marker; the helper allows
45 seconds for startup and rolls back if that fails. Independent frozen launches
set `PYINSTALLER_RESET_ENVIRONMENT=1`. Successful staging cleanup is delayed and
only removes recognized files. In an unwritable folder, the user can save a new
copy elsewhere; the original remains. Old versions without this implementation
need a one-time manual download.

The tag-triggered workflow in [.github/workflows/build.yml](.github/workflows/build.yml)
uses Python 3.11, builds both platforms, runs offline tests on both and Windows
UI/packaged-update checks, then publishes `PakCricket-Windows.zip` and
`PakCricket-Mac.zip` using [release-notes.md](release-notes.md). Builds are unsigned.
`requirements.txt` is pinned, but the workflow installs dependencies without those
pins; do not assume exact environment reproducibility.

## Significant decisions and rationale

- **Use Cricbuzz with layered parsing:** free APIs researched in the earlier
  discussion had quotas poorly suited to frequent live polling. Embedded data
  reduces coupling to styling; scoped HTML is a fallback, not a guarantee against
  upstream changes. No attempt to evade access controls was approved.
- **Separate stale data from match status:** an outage should show the last
  reliable score with its age, not mislead users into thinking no match is on.
  Whole-refresh preservation favors consistency over partial updates.
- **Keep the portable widget small:** retain Python/Tkinter/rumps instead of
  changing frameworks or introducing a backend/mandatory installer.
- **Explicit Windows update action:** users should be informed automatically,
  but the app should not replace itself or restart during a match unprompted.
  Backup and startup verification reduce the risk of a broken update.
- **No active-user tracking:** the owner chose download counts for now. There
  is no random installation ID, heartbeat, or user-detail collection. Adding
  opt-in active-installation telemetry remains a separate, unapproved feature.
- **Open-source maintenance:** allowing others to repair layout-dependent
  scraping was an explicit motivation. Preserve that intent; no LICENSE file is
  currently present, so do not invent license terms.
- **Context belongs in Git:** stable rules live in AGENTS.md, durable design here,
  and current progress in HANDOFF.md. This avoids relying on one machine's chat
  history while keeping public user docs separate.

## Validation map

`tests/test_core.py` covers parsing, filtering, dates, stale snapshots, preferences
and version order; `tests/test_updates.py` covers release/download validation,
helper replacement/rollback, visibility behavior, and download aggregation.
`tests/fixtures/` includes synthetic fallback samples and observed flight records.
See AGENTS.md for commands and the distinction between offline, live, desktop,
and packaged tests. Build success does not establish every live-match or macOS
interaction works; record actual test evidence in HANDOFF.md.

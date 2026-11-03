# Development handoff

Last reviewed: **2026-11-03** (Asia/Karachi). This is the current-work record;
see [AGENTS.md](AGENTS.md) for session instructions and
[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for architecture and decisions.

## Baseline and current work

- Repository: [mabs7/cricket-tray](https://github.com/mabs7/cricket-tray), branch
  `main`. Application version: **v2.8.0**, commit `3de9eab`.
- Added a static GitHub Pages showcase and download landing page in
  [docs/index.html](docs/index.html) (with [docs/.nojekyll](docs/.nojekyll)) on
  macOS (`3de9eab`), and refined it on Windows (**2026-11-03**) into a cleaner,
  minimalist design with a restrained dark slate palette, prominent keyword-focused
  copy, and distinct hover glows on both the Windows (emerald) and macOS (sky-blue)
  download buttons. It features an interactive Windows floating-bar and macOS
  menu-bar preview, accurate platform-specific capabilities, direct
  `/releases/latest/download/` asset links (`PakCricket-Windows.zip` and
  `PakCricket-Mac.zip`), and an "About the Developer" section linking to Muhammad
  Abubakar's portfolio (`https://abubakar144-portfolio.netlify.app`) and GitHub
  profile.
- Existing Python application code, tests, version, and CI workflow are unchanged.
  The owner requested committing and pushing this minimalist landing-page refinement
  to `main`; no new application release tag is created. Verify `git status --short --branch`
  and `git log -1` for the actual commit and synchronization state before continuing
  on another computer.

## Recent implementation history

| Baseline | Work completed |
| --- | --- |
| `e18605f` / v2.7.0 (2026-10-04) | Structured Cricbuzz parsing with HTML fallback and validation; stable IDs; preserved stale snapshots; improved Windows details, controls and preferences; macOS dropdown; numeric version comparison; regression suite. |
| `36846c2` / v2.8.0 (2026-10-09) | Windows visibility watchdog and callback recovery; local logging; periodic update checks and visible notifications; portable Windows download/verify/replace/restart with backup/rollback; maintainer download-count report; Windows smoke checks added to release CI. |
| `542692f` (2026-10-30) | Added AGENTS.md, PROJECT_CONTEXT.md, and HANDOFF.md persistent repository context. |
| `3de9eab` (2026-11-03) | Added GitHub Pages showcase landing page (`docs/index.html`, `docs/.nojekyll`) and updated context. |

Conversation evidence: on 2026-10-09 the owner reported live scores updating
correctly, but the bar disappearing after some time. v2.8.0 addresses visibility
and UI callback resilience. No subsequent owner confirmation of the bar fix or
an actual v2.8.0-to-newer-version update is recorded in the available history.

## Validation and external status

- **Historical, 2026-10-09:** all 32 offline tests, Windows UI smoke checks, and
  the local packaged-updater handshake test passed. The latter used disposable
  copies of the same build; it is not proof of a real upgrade between different
  published versions. GitHub Windows/macOS builds and release publication passed
  for v2.8.0. [Recorded run](https://github.com/mabs7/cricket-tray/actions/runs/37939514206).
- **Current landing-page task, 2026-11-03 (Windows):** pulled `3de9eab` from
  `origin/main` and refined `docs/index.html` for a minimalist color palette,
  prominent keyword-driven copy, and distinct hover glows on the Windows and macOS
  download buttons. Verified repository-relative links, download asset URLs
  (`PakCricket-Windows.zip`, `PakCricket-Mac.zip`), platform feature accuracy, and
  `git diff --check`. Python application code and builds were unchanged.
- [Issue #1](https://github.com/mabs7/cricket-tray/issues/1) reported missing
  Pakistan/England Test scores before the scraper changes. It was replied to and
  closed on 2026-10-04, linking v2.7.0. The reporter's later follow-up says they
  plan to test during a match and contribute; it does **not** confirm resolution.
- The last measured download total was **53** (37 Windows, 16 macOS) on
  2026-10-09. This is historical, not today's total or active users. Obtain a fresh
  report with `python download_counts.py`; no telemetry was added.

## Unresolved items and next tasks

1. **Validate real Windows match usage.** Reproduce any continuing disappearance
   and determine whether the app remains in the tray, becomes hidden/covered, or
   exits. Check the local app log, topmost/hidden preferences, sleep/resume,
   desktop switches and display changes. The original root cause was not proven;
   do not describe the watchdog as a confirmed cure for all cases.
2. **Validate on the MacBook.** Test menu rendering/selection, notifications,
   refresh/shutdown behavior and packaged launch. Prior Windows checks and macOS
   CI build success do not replace interactive macOS QA. macOS in-app executable
   replacement is not implemented; release-page installation is intentional.
3. **Exercise the first real portable upgrade when a newer release exists.**
   Check digest verification, restart, preserved preferences, rollback, writable
   and unwritable locations. Unit tests and the same-build packaged smoke test
   already exist; preserve them.
4. **Improve fixtures if new failures appear.** Add offline samples from failing
   layouts/match states before adjusting parsing. Cricbuzz is still an upstream
   dependency and can change or refuse requests. Keep blocked pages distinct
   from valid empty schedules.
5. **Small documentation/maintenance follow-ups, not changed here:** README still
   calls the Mac archive `PakCricket.zip` in places, while release CI publishes
   `PakCricket-Mac.zip`. Its general feature list also mixes Windows/macOS
   capabilities; check platform-specific code before promising parity. Pinned
   requirements and unpinned CI installs can diverge. No LICENSE file is present;
   license choice belongs to the owner.

No active-installation counting or user-detail tracking is approved or pending
implementation. Reddit/LinkedIn post drafts were prepared in conversation; no
publication through this session was recorded.

## Continuing on either computer

Synchronize this repository through Git, inspect local changes before pulling,
and read AGENTS.md -> PROJECT_CONTEXT.md -> HANDOFF.md. Create a local virtual
environment for that OS; do not transfer Windows binaries or `.venv` to macOS.
Follow README/CI for platform setup and AGENTS.md for validation. User preferences
and logs remain local; these files synchronize development knowledge only.

When finishing significant work, replace stale progress in this file with the
actual change, evidence, remaining work and commit/push/release state. Update
PROJECT_CONTEXT.md for durable changes and AGENTS.md only for new working rules.
Keep historical verification labeled with its date/platform rather than claiming
it was repeated in the current session.

## Documentation verification for this handoff

- Updated `docs/index.html` and `HANDOFF.md`; existing Python application and test files are unchanged.
- Repository-relative documentation links resolve and `git diff --check` passes.
- No application tests/builds were required or rerun; no new application release was created.

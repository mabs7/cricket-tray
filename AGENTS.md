# Instructions for Codex sessions

## Project and context

PAK Cricket is a free Python desktop widget for Pakistan international and PSL
scores: a portable floating bar/system tray app on Windows and a menu bar app on
macOS. The repository is `mabs7/cricket-tray`; the default branch is `main`.

At the start of a session:

1. Read this file, [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), and
   [HANDOFF.md](HANDOFF.md).
2. Inspect `git status --short --branch` and recent commits before editing.
   Preserve existing user changes. Check upstream state when relevant rather
   than assuming another computer has no newer commits; do not blindly pull
   over local work.
3. Read the relevant source/tests. Code and verified repository state take
   precedence over stale notes. Distinguish confirmed facts from proposed work.
4. Use [readme.md](readme.md) for public usage/setup instructions and
   [release-notes.md](release-notes.md) for the release being prepared.

## Technical standards and conventions

- Target Python 3.11+; release CI currently uses 3.11. Keep the app lightweight
  and compatible with Windows and macOS. Linux is not a supported product target.
- Follow the existing flat-module layout, four-space indentation, `snake_case`
  functions/variables, `PascalCase` classes, and uppercase constants. No formatter,
  linter, or static type checker is currently configured; do not impose a large
  formatting rewrite while fixing a small issue.
- Keep fetching, pure parsing/filtering, shared refresh state, and UI work
  separate. Preserve the dictionary contracts documented in PROJECT_CONTEXT.md.
- Keep network/download work off the UI thread. On Windows, deliver worker/tray
  results through the queue and schedule Tk operations on its main thread.
- Use bounded network timeouts and meaningful error states. Fetch/parse failure
  must not become an empty schedule or erase the last reliable score. Keep
  match state separate from refresh health.
- Prefer stable match IDs and validated, match-scoped extraction over broad
  page-text searches or CSS-only assumptions. Decode embedded data; never execute
  page scripts. Add representative offline fixtures when changing parsers.
- Guard platform-specific APIs/imports. Shared modules and the offline test suite
  must remain usable on both target systems. Do not infer macOS GUI correctness
  from Windows checks or a successful package build.
- Use `pathlib`, UTF-8 files, and platform-appropriate executable paths. Do not
  commit machine-specific drive paths, virtual environments, credentials,
  settings, logs, temporary update files, or generated build artifacts.

## Product constraints

- Preserve the portable Windows distribution: unzip and run, no mandatory
  installer, administrator rights, or background service.
- The bar should remain visible without stealing focus; explicit Hide, Quit,
  and disabling Always on top must be respected. Do not promise visibility over
  Windows security screens or exclusive full-screen apps.
- Keep the app free and API-key-free. It currently uses Cricbuzz directly;
  reliability is best effort, not a guaranteed real-time feed. Do not bypass
  access restrictions.
- There is no active-user tracking, analytics endpoint, installation ID, or
  user-detail collection. The approved metric is GitHub asset download counts,
  which are not unique users. Do not add telemetry as an incidental change.
- Check automatically for updates, but require the user's action to download,
  replace, and restart. Preserve preferences, trusted release URL checks,
  SHA-256 verification, archive/path validation, backup, and startup rollback.
  Never replace the Python interpreter in a source run.
- Preserve macOS support and its current release-page installation flow unless
  a change to that behavior is explicitly part of the task.

## Validation and releases

- Use a separate local virtual environment on each computer; never copy `.venv`
  between Windows and macOS. Activate it and use its `python` for commands.
  Platform dependencies/setup are described in readme.md and requirements.txt;
  the actual release commands live in `.github/workflows/build.yml`.
- For application changes, run `python -m unittest discover -s tests -v` and
  checks appropriate to the change. Use saved fixtures and mocked requests for
  deterministic tests; `test_scraper.py` is a separate live network diagnostic.
- `python tests/ui_smoke.py` is Windows-only and creates temporary Tk windows.
  `python tests/packaged_update_smoke.py` is also Windows-only, requires a freshly
  built `dist/PakCricket.exe`, and launches/terminates disposable executable
  copies. Do not run either as if it were a headless cross-platform unit test.
- For documentation-only work, verify links, factual accuracy, scope, and
  `git diff --check`; application builds/tests need not be repeated without a
  relevant reason. Report what was actually checked.
- For a requested release, update `version.py`, release notes, and affected public
  documentation. A pushed `v*` tag starts the two platform builds and publishes
  downloads only after both succeed. Do not move published tags or claim a
  release is available until CI and its assets have been verified.
- Keep the asset names/ZIP layout compatible with the updater; consult the
  architecture notes before changing packaging or the helper entry points.

## Maintain persistent context

After significant implementation, investigation, validation, release, or a change
in direction, update the relevant context files in the same work item:

- `PROJECT_CONTEXT.md`: durable architecture, contracts, features, decisions and
  rationale. Replace obsolete descriptions rather than appending a diary.
- `HANDOFF.md`: current baseline, work completed, verification with dates and
  platform, unresolved findings, and actionable next tasks. Mark historical
  evidence and unverified hypotheses explicitly.
- `AGENTS.md`: stable working rules and constraints only when they change.
- `readme.md` / `release-notes.md`: user-visible instructions and release changes
  when applicable; link to these instead of duplicating their full contents.

Use repository-relative Markdown links and ISO dates so these files work in any
checkout. Do not include private conversation transcripts, personal machine
details, or credentials. Before finishing, ensure handoff notes match the actual
diff and clearly state whether work is local, committed, pushed, or released.
Context travels through Git: carry it in the relevant commit, push when within
the task's authorized scope, and synchronize the other computer before resuming.
These instructions guide future Codex sessions; they are not a background sync
service.

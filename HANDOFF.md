# Development handoff

Last reviewed: **2026-11-13** (Asia/Karachi). This is the current-work record;
see [AGENTS.md](AGENTS.md) for session instructions and
[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for architecture and decisions.

## Baseline and current work

- Repository: [mabs7/cricket-tray](https://github.com/mabs7/cricket-tray), branch
  `main`. Published application version: **v2.9.1** (`3abd81d`, released
  2026-11-13 following unpublished `v2.9.0` tag `e3608d6`). Latest docs/website
  commit: `8712b08`.
- **Completed in recent sessions (2026-11-11 to 2026-11-13, Windows):**
  1. **Stumps / Session-Break State (`paused` + `phase`):** Fixed the issue where
     a Test match stopped for the day at Stumps (or a match at Lunch, Tea, Dinner,
     Drinks, Innings Break, Rain Delay, Wet Outfield, or Bad Light) still showed
     `LIVE`. `scraper.py` now classifies interrupted matches as `state="paused"`
     with `is_live=False` and extracts a normalized `phase` (`"Stumps"`,
     `"Lunch"`, `"Tea"`, `"Innings Break"`, `"Rain Delay"`, etc.). Both the
     Windows floating bar/details cards and the macOS menu bar now display
     `STUMPS` (or the specific break label) in sky-blue (`#7ec8f8`) instead of
     red `LIVE`, and `scores.py` polls every 5 minutes at Stumps (or 2 minutes
     during mid-day breaks) rather than the 45-second active-play interval.
  2. **Expanded Match Coverage (Internationals + 6 Major Leagues):** Expanded
     `scraper.py` to extract Cricbuzz's `typeMatches` grouping (`International`,
     `League`, `Domestic`, `Women`) and updated `filter.py` (`competition()`,
     `filter_covered_matches()`, `get_match_state()`) to cover:
     - **Pakistan** fixtures (Men, Women, U19, Shaheens/A, and PSL)
     - **Senior Men's International** matches (Tests, ODIs, T20Is, ICC events)
     - **6 Major Franchise Leagues:** **PSL**, **IPL**, **BPL**, **Big Bash League (BBL)**, **SA20**, and **The Hundred**
     Unrelated domestic competitions (e.g. Sheffield Shield, Ford Trophy, Ranji),
     T10/regional leagues (e.g. Abu Dhabi T10, Nepal Premier League, CSA T20),
     legends tournaments, and non-Pakistan women's/youth leagues (e.g. WBBL, WPL)
     are excluded. Active `live` matches always take precedence over `paused`
     matches, and within each tier matches are ordered **Pakistan → International → League**.
  3. **Match Center Selection Mechanism & UI Modernization:**
     - Added category filter pills (`All`, `Pakistan`, `International`, `PSL`, `IPL`,
       `BPL`, `BBL`, `SA20`, `The Hundred` via `matches_category()`) in the Match
       Center popup so the user can view detailed matches by competition while the
       floating live strip shows only the selected match.
     - Added immediate one-click match selection (clicking any match card or its
       `Show on Live Strip` button immediately updates the floating live strip without
       waiting for the next timer tick), an active-strip header banner (`▸ Pinned to
       live strip: ...` / `Auto-select top match`), emerald active-card border and
       `📌 ON LIVE STRIP` badge, and `◀` / `▶` quick-cycle buttons on the floating
       strip itself.
     - Modernized all Tkinter buttons, cards, borders, context menus, and the
       vertical `ttk.Scrollbar` (`Dark.Vertical.TScrollbar`) so no unstyled Windows 95
       gray 3D buttons remain, and persisted `selected` across sessions on macOS as
       well as Windows.
  4. **Persistent Feed Scope & Team Selector (`scope` + `team`):**
     - Added `"scope"` (`"team"`, `"international"`, or `None`) and `"team"` to
       `settings.py` (`DEFAULTS` + validation in `load_settings()`), persisted
       in `settings.json` so restarts remember the choice automatically.
     - Added `TEAMS` (12 major international sides and paired T20/Hundred
       leagues, e.g., Pakistan → PSL, India → IPL, Australia → BBL,
       England → The Hundred, South Africa → SA20, Bangladesh → BPL),
       `is_team_match()`, `filter_for_scope()`, and `categories_for_scope()` in
       `filter.py`, plus `ScoreService.set_filter(scope, team)` in `scores.py` to
       re-filter cached pools immediately without waiting for another fetch.
     - Added persistent `My Team: <Team>`, `Change Team ▾` (expanding a 3-column
       team grid), and `International` buttons in the Windows Match Center (and
       equivalent menu items in the macOS `rumps` menu), auto-opening the
       Match Center / team-or-international choice on first launch when
       `scope` is unset (`None`).
  5. **Hardening & Stability Pass (verified via read-only audit + regression suite):**
     - `scraper.py`: Added chronological `inningsId` sorting + `isDeclared` (`434/9d`)
       formatting, key-order-independent `typeMatches` parsing in `_categories()`,
       iterative JSON traversals, explicit-`null` field guards, active-resumption
       exclusions + rain-phrase improvements in `match_state()`, and bounded
       streaming HTTPS fetches (10 MiB cap + 20s deadline).
     - `filter.py`: Prioritized the user's chosen national team ahead of its
       paired league in `Team` mode (`_rank`), separated team-only vs league pills
       in `matches_category(..., scope=scope)`, added `Pakistan Shaheens`, and
       blocked non-senior/women's leaks into `International` mode.
     - `settings.py`, `updater.py`, `update_engine.py`, `window_visibility.py`:
       Validated `team in TEAMS` + unique temp-file replacement in `save_settings()`;
       added `PermissionError` retry & `TimeoutExpired` protection to update
       rollback, stale backup/stage cleanup (`cleanup_old_updates()`), `ETag`
       caching (`If-None-Match`), `type(size) is int` validation, and multi-monitor
       `monitor_work_area()` / Win+L `ERROR_ACCESS_DENIED` suppression.
     - `main.py`: Added `pystray` setup synchronization + `topmost` menu sync +
       clean tray teardown, idempotent `quit()` and modal update dialog guards,
       wrapped filter pills and badge-first card headers, precision-touchpad scroll
       handling, font caching, macOS `menu_key` caching (avoiding 2s menu rebuilds),
       and empty-overs formatting fixes.
  6. **GitHub Pages Website Update, Social Cards & UX Overhaul (`docs/`, `7432365` & `8712b08`):**
     - Updated [docs/index.html](docs/index.html) and [docs/sitemap.xml](docs/sitemap.xml)
       for **v2.9.1** features (12 teams, international + 6 major leagues, session-break
       states, Windows Match Center and macOS feed toggles).
     - Added hosted visual and icon assets: [docs/og-preview.png](docs/og-preview.png)
       (`1200×630` RGB PNG), [docs/favicon.svg](docs/favicon.svg),
       [docs/favicon-48x48.png](docs/favicon-48x48.png), and
       [docs/apple-touch-icon.png](docs/apple-touch-icon.png), wired with Open Graph
       (`og:image`, dimensions, alt) and `twitter:card="summary_large_image"` tags.
     - Fixed interactive preview math (`PAK 172/4 (18.4)` vs `AUS 196/7 (20)`), added
       `Matches (2) ▾`, `Change Team ▾` 6-team picker, category filters, `◀`/`▶`
       strip cycling, macOS `Feed: International & Leagues` / `Feed: Pick a Team ▸`
       toggles, responsive mobile breakpoints (`<= 780px`, `<= 720px`, `<= 560px`),
       `:focus-visible`/ARIA/reduced-motion accessibility, `#faq` section, and
       updated `SoftwareApplication` + `FAQPage` JSON-LD.

## Recent implementation history

| Baseline | Work completed |
| --- | --- |
| `e18605f` / v2.7.0 (2026-10-04) | Structured Cricbuzz parsing with HTML fallback and validation; stable IDs; preserved stale snapshots; improved Windows details, controls and preferences; macOS dropdown; numeric version comparison; regression suite. |
| `36846c2` / v2.8.0 (2026-10-09) | Windows visibility watchdog and callback recovery; local logging; periodic update checks and visible notifications; portable Windows download/verify/replace/restart with backup/rollback; maintainer download-count report; Windows smoke checks added to release CI. |
| `542692f` (2026-10-30) | Added AGENTS.md, PROJECT_CONTEXT.md, and HANDOFF.md persistent repository context. |
| `0c975b1` (2026-11-03) | Added minimalist GitHub Pages landing page (`docs/index.html`), `sitemap.xml`, `robots.txt`, JSON-LD metadata, and Google Search Console verification tag. |
| `3abd81d` / v2.9.1 (2026-11-13) | Expanded coverage to senior internationals + 6 major leagues, added Stumps/break states, Match Center selection, 12-team selector, hardening pass, and fixed macOS ctypes test mock for release (`v2.9.0` superseded by `v2.9.1`). |
| `8712b08` (2026-11-13) | Updated GitHub Pages site for `v2.9.1`, added hosted `og-preview.png` (`summary_large_image`) and favicons, fixed preview cricket math, added interactive team/feed previews, mobile layout, ARIA/focus accessibility, and `#faq`. |

## Validation and external status

- **Website & Release Verification, 2026-11-13 (Windows / Live):**
  - GitHub release API (`/releases/latest`) verified **v2.9.1** published at
    `2026-11-13T06:32:43Z` with `PakCricket-Windows.zip` (`25,176,709` bytes) and
    `PakCricket-Mac.zip` (`22,966,995` bytes).
  - Offline validation on `docs/` (`8712b08`): HTML tag balance (`52` static IDs),
    all `36` JS `getElementById` references matched, JSON-LD and `docs/sitemap.xml`
    parsed, `node --check` passed on inline script, and `git diff --check` passed.
  - Live GitHub Pages check (`Twitterbot/1.0`): `https://mabs7.github.io/cricket-tray/`
    returned `HTTP 200 OK` (no redirect) with `twitter:card="summary_large_image"`,
    `og:image`/`twitter:image` pointing to `og-preview.png`; `og-preview.png`
    returned `HTTP 200 OK` (`image/png`, `1200×630` RGB, `72,959` bytes);
    `/cricket-tray` (no trailing slash) returned `301` to `/cricket-tray/`.
- **Application Validation, 2026-11-13 (Windows, v2.9.1):**
  - `.venv\Scripts\python.exe -m unittest discover -s tests -v`: **41 offline tests passed**
    after final `v2.9.1` release edits (and verified under simulated `sys.platform='darwin'`
    with `ctypes.WinDLL`/`get_last_error` removed).
  - `.venv\Scripts\python.exe tests\ui_smoke.py`: **passed** on Windows (`v2.9.1`).
  - `.venv\Scripts\python.exe test_scraper.py`: **passed** against live Cricbuzz
    data (verified `Pakistan vs Sri Lanka` chronological innings + `434/9d` declared
    score, `New Zealand vs India` `Innings Break`, `England vs Australia` live, and
    `Zimbabwe vs Afghanistan` live).
  - Live Windows packaged widget verification (`dist/PakCricket.exe`, `11:14 AM` build):
    verified by owner on desktop showing `Bad Light` interruption state.
  - `.venv\Scripts\python.exe tests\packaged_update_smoke.py`: **passed** earlier
    against the `10:32:55 AM` `dist/PakCricket.exe` build; `v2.9.1` GitHub
    Actions CI subsequently built and published both platform assets.
  - `git diff --check`: **passed**.
- **Earlier live diagnostic, 2026-11-11 (Windows, prior to `scope`/`team` UI controls):**
  - `python test_scraper.py`: **passed** against live Cricbuzz data; verified
    Pakistan vs Sri Lanka 1st Test (`Day 3: Stumps - Sri Lanka trail by 30 runs`)
    is classified as `state="paused"`, `phase="Stumps"`, `is_live=False`, and
    rendered as `● STUMPS` instead of `● LIVE`.

## Unresolved items and next tasks

1. **Confirm X (Twitter) social preview card cache clearing:** Bare URL
   `https://mabs7.github.io/cricket-tray/` had been posted on X before `8712b08`,
   so X cached the pre-update imageless card (up to ~7 days) and still rendered no
   preview right after push. Test `https://mabs7.github.io/cricket-tray/index.html?v=3`
   on X (or LinkedIn Post Inspector) to verify card rendering independently of the
   cached bare URL; if `?v=3` also fails when posted alone without media, revisit
   `og:url` canonical collapsing or `mabs7.github.io` root `robots.txt`.
2. **Validate on the MacBook:** Test `PakCricket-Mac.zip` (`v2.9.1`) menu rendering
   (`STUMPS · ...`, `Team` / `International` menu switching, and reduced menu rebuilds)
   on macOS.
3. **Exercise portable upgrade from `v2.8.0` to `v2.9.1`:** Verify in-app upgrading
   from v2.8.0 to v2.9.1 on Windows.
4. **Small documentation/maintenance follow-ups:** No LICENSE file is present;
   license choice belongs to the owner.

## Continuing on either computer

Synchronize this repository through Git, inspect local changes before pulling,
and read AGENTS.md -> PROJECT_CONTEXT.md -> HANDOFF.md. Create a local virtual
environment for that OS; do not transfer Windows binaries or `.venv` to macOS.
Follow README/CI for platform setup and AGENTS.md for validation. User preferences
and logs remain local; these files synchronize development knowledge only.

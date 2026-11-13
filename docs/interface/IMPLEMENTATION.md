# Rust desktop migration record

2026-11-12. The Iced desktop is implemented with the requested top tabs and dark purple theme. [Launch instructions](../../README.md#build-and-launch). The original Tkinter frontend remains a fallback while the user evaluates the replacement. No live game world was changed during the migration.

## Delivered behavior

- Mob, Fortune, Iron and Gold tabs, shared creation seed/view distance/search center, per-mode drafts and collapsed advanced settings.
- 120ms button hover, 160ms tab selection, 180ms panel expansion and result reveal, with interruptible ease-out transitions. Reduced motion checkbox and startup environment override disable transitions.
- Responsive wide/stacked layouts, short-window scrolling at high zoom, fixed Find/Cancel/Next/Export actions and 100/150/200% scaling.
- Named placement/player coordinates with Copy, build prerequisites, evidence limits and the complete export plan.
- Background search/terrain/cleanup/export with JSON progress, elapsed time, cancellation of the worker process group, error reporting, field focus and stale-result protection. Previous results survive failed searches.
- Read-only saved-world selection and seed loading, trace mode, 1/3–3/3 Gold success selection and existing native cleanup export behavior.
- Native folder dialogs; exclusive output creation and rollback of files created by a failed export. No overwrite or automatic save repair.
- Explicit keyboard focus rings for controls lacking built-in Iced focus, Tab/Shift+Tab, Enter/Space, directional mode/choice selection, Ctrl+Enter, Escape and Ctrl+S.

The frontend uses Iced 0.14.0 with its software renderer and RFD 0.17.2. The separate Cargo crate keeps the existing RNG CLI free of GUI dependencies. Python calculation/assembly entry points moved from `gui.py` to `backend.py`; Tkinter and `desktop_worker.py` call that same implementation. The worker adapts the legacy generated plan into structured coordinate/requirement fields; the Rust view never parses display labels. This adapter deliberately omits unrecognized coordinates rather than inventing them.

## Checks and observed results

Local runtime: Linux desktop with X11/Xvfb window checks; Rust stable toolchain, Python 3 and the existing Java/MCP 1.12.2 terrain runtime. These are UI/tool checks, not new Minecraft gameplay trials.

| Check | Result |
| --- | --- |
| Optimized locked desktop build | Passed |
| Existing RNG arithmetic/reference tests | 19 passed |
| Rust UI state/reduced-motion/process-tree cancellation tests | 4 passed |
| Python worker validation, all-mode artifact dispatch, export rollback, saved-world read-only selection, protocol error and no-Tk import checks | 6 passed |
| Shared detector, roof, combined legacy/native, cleanup, water, success selection, next candidates, vertical placement/terrain, height and terrain regression scripts | All 12 passed |
| Real worker searches with actual terrain scans | Gold, Fortune, Iron and Mob all completed for seed 12345, center 0/0, view distance 10; radius 25 except Iron 128. Mob retained candidate index 12; others index 0. |
| Native dialog export from the Gold result window | Saved schematic/plan; complete decoded block/entity NBT equals the independent headless Gold search |
| Search cancellation in window | Escape returned to editable settings and a cancelled status; separate process-tree test confirms descendant termination |
| Render review | Wide/compact layouts and 100/150/200% scaling; corrected a short-window overflow so settings/results scroll and actions stay visible |
| Error review | Invalid destination reports the actual write failure and retains the previous candidate; unit tests cover existing-file protection and partial-pair rollback |
| Agent setup | Passed |

The research workspace retains private test logs and candidate artifacts; they are excluded from this repository. Full source tests remain reproducible from the checked-in commands. [Desktop preview](desktop.png) is a real application render using example inputs.

## Limits and retained fallback

Python 3, Java and the existing MCP/runtime dependencies remain required. Linux file dialogs use the desktop portal or Zenity fallback. Packaging, Windows/macOS, screen-reader integration, physical multi-monitor DPI transitions and long-duration desktop soak tests are not established by these checks. X11 render checks do not establish complete Wayland compatibility. The legacy Tkinter launcher retains `--world SAVE`; the Rust frontend selects saved worlds in Gold instead.

A numerical result, a terrain scan and a successful export do not establish survival construction, rates, modded-server compatibility or new RNG mechanisms. Existing detector, roof and Gold evidence limits still apply. There was no new gameplay test, live-world write or upstream edit during the migration.


## Acceptance continuation, 2026-11-13

The baseline publication checkout and remote main both matched `7b02454e9dd9cb3adfa419cf6caab5ef9dc6f201`, with a clean publication checkout before changes. New checks used Linux 7.3.3-1-cachyos, Python 3.14.9, Rust 1.92.0 and OpenJDK 21.0.12.1, with the existing pinned MCP terrain runtime. This is tool validation, not gameplay evidence.

At the user's direction, continued GUI testing uses `/home/froyln/Dev/ai-desktop.sh` exclusively: isolated headless Sway, `WAYLAND_DISPLAY=wayland-2`, one 1920x1080 virtual output, VNC input and compositor screenshots. Earlier Niri host-session observations are separate and do not establish the isolated result. A private `dbus-run-session` for the test app keeps portal folder dialogs inside isolated Sway rather than routing them through the host session bus. No physical output configuration was changed.

Observed in isolated Sway:

- Actual terrain-backed searches completed in Mob, Fortune, Iron and Gold for seed 12345/view 10/center 0,0. Mode/result screenshots and candidate artifacts were retained privately.
- A native portal folder dialog exported Gold's schematic and plan. Complete decoded NBT and plan equal the calculated candidate. A repeated export raised a file-exists error, retained the candidate and preserved both destination SHA-256 hashes.
- Next location reached an actual terrain scan for candidate 2; Escape cancelled it. Completion of that next search is not claimed.
- 100%, 150% and 200% application scaling and a 760x573 compositor window were inspected. These are virtual-output/application zoom checks, not physical mixed-DPI acceptance.
- At 150%, Tab originally moved focus below the viewport without scrolling. Fixed by revealing the focused control in its owning scroll area after Tab/Shift+Tab and validation focus operations. An actual after-fix screenshot shows the formerly hidden Gold success selector with a visible focus ring. Two focused regression tests cover scroll distances and visible/outside controls. The shared input row now stacks below 940 logical pixels after the 150% capture exposed insufficient width.

Fresh checks passed: 19 core Rust tests, 6 desktop tests (4 existing plus 2 focus tests), 6 worker tests, optimized locked desktop build, agent setup, shared detector, six-species/native roof, combined native, cleanup, next candidates, real vertical terrain (four cases), terrain scanner, portal success selection and portal water scripts. `check_frontend_parity.py` adds five actual calculated full decoded-NBT/plan comparisons for Mob/Fortune/Iron/scheduled Gold/exact Gold through Tk's shared calculation entry points and JSON worker. Terrain is explicitly stubbed in that parity check; independent native and cleanup decoding fixtures remain separate checks. This is not exhaustive setting/UI/cleanup parity.

Tkinter is retained. Both frontends expose the mode settings, but Rust still lacks the legacy `--world SAVE` launcher option. Retirement remains blocked by incomplete desktop acceptance and exhaustive setting/cleanup UI parity. The legacy upstream-JAR launch convenience is also not supplied by Rust. Python/Java/MCP remain intentional dependencies; packaging is deferred.

Still unverified: physical 100/150/200% output-scale transitions between mixed-DPI monitors, screen-reader announcements/navigation (no screen-reader runtime tested), a long soak, cleanup-stage cancellation, a completed actual Next location, exhaustive invalid/no-result/export-error paths and all setting/cleanup UI combinations. Windows/macOS remain untested. Reduced-motion logic passes its state regression; perceptual/motion accessibility acceptance is incomplete. Do not retire the fallback or describe desktop acceptance as complete.

Private captures, logs, calculated exports and the isolated-input harness are under ignored `tools/rng_finder/target/desktop-validation-20261113/`. They are not publication assets. No Minecraft process/world was used for a gameplay trial, no live-world writes were made, and no external publication was performed in this continuation.

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

# World RNG Finder interface design

Design specification, 2026-11-12. The Iced frontend is now implemented; see [implementation and verification](IMPLEMENTATION.md). The Tkinter fallback remains available. Screens use illustrative inputs and empty results; they do not report a calculated candidate.

## Direction and visual system

A dark Minecraft survey notebook with horizontal top tabs and a dark purple palette, following the user’s revised direction. Deep aubergine surfaces, lavender text and purple selection keep the working area quiet and readable. The memorable element is a coordinate ledger in the result, with clearly separated placement minimum, player position and target block. Avoid decorative block textures, rate counters and an unverified map preview. Left-align labels, inputs and result values.

| Token | Value / role |
| --- | --- |
| Background | `#151020`, deep purple main background |
| Surface | `#21182F`, header, editable fields and results |
| Primary text | `#F1EAFB`, pale lavender |
| Purple action | `#7245AC`, primary action and selected tab; white button text |
| Secondary | `#BEB0D0`, supporting and disabled text |
| Caution | `#F0BD76`, errors and evidence limitations, always with text |
| Border / focus | `#49365E` borders; `#CFABFF` focus ring and selected-tab underline |
| Type | Noto Sans, system sans fallback; 14px body/labels, 12px supporting text, 18px section titles, 26px mode title |
| Coordinates | Noto Sans Mono, system monospace fallback, 14px; selectable, signed values, explicit X/Y/Z |
| Spacing | 4, 8, 12, 16, 24, 32 logical pixels; 24px page inset, 16px form gap |
| Controls | At least 36px high; 4px corner radius; 2px lavender keyboard focus ring with 2px offset |

White text on purple buttons; pale lavender text on dark purple surfaces. Use the lavender underline plus bold text for the selected top tab. No color-only status. Do not use secondary text opacity to indicate disabled controls: retain legibility and add a disabled state. Respect platform text scaling and reduced motion.

## Motion

Use short ease-out cubic transitions: button hover 120ms, selected top tab 160ms, Advanced expansion/collapse 180ms and result-surface reveal 180ms. Pressed buttons darken immediately for feedback; avoid layout movement on hover. Interruptions reverse from the current interpolated state. Keep input and export actions available without waiting for an animation. Animate only after interaction or a new result; do not add ambient effects. The visible Reduced motion control and `RNG_REDUCED_MOTION=1` disable transitions. No animation is required to understand state.

## Layout

Default 1120 × 800 logical pixels. A horizontal tab row below the title holds Mob, Fortune, Iron, Gold in that order at every window size. Navigation never moves to a sidebar. World/server settings appear once above mode settings: world creation seed, server view distance and search center X/Z. The seed is explicitly the creation seed, never an internal Random state. Mode drafts survive navigation; world settings are shared. A result belongs to the complete input snapshot and mode that produced it.

At widths below 1000px, keep the top tabs and stack the settings above results. Minimum supported size 760 × 600; both content areas scroll without hiding the active search/cancel action. At larger text scales switch to the stacked layout based on measured content width. Labels wrap; coordinate values remain selectable. Avoid horizontal scrolling of the entire window. The complete plan may use its own horizontal scrollbar for preformatted content.

```text
┌────────────────────────────────────────────────────────────┐
│ World RNG Finder                              Java 1.12.2  │
│ [ Mob ] [ Fortune ] [ Iron ] [ Gold ]                       │
├────────────────────────────────────────────────────────────┤
│ World & server: seed / view distance / X / Z                │
├───────────────────────┬────────────────────────────────────┤
│ Mode settings         │ Candidate                          │
│ ▸ Advanced            │ Placement / player / requirements  │
│ Find candidate        │ Next location / Export             │
└───────────────────────┴────────────────────────────────────┘
Narrow: top tabs → shared inputs → mode settings → result.
```

Wireframes: [Mob](mob.svg), [Fortune](fortune.svg), [Iron](iron.svg), [Gold](gold.svg), and [compact layout / states](states.svg). PNG previews use the same filenames. They specify visual hierarchy, not a live application.

## Mode parity

All defaults and validation must come from the existing handlers, not labels. The current modes have different radius defaults; store radius in the mode draft despite its common meaning. Never reset a hidden setting silently when opening Advanced.

| Mode | Main settings | Advanced, initially collapsed | Result requirements |
| --- | --- | --- | --- |
| Mob | Species: witch/creeper/skeleton/zombie/spider/enderman; player range 1–1 | Radius 25 regions; minimum random Y bound 64 | Actual bound, roof/body clearance, player stack, spawn target; no implied production boost |
| Fortune | Ore: diamond/coal/emerald/quartz/lapis/redstone; Fortune 3; minimum items 4 | Radius 25 regions; maximum RNG advances 0 | Mining position, modeled drop target, input prerequisites; harvesting unverified |
| Iron | No extra required inputs | Radius 128 regions | Village center, first modeled spawn, 24 doors/300 adults, required Nether receiver; collection absent |
| Gold | Difficulty Hard (maps to 3); minimum passing checks 1/3, 2/3, 3/3; optional saved Overworld picker | Radius 25 regions; trace mode off; measured advances 0 enabled only in trace mode | Portal/player/minimum corner, water/gates/receiving channel, cleanup inclusion; trace alignment limits |

Radius label: “Search radius (80-chunk regions)”. Explain that this is not blocks or chunks. Keep 2/3 and 3/3 visible, with “Rarer candidates; no guaranteed rate increase.” Gold trace mode maps to existing exact behavior; measured advances are not used in automatic mode. Do not add a separate unsupported algorithm mode.

Saved-world selection is read-only and Gold-only. Show full path on demand, detected seed and selection errors. The existing picker sets the shared creation seed; make this visible with “Seed loaded from saved world.” Revalidate seed/world agreement before searching if the seed changes. Never repair an invalid level.dat or substitute an earlier scan. Missing optional world: “Cleanup replacements not included.” Export is one native `.litematic` containing full build plus compact cleanup regions when selected, accompanied by the existing text plan. Do not restore separate cleanup-only exports.

## Interaction states

| State | Behavior and copy |
| --- | --- |
| Initial | “Enter a world creation seed, then find a candidate.” Next and Export disabled. No dummy coordinates. |
| Invalid | Inline error next to each invalid input; focus first invalid field. Preserve values. Example: “View distance must be 3–32 chunks.” |
| Searching | Show current stage: calculating, checking terrain, scanning saved world, assembling export. Indeterminate indicator unless the worker supplies a meaningful total. Elapsed time, Cancel visible; no invented percentage. Freeze inputs and mode changes for this request. |
| Cancelling | “Cancelling…” until worker and child processes stop. Discard late responses by request ID; no export from an incomplete result. Never block the UI waiting for termination. |
| Cancelled | Restore editable draft. Retain previous successful result only if its snapshot still matches. “Search cancelled. You can change settings or try again.” |
| No candidate | “No usable candidate in this search.” Show actual rejection reason and suggest increasing radius/changing center. Never downgrade success count automatically. |
| Dependency failure | “Terrain scanner could not start.” Show actual missing Java/Python/build requirement plus expandable technical details. Keep input draft; offer Retry after correction. |
| Ready | Coordinate ledger, build prerequisites, terrain/cleanup summary and evidence limitations, then expandable complete plan. Next location and Export enabled. |
| Input changed | Keep previous result visible with “Settings changed. Find a new candidate to export.” Disable Next/Export until recalculated; do not silently relabel old coordinates. |
| Next location | Search with existing skip/excluded-region semantics; preserve previous valid candidate on failure. Only successful completion replaces it. |
| Exporting | Disable duplicate exports; show stage and keep window responsive. Cancelled file dialog leaves candidate intact. Report write errors without discarding candidate. |
| Exported | Show actual output paths and “Saved schematic and plan.” Only report success after both writes complete. Preserve the current exclusive-create behavior: never overwrite existing outputs; ask the user to choose another folder. Roll back files created by a partially failed export. |

The current `subprocess.run` worker has no cancellation protocol. Cancel is a required implementation task, not an existing capability: termination must cover Rust, Python and Java descendants and temporary files. The Rust UI must receive structured fields for coordinates, requirements, evidence and progress; do not parse rendered labels as an API. Keep raw plan text for review/export.

## Results and accessibility

Result order: candidate/mode → placement minimum X/Y/Z → player/AFK X/Y/Z → mode target → required build/clearance → cleanup and terrain coverage → evidence limitations → full plan. Each coordinate row has a named Copy action; preserve half-block positions. Show only fields actually returned. Put critical receiver, roof, clearing and startup requirements above the full-plan disclosure. Distinguish sampled seed terrain from a saved-world scan.

Use “Modeled candidate” as the status, never “Verified farm.” Summaries link to the existing evidence records. Gold prepared-world success is distinct from trace modes, modded servers and survival construction; Mob's comparable no-input control prevents a rate claim. Export does not mean gameplay reproduced.

Tab sequence: mode selector → shared fields → visible mode fields → Advanced → revealed advanced fields → Find/Cancel → result Copy actions → Next location → Export → complete plan. Mode selector supports arrow keys; Space/Enter activates focused buttons, Escape cancels an active search, Ctrl+Enter starts a valid idle search, Ctrl+S opens export only when enabled. File dialogs retain native behavior. Errors and status changes need accessible labels/announcements; verify Iced accessibility on the target desktop before claiming support. Focus returns to the initiating action after dialogs and cancellation. Expanding Advanced moves no focus unexpectedly.

## Review and implementation handoff

Reviewed against the requested brief: all four modes and legacy trace options accounted for; shared inputs remove duplication; advanced fields retain exact backend meaning; results prioritize placement and construction. Removed decorative map/rate ideas because no reliable data currently supports them. Applied the subject-specific palette/type/layout and review principles from the reviewed [frontend-design guidance](https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md), adapted to desktop rather than web hero layouts.

Implementation references: `tools/rng_finder/gui.py`, `backend.py`, `desktop_worker.py` and `desktop/src/{main,worker,focus}.rs`. [Validation limits](../VALIDATION.md) distinguish inspected algorithms, prepared-world evidence and unverified survival/rate claims.

Migration acceptance checklist (implementation results are recorded separately):

1. Prove Iced rendering, native file dialogs, fonts, DPI and a cancellable background task on the target desktop. Retain Tkinter until parity passes.
2. Extract the smallest headless Python worker boundary reusing existing calculation/export/terrain code; structured request/result/progress/error messages and process cancellation. No NBT or terrain rewrite.
3. Implement the layouts and all modes with input snapshots, validation and native export parity. Compare blocks, tile entities, origins and cleanup subregions against the accepted detector/roof baseline.
4. Review actual application screenshots at wide/compact sizes and 100/150/200% text scaling. Exercise focus, errors, cancel during terrain/cleanup, Next failure and export failure. Static mockup review does not pass this gate.
5. Run 19 current Rust tests and affected Python/native/terrain/export checks. Update requirements and evidence status. External publication requires authorization.

User revision: horizontal top tabs and dark purple mode replace the original sidebar/light proposal in all mode and state previews.

Design verification: SVGs rendered to PNG and visually reviewed. The subsequent Rust implementation has separate runtime checks and screenshots in [the migration record](IMPLEMENTATION.md); platform accessibility beyond keyboard operation remains unverified. No upstream source or gameplay world changed.

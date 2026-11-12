# Selecting one, two or three portal checks, 2026-11-12

## Requested behavior

Gold has a readonly target selector1/3(default),2/3,3/3. These are **minimum successful checks per aligned tick**, not randomTickSpeed values or guaranteed measured-rate multipliers. The CLI accepts `--portal-successes 1|2|3` in portal mode only. Search skips regions which do not meet the target and never silently falls back. The existing finite radius/fixed portal rank remain;2/3 and especially3/3 candidates are rarer, so a given seed/search area may have no match. Existing1/3 candidate ordering and layouts are preserved.

## Inspected algorithm

Pinned MCP stable39, Minecraft1.12.2 source jar SHA256bb7fbb57cd96d3096a641d38af0de14e8dff9d748ebb8ccc8b0e7d45edf96d61: `WorldServer.updateBlocks` makes three random-tick positions per active section at defaultRTS3; a full portal section makes every selected cell a portal. `BlockPortal.updateTick` uses `World.rand.nextInt(2000)<difficulty`, then calls `ItemMonsterPlacer.spawnCreature`.

Successful spawning is not just a skipped roll: `ItemMonsterPlacer.spawnCreature` uses one World.rand.nextFloat for yaw. Inherited `EntityZombie.onInitialSpawn` with null group data uses one World.rand.nextFloat for baby selection; a baby uses another for an existing-chicken attempt, and only if that roll fails another for the new-chicken attempt. Entity-owned Random draws in construction/attributes/equipment/sounds are separate and are not substituted for World.rand. `EntityChicken.onInitialSpawn` does not add World.rand draws on this path. `portal_spawn_draws` models these2/3/4draw branches, then `portal_success` continues checking until the requested number passes or three checks are exhausted. A passing check must actually be able to spawn; blocked floors or modded hooks invalidate later predictions.

## Independent reference and actual-method checks

`tests/PortalSpawnSequenceProbe.java` runs the actual pinned `BlockPortal.updateTick` and `ItemMonsterPlacer.spawnCreature` methods in a controlled Unsafe-allocated WorldServer fixture. World services supply a stone floor, empty nearby chicken list, fixed date/difficulty, no-op sounds and entity insertion. This is an algorithm check, not live gameplay. It compares post-spawn java.util.Random state via nextLong for513 initializations, including seed16414 for the rare baby/existing-chicken branch. Entity-owned random seeds vary independently.

At mansion region(0,0), tick rank82, view10 and Hard:

| World seed | Actual three portal rolls with successful-spawn calls | Actual inserted pigmen |
|---|---|---:|
|171656809007210|1,2,669|2|
|84785424703645|0,2,1|3|

These are intentionally constructed known seeds, not a claim that an arbitrary user seed has nearby3/3candidates. Derived target internal states866174 and365587603 were found by standalone finite-state search and inverted90LCGsteps; full Java bounded calls independently confirm them. Rust tests include all three spawn-draw branches and the known two/three-success results. Python checks validate all selector CLI values, nonmatching3/3failure with no output created, mode/range errors, exported target/conditional check and desktop forwarding. Existing pinned tick/combined/native/cleanup checks pass. Private Xvfb GUI smoke confirms default/options, readonly restoration and result invalidation.

## Boundaries

No user save is edited. Existing terrain/collision/sliced-portal and cleanup requirements still apply; no grid shape or farm coordinates are changed merely by selecting a count. A new matching region can relocate the whole candidate. Tick rank is currently fixed by the existing planner, not an exhaustive search of every possible chunk arrangement. No claim of automatic3xgold collection, long-term stability, survival construction or universal server-fork compatibility follows from these checks.

## Prepared export follow-up

Actual combined exports in separate disposable vanilla worlds produced2365new pigmen/100.888s for2/3 and3114/100.876s for3/3, each from one Survival lever click followed by two autosave-driven restarts. These are short trials with constructed reference seeds, not a controlled exactrate-multiplier test. Both fixed modes passed1/1run. Environment/settings/logs/exact schematics and offline checks are retained in the private research workspace under research/experiments/pigman-multiple-ticks/; raw world-specific logs are not bundled here. No new Kisde or user-world gameplay test.

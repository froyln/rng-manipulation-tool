# Minecraft 1.12.2 RNG manipulation tool

A Rust candidate calculator and Iced desktop interface for Minecraft Java **1.12.2** world-RNG manipulation. The Gold tab exports a complete Pigman RNG machine with an autosave detector, one start lever, sliced portals, stepped packed-ice/water spawn floors and an optional saved-world cleanup overlay.

The current Pigman template omits accidentally captured trees/plants and the obsolete button-delay branch. With a saved Overworld selected, the export is **one `.litematic`** containing the machine and actual nonflammable red-concrete replacement blocks, split into compact subregions. These are exact replacement positions, not borders. Other modes include hostile-mob, Fortune and iron-golem candidate calculations; they have different verification limits.

## Requirements

- Rust/Cargo to build the calculator.
- Python 3 for the headless assembly/terrain worker; no pip packages required. Tkinter is needed only for the retained legacy interface.
- Linux desktop with a file-dialog portal or Zenity fallback for the Rust UI; other platforms are not yet verified.
- A JDK (`java` and `javac`) and a locally prepared **MCP stable-39, Minecraft 1.12.2 deobfuscated runtime** with its dependencies for desktop terrain scanning and native palette conversion. Java 8 was used for gameplay tests. Minecraft binaries and decompiled game code are not included.

The command-line calculator works without the Minecraft runtime. **The desktop Find action requires it**, including when a saved world is selected.

## Build and launch

From the repository root:

```sh
cargo build --release --manifest-path tools/rng_finder/Cargo.toml
cargo run --release --locked --manifest-path tools/rng_finder/desktop/Cargo.toml
```

The Rust UI has horizontal top tabs, dark purple styling, short hover/tab/panel animations and a Reduced motion control (`RNG_REDUCED_MOTION=1` to disable transitions at startup). All four modes share world/server inputs and retain their own settings. Search/terrain/cleanup/export run in a background worker; Find/Cancel, Next and Export remain visible while panels scroll. The footer supports 100/150/200% scaling.

Use Ctrl+Enter to search, Escape to cancel and Ctrl+S to export. Tab/Shift+Tab moves focus; Enter/Space activates buttons and Left/Right changes focused tabs or choices. Review coordinates, build requirements and the complete plan before export. Existing files are never overwritten. [Preview and verification](docs/interface/IMPLEMENTATION.md).

The Tkinter fallback remains available with `python3 tools/rng_finder/gui.py` (including its existing `--world SAVE` argument). It may need your operating system's Python Tk package (`python3-tk` on Debian/Ubuntu). The Rust UI selects saved worlds in Gold. Python and Java remain required: this is not a Python-free distribution.

Configure the deobfuscated runtime before searching in either GUI. By default the scanner looks under `$GRADLE_USER_HOME/caches` (or `~/.gradle/caches`) for:

```text
minecraft/net/minecraft/minecraft/1.12.2/stable/39/minecraftBin-1.12.2.jar
modules-2/files-2.1/**/*.jar
```

This is the existing MCP/ForgeGradle cache layout, **not an ordinary vanilla server jar**. If your legally obtained local development runtime is elsewhere, provide its full Java classpath, including dependencies:

```sh
export RNG_MINECRAFT_CLASSPATH='/path/to/minecraftBin-1.12.2.jar:/path/to/dependency.jar'
cargo run --release --locked --manifest-path tools/rng_finder/desktop/Cargo.toml
```

Use `;` instead of `:` between classpath entries on Windows. This repository does not download or set up MCP for you. A missing runtime causes an explicit setup error.

For the standalone interactive calculator:

```sh
cargo run --release --manifest-path tools/rng_finder/Cargo.toml
```

## Verification

```sh
cargo test --manifest-path tools/rng_finder/Cargo.toml
cargo test --locked --manifest-path tools/rng_finder/desktop/Cargo.toml
python3 tools/rng_finder/tests/check_desktop_worker.py
python3 tools/rng_finder/tests/check_autosave_schematic.py
python3 tools/rng_finder/tests/check_combined_schematic.py
```

With the configured MCP runtime:

```sh
python3 tools/rng_finder/tests/check_portal_tick_model.py
python3 tools/rng_finder/tests/check_portal_successes.py
python3 tools/rng_finder/tests/check_portal_water.py
python3 tools/rng_finder/tests/check_shared_detector.py
python3 tools/rng_finder/tests/check_mob_roof.py
python3 tools/rng_finder/tests/check_combined_litematic.py
python3 tools/rng_finder/tests/check_rng_cleanup.py
```

Build the release binary before Python checks. Additional focused checks are in `tools/rng_finder/tests/`. These are script-based checks, not all discoverable by unittest. See [validation limits](docs/VALIDATION.md) and [source attribution](THIRD_PARTY.md).

Portal CLI searches accept `--portal-successes 1`, `2` or `3` (default1), for example:

```sh
tools/rng_finder/target/release/rng-finder --portal 84785424703645 3 0 0 0 0 10 output --portal-tick-model --portal-successes 3
```

That constructed reference seed matches3/3at region0,0; it is not a recommendation to use someone else's world seed/coordinates. The search accounts for successful-spawn yaw and baby/jockey World.rand calls before later checks. See [multi-check model and limits](docs/MULTIPLE_TICKS.md). An aligned three-spawn tick is not a guaranteed3xhourly farm yield.

The default sliced Pigman template transports mobs toward+Z over packed ice, through open fence gates and into a dry receiving channel outside the portal chunk. Leave the outlet gates open and empty/connect the receiving channel to your own collection system. When upgrading an old flat-floor build, remove the old last floor row identified in the new plan before a non-air paste. Always use the new plan's placement origin: the lower receiving floor changes the schematic origin while portal/grid/AFK world coordinates stay fixed. Legacy trace-mode frames retain their old layout.

## Shared detector and Mob roof

Mob, Fortune, Iron and Gold trace/manual preserve Xcom’s loading lattice while using Command’s shared sand detector. Leave the single AFK lever on; regenerate the complete build and follow its new minimum corner. Clear obsolete detector blocks before a non-air retrofit. Scheduled Gold keeps its grid, ice/water platform and native compact cleanup export.

Mob candidates include a non-spawnable opaque bottom-stone-slab roof with a 15-block overhang, a three-block interior and species clearance. Search rejects incompatible height bounds or circuit conflicts. Clear the listed interior/floor volumes before non-air placement, and spawn-proof terrain below the roof shadow. The sampled-column control remains above the roof. [Evidence and limits](docs/VALIDATION.md).

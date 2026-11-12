# Minecraft 1.12.2 RNG manipulation tool

A Rust candidate calculator and Python desktop interface for Minecraft Java **1.12.2** world-RNG manipulation. The Gold tab exports a complete Pigman RNG machine with an autosave detector, one start lever, sliced portals and an optional saved-world cleanup overlay.

The current Pigman template omits accidentally captured trees/plants and the obsolete button-delay branch. With a saved Overworld selected, the export is **one `.litematic`** containing the machine and actual nonflammable red-concrete replacement blocks, split into compact subregions. These are exact replacement positions, not borders. Other modes include hostile-mob, Fortune and iron-golem candidate calculations; they have different verification limits.

## Requirements

- Rust/Cargo to build the calculator.
- Python 3 with Tkinter for the desktop interface; no pip packages required.
- A JDK (`java` and `javac`) and a locally prepared **MCP stable-39, Minecraft 1.12.2 deobfuscated runtime** with its dependencies for desktop terrain scanning and native palette conversion. Java 8 was used for gameplay tests. Minecraft binaries and decompiled game code are not included.

The command-line calculator works without the Minecraft runtime. **The desktop Find action requires it**, including when a saved world is selected.

## Build and launch

From the repository root:

```sh
cargo build --release --manifest-path tools/rng_finder/Cargo.toml
python3 tools/rng_finder/gui.py
```

Tkinter may need your operating system's Python Tk package (`python3-tk` on Debian/Ubuntu). Configure the deobfuscated runtime before searching in the GUI. By default the scanner looks under `$GRADLE_USER_HOME/caches` (or `~/.gradle/caches`) for:

```text
minecraft/net/minecraft/minecraft/1.12.2/stable/39/minecraftBin-1.12.2.jar
modules-2/files-2.1/**/*.jar
```

This is the existing MCP/ForgeGradle cache layout, **not an ordinary vanilla server jar**. If your legally obtained local development runtime is elsewhere, provide its full Java classpath, including dependencies:

```sh
export RNG_MINECRAFT_CLASSPATH='/path/to/minecraftBin-1.12.2.jar:/path/to/dependency.jar'
python3 tools/rng_finder/gui.py
```

Use `;` instead of `:` between classpath entries on Windows. This repository does not download or set up MCP for you. A missing runtime causes an explicit setup error.

For the standalone interactive calculator:

```sh
cargo run --release --manifest-path tools/rng_finder/Cargo.toml
```

## Verification

```sh
cargo test --manifest-path tools/rng_finder/Cargo.toml
python3 tools/rng_finder/tests/check_autosave_schematic.py
python3 tools/rng_finder/tests/check_combined_schematic.py
```

With the configured MCP runtime:

```sh
python3 tools/rng_finder/tests/check_portal_tick_model.py
python3 tools/rng_finder/tests/check_combined_litematic.py
python3 tools/rng_finder/tests/check_rng_cleanup.py
```

Build the release binary before Python checks. Additional focused checks are in `tools/rng_finder/tests/`. These are script-based checks, not all discoverable by unittest. See [validation limits](docs/VALIDATION.md) and [source attribution](THIRD_PARTY.md).

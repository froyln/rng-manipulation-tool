# Source attribution

The calculator and integration were developed in the Threadstone research workspace. Minecraft is a Mojang/Microsoft product. No Minecraft binaries or decompiled Minecraft source are distributed here. No ownership of third-party designs is claimed.

## Command: tile-tick grid and autosave detector

Original reference downloads are preserved unchanged in `sources/GridTileTick.schematic` and `sources/AutoSaveDetector.schematic`. They were supplied through Command's tutorial in RandomFT's SSP & C Discord:

- [Tutorial thread](https://discord.com/channels/1544612219663421493/1563282308004319374)
- [Grid/detector download post](https://discord.com/channels/1544612219663421493/1563282308004319374/1563314657891057694)
- [Detector placement explanation](https://discord.com/channels/1544612219663421493/1563282308004319374/1563456452532641792)

SHA256:

```text
997bdacda330deae58adbe01b52e228133eedf9c3f89658b0254f0b443c3d8ac  sources/GridTileTick.schematic
69dfe99227086ac92cadb928588974ad53786eb096ce3994c9d381193609a42a  sources/AutoSaveDetector.schematic
```

`tools/rng_finder/reference/prepare_tile_grid.py` creates the adapted1.12research copies: blue terracotta supports, legacy tile-entity ID conversion, removal of original debug blocks/button, accidentally captured trees/plants and obsolete button delay. The desktop adds its own connected lever/detector routes. The originals remain unchanged. The older tutorial's1.7region and chunk-order rules are not substituted for the1.12.2model.

## Xcom: original loading-grid reference

`tools/rng_finder/reference/xcom-chunk-loading-grid.schematic` and `xcom-detector.nbt` preserve the original Xcom reference used by the other calculator modes. See [Xcom's RNG explanation](https://www.youtube.com/watch?v=hC88NnanFFA), especially9:50–11:17 for control-platform/loading placement. Video descriptions do not independently prove every implementation detail.

## RandomFT and RNG research

RandomFT's Pigman tools and tick-order explanations informed the1.12research; Command's older tutorial supplied the physical references above. The exported program is an independently developed calculator/integration, not a redistribution of their calculator JARs. Source authors retain rights to their designs/assets; no blanket relicensing of these third-party materials is implied.

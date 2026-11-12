# Pigman water transport

The default scheduled/sliced Gold export uses packed ice, which does not melt like ordinary ice. Two reachable drops maintain the north-to-south water stream across the16x16spawn floor. Open fence gates at the south edge stop water while pigmen fall into a contained dry receiving channel outside the portal chunk. Portal/grid/AFK world coordinates are unchanged; the lower receiving floor changes the component and combined placement origin. Use the new plan origin.

For retrofits, clear the old flat floor's final row identified in the generated plan before non-air pasting. Leave outlet gates open, keep lanes/headroom clear and connect/empty the finite receiving basin. No killing or item collection system is supplied. Legacy manual/exact-mode frames retain their old floor.

Prepared vanilla1.12.2 test:1174new pigman UUIDs in101.17seconds after one Survival lever click and automatic detector cycles.483matching saved UUIDs moved from portal birth positions into the outside dry channel; no older surviving pigmen remained upstream at the final save. All4096portals,288watercells,288packedice blocks and16open gates persisted; no water escaped the channel. Missing/dead UUIDs are not counted as proven transport. Earlier unreachable-step and wet-basin candidates were rejected, not included as successful final trials.

Environment: official1.12.2 vanilla jar SHA256fe1f9274e6dad9191bf6e6e8e36ee6ebc737f373603df0946aafcded0d53167e, Java8u512, AMD Ryzen52600,256–768MBheap, one Survival player, prepared Overworld seed7480186273489543341, view10, Hard, clear, normal20TPS target, RTS3/spawningtrue/defaultcramming24. This is prepared construction, not a new live Kisde/survival-built/long-duration or gold-yield result. Private raw logs/settings/UUIDaudits remain in the research workspace.

Run `python3 tools/rng_finder/tests/check_portal_water.py` with the configured MCP runtime and built release binary to verify floor grades, fluid states, source row, open gates, containment/headroom, unchanged portal coordinates, route compatibility and native palette conversion.

A final3/3load follow-up also passed:2266newUUIDs/81.06seconds,488matching saved survivors outside the portal chunk, no older survivor upstream, stable288watercells/4096portals and clean shutdown. These short prepared-world trials still require an emptied/connected receiving channel for continued operation.

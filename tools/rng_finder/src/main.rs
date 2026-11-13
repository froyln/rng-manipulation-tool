use std::io::{self, Write};
use std::path::Path;

const MULT: u64 = 0x5deece66d;
const MASK: u64 = (1 << 48) - 1;

#[derive(Clone, Copy)]
struct JavaRandom(u64);
impl JavaRandom {
    fn new(seed: i64) -> Self {
        Self((seed as u64 ^ MULT) & MASK)
    }
    fn next(&mut self, bits: u32) -> u32 {
        self.0 = self.0.wrapping_mul(MULT).wrapping_add(11) & MASK;
        (self.0 >> (48 - bits)) as u32
    }
    fn next_int_unbounded(&mut self) -> i32 {
        self.next(32) as i32
    }
    fn next_int(&mut self, bound: i32) -> i32 {
        assert!(bound > 0);
        if bound & (bound - 1) == 0 {
            return ((bound as i64 * self.next(31) as i64) >> 31) as i32;
        }
        loop {
            let bits = self.next(31) as i32;
            let value = bits % bound;
            if bits.wrapping_sub(value).wrapping_add(bound - 1) >= 0 {
                return value;
            }
        }
    }
}

fn parse_seed(input: &str) -> i64 {
    if let Ok(n) = input.parse::<i64>() {
        return n;
    }
    input
        .encode_utf16()
        .fold(0_i32, |h, c| h.wrapping_mul(31).wrapping_add(c as i32)) as i64
}

fn mansion_reset_rng(seed: i64, region_x: i32, region_z: i32) -> JavaRandom {
    let seed = (region_x as i64)
        .wrapping_mul(341873128712)
        .wrapping_add((region_z as i64).wrapping_mul(132897987541))
        .wrapping_add(seed)
        .wrapping_add(10387319);
    let mut rng = JavaRandom::new(seed);
    for _ in 0..4 {
        rng.next_int(60);
    }
    rng
}

fn portal_success(rng: &mut JavaRandom, difficulty: i32, required: usize) -> Option<(usize, i32)> {
    // Successful ItemMonsterPlacer/EntityZombie spawns consume World.rand before the next check.
    let mut successes = 0;
    for attempt in 1..=3 {
        let roll = rng.next_int(2000);
        if roll < difficulty {
            successes += 1;
            if successes == required { return Some((attempt, roll)); }
            portal_spawn_draws(rng);
        }
    }
    None
}

fn portal_spawn_draws(rng: &mut JavaRandom) {
    rng.next(24); // ItemMonsterPlacer: yaw.
    if (rng.next(24) as f64 / 16_777_216.0) < 0.05 { // EntityZombie: baby.
        if (rng.next(24) as f64 / 16_777_216.0) >= 0.05 {
            rng.next(24); // New-chicken check only when the existing-chicken roll fails.
        }
    }
}

fn portal_tick_candidate(
    seed: i64,
    region_x: i32,
    region_z: i32,
    tick_rank: usize,
    difficulty: i32,
    required: usize,
) -> Option<(usize, i32)> {
    let mut rng = mansion_reset_rng(seed, region_x, region_z);
    rng.next_int(1);
    for _ in 0..3 {
        rng.next_int(11);
    }
    for _ in 0..tick_rank {
        rng.next_int(16);
    }
    portal_success(&mut rng, difficulty, required)
}

fn chunk_hash(x: i32, z: i32) -> u32 {
    let sx = 1664525_i32.wrapping_mul(x).wrapping_add(1013904223);
    let sz = 1664525_i32
        .wrapping_mul(z ^ 0xdeadbeefu32 as i32)
        .wrapping_add(1013904223);
    let h = (sx ^ sz) as u32;
    h ^ (h >> 16)
}

// shortcut: assumes a freshly sized Java 8 HashSet and a complete sent-chunk square.
fn first_spawn_chunk(player_x: i32, player_z: i32, view: i32) -> (i32, i32) {
    let radius = view.min(7);
    let count = ((2 * radius + 1) * (2 * radius + 1)) as u32;
    let capacity = ((count * 4 + 2) / 3).next_power_of_two().max(16);
    let mut first = (u32::MAX, (0, 0));
    for dx in -radius..=radius {
        for dz in -radius..=radius {
            let p = (player_x + dx, player_z + dz);
            let bucket = chunk_hash(p.0, p.1) & (capacity - 1);
            if bucket < first.0 {
                first = (bucket, p);
            }
        }
    }
    first.1
}

#[cfg(test)]
fn grid_in_player_view(player: (i32, i32, i32), region_x: i32, region_z: i32, view: i32) -> bool {
    let gx = region_x * 1280 - 112;
    let gz = region_z * 1280 - 112;
    let pcx = player.0.div_euclid(16);
    let pcz = player.2.div_euclid(16);
    pcx + view >= gx.div_euclid(16)
        && pcx - view <= (gx + 351).div_euclid(16)
        && pcz + view >= gz.div_euclid(16)
        && pcz - view <= (gz + 1039).div_euclid(16)
}

// The vanilla spawner counts positions not present in its eligible set once per player.
fn control_position(region_x: i32, region_z: i32, view: i32) -> (i32, i32, i32) {
    let gx = region_x * 1280 - 112;
    let gz = region_z * 1280 - 112;
    (gx + 10 * 16 + 8, 66, gz + (1 - view) * 16 + 8)
}

fn warn_control_boundary(plan: &Path, region_x: i32, region_z: i32, view: i32) -> io::Result<()> {
    let mut file = std::fs::OpenOptions::new().append(true).open(plan)?;
    let (x, _, z) = control_position(region_x, region_z, view);
    writeln!(file, "\nCONTROL BOUNDARY: reference player column X {x}, Z {z}; use the player Y reported above. The preserved blue control platform is inside the view square and row 2 onwards is outside. The replacement sand detector is placed separately at the north lazy boundary; its priming reaches beyond the player view square. The portal setup uses the adjacent chunk to the east. Some starter-line blocks share the loaded detector row. This is a geometric candidate, not proof of ticking, unloading, calibration, or a working reset cycle. Verify in a disposable 1.12.2 world.")
}

fn hostile_threshold(view: i32, players: i32) -> i32 {
    let diameter = 2 * view.min(7) + 1;
    let eligible = diameter * diameter;
    70 * (289 + (players - 1) * (289 - eligible)) / 289
}

#[derive(Clone, Copy)]
enum Mob {
    Witch,
    Creeper,
    Skeleton,
    Zombie,
    Spider,
    Enderman,
}
impl Mob {
    fn matches(self, weight: i32) -> bool {
        match self {
            Mob::Spider => (0..100).contains(&weight),
            Mob::Zombie => (100..195).contains(&weight),
            Mob::Skeleton => (200..300).contains(&weight),
            Mob::Creeper => (300..400).contains(&weight),
            Mob::Enderman => (500..510).contains(&weight),
            Mob::Witch => (510..515).contains(&weight),
        }
    }
    fn name(self) -> &'static str {
        match self {
            Mob::Witch => "witch",
            Mob::Creeper => "creeper",
            Mob::Skeleton => "skeleton",
            Mob::Zombie => "zombie",
            Mob::Spider => "spider",
            Mob::Enderman => "enderman",
        }
    }
}

#[derive(Debug, PartialEq)]
struct Candidate {
    region_x: i32,
    region_z: i32,
    player: (i32, i32, i32),
    first_chunk: (i32, i32),
    initial: (i32, i32, i32),
    attempts: [(i32, i32, i32); 4],
    weight: i32,
    y_bound: i32,
}

fn candidate(
    seed: i64,
    rx: i32,
    rz: i32,
    y_bound: i32,
    mob: Mob,
    offset: (i32, i32),
    view: i32,
) -> Option<Candidate> {
    let seed = (rx as i64)
        .wrapping_mul(341873128712)
        .wrapping_add((rz as i64).wrapping_mul(132897987541))
        .wrapping_add(seed)
        .wrapping_add(10387319);
    let mut rng = JavaRandom::new(seed);
    for _ in 0..4 {
        rng.next(32);
    }
    let x_in_chunk = rng.next_int(16);
    let z_in_chunk = rng.next_int(16);
    let y = rng.next_int(y_bound);
    let dx = rng.next_int(6) - rng.next_int(6);
    let _dy = rng.next_int(1) - rng.next_int(1);
    let dz = rng.next_int(6) - rng.next_int(6);
    // These intervals follow the normal-biome hostile weights in LightningFinder MobList.
    let weight = rng.next_int(515);
    // The AFK player stands one block higher and its detector adapter rises12more blocks.
    if !mob.matches(weight) || y < 5 || y > 242 || y > y_bound - 6 {
        return None;
    }
    let px = rx
        .checked_mul(1280)?
        .checked_add(512)?
        .checked_add(offset.0)?;
    let pz = rz
        .checked_mul(1280)?
        .checked_add(512)?
        .checked_add(offset.1)?;
    let player = (px, y + 1, pz);
    let chunk = first_spawn_chunk(px.div_euclid(16), pz.div_euclid(16), view);
    let x = chunk.0 * 16 + x_in_chunk;
    let z = chunk.1 * 16 + z_in_chunk;
    let mut attempt = (x + dx, y, z + dz);
    let dist_x = attempt.0 as i64 - px as i64;
    let dist_z = attempt.2 as i64 - pz as i64;
    if dist_x * dist_x + dist_z * dist_z < 24 * 24 {
        return None;
    }
    let mut attempts = [attempt; 4];
    rng.next(24); // The spawning routine draws nextFloat after each eligible attempt.
    for next in attempts.iter_mut().skip(1) {
        let (last_x, last_y, last_z) = attempt;
        let dx = rng.next_int(6) - rng.next_int(6);
        let dy = rng.next_int(1) - rng.next_int(1);
        let dz = rng.next_int(6) - rng.next_int(6);
        *next = (last_x + dx, last_y + dy, last_z + dz);
        attempt = *next;
        rng.next(24);
    }
    for &(x, _, z) in &attempts {
        let dx = x as i64 - px as i64;
        let dz = z as i64 - pz as i64;
        if dx * dx + dz * dz < 24 * 24 {
            return None;
        }
    }
    Some(Candidate {
        region_x: rx,
        region_z: rz,
        player,
        first_chunk: chunk,
        initial: (x, y, z),
        attempts,
        weight,
        y_bound,
    })
}

fn prompt(msg: &str, default: Option<&str>) -> io::Result<String> {
    print!("{}", msg);
    io::stdout().flush()?;
    let mut input = String::new();
    io::stdin().read_line(&mut input)?;
    let input = input.trim();
    if input.is_empty() {
        Ok(default.unwrap_or("").to_owned())
    } else {
        Ok(input.to_owned())
    }
}

fn number(prompt_text: &str, default: &str) -> Result<i32, Box<dyn std::error::Error>> {
    Ok(prompt(prompt_text, Some(default))?.parse()?)
}

fn ore_quantity(rng: &mut JavaRandom, ore: &str, fortune: i32) -> i32 {
    if ore == "redstone" {
        return 4 + rng.next_int(2) + rng.next_int(fortune + 1);
    }
    let bonus = if fortune > 0 {
        (rng.next_int(fortune + 2) - 1).max(0)
    } else {
        0
    };
    let base = if ore == "lapis" {
        4 + rng.next_int(5)
    } else {
        1
    };
    base * (bonus + 1)
}

fn fortune_main(args: &[String], skip: usize) -> Result<(), Box<dyn std::error::Error>> {
    if args.len() != 11 {
        return Err("Fortune mode requires seed, ore, level, minimum drops, X, Z, radius, maximum advances, view distance and output directory".into());
    }
    let seed = parse_seed(&args[1]);
    let ore = args[2].to_ascii_lowercase();
    if args[1].trim().is_empty()
        || !["diamond", "coal", "emerald", "quartz", "lapis", "redstone"].contains(&ore.as_str())
    {
        return Err("Enter a seed and a supported ore".into());
    }
    let level: i32 = args[3].parse()?;
    let target: i32 = args[4].parse()?;
    let x: i32 = args[5].parse()?;
    let z: i32 = args[6].parse()?;
    let radius: i32 = args[7].parse()?;
    let advances: i32 = args[8].parse()?;
    let view: i32 = args[9].parse()?;
    if !(0..=3).contains(&level)
        || !(1..=32).contains(&target)
        || !(0..=128).contains(&radius)
        || !(0..=1000).contains(&advances)
        || !(3..=32).contains(&view)
        || x.unsigned_abs() > 29_000_000
        || z.unsigned_abs() > 29_000_000
    {
        return Err(
            "Invalid level, minimum drops, coordinates, radius, advances or view distance".into(),
        );
    }
    let max_drops = match ore.as_str() {
        "redstone" => 5 + level,
        "lapis" => 8 * (level + 1),
        _ => level + 1,
    };
    if target > max_drops {
        return Err(
            format!("That ore and Fortune level can drop at most {max_drops} items").into(),
        );
    }
    let rx = (x + 128).div_euclid(1280);
    let rz = (z + 128).div_euclid(1280);
    let mut found = None;
    let mut remaining = skip;
    'search: for distance in 0..=radius {
        for dx in -distance..=distance {
            let dz = distance - dx.abs();
            'region: for signed_z in if dz == 0 { vec![0] } else { vec![-dz, dz] } {
                let (region_x, region_z) = (rx + dx, rz + signed_z);
                let mining = control_position(region_x, region_z, view);
                let local_seed = (region_x as i64)
                    .wrapping_mul(341873128712)
                    .wrapping_add((region_z as i64).wrapping_mul(132897987541))
                    .wrapping_add(seed)
                    .wrapping_add(10387319);
                let mut rng = JavaRandom::new(local_seed);
                for _ in 0..4 {
                    rng.next(32);
                }
                for count in 0..=advances {
                    let drops = ore_quantity(&mut rng.clone(), &ore, level);
                    if drops >= target {
                        if remaining > 0 {
                            remaining -= 1;
                            continue 'region;
                        }
                        found = Some((region_x, region_z, mining, count, drops));
                        break 'search;
                    }
                    rng.next(32);
                }
            }
        }
    }
    let (region_x, region_z, mining, count, drops) =
        found.ok_or("No matching region within the chosen radius and advance limit")?;
    let grid_x = region_x * 1280 - 112;
    let grid_z = region_z * 1280 - 112;
    let path = Path::new(&args[10]);
    if ["rng-combined.schematic", "rng-combined-plan.txt", "autosave-detector.schematic"].iter().any(|name| path.join(name).exists()) {
        return Err("Output files already exist; choose another directory".into());
    }
    std::fs::create_dir_all(path)?;
    let grid = path.join("xcom-original-grid.schematic");
    let plan = path.join("rng-finder-plan.txt");
    if grid.exists() || plan.exists() {
        return Err("Output files already exist; choose another directory".into());
    }
    std::fs::write(
        &grid,
        include_bytes!("../reference/xcom-shared-detector-grid.schematic"),
    )?;
    std::fs::write(&plan, format!("Minecraft Java 1.12.2 Fortune-drop candidate (experimental)\nWorld seed: {seed}\nOre: {ore}; Fortune: {level}; requested minimum: {target}\nSearch center: {x}, {z}; radius: {radius} regions\nServer view distance: {view}\nMansion region: {region_x}, {region_z}\nSuggested mining/player position: {}, {}, {} (check terrain)\nModeled drop quantity: {drops} items from one ore\nModeled advances after reset: {count} unbounded nextInt calls\n\nGrid schematic: {}\nPlacement minimum corner (local 0,0,0): {grid_x}, 64, {grid_z}\nOrientation: unchanged\nAutosave detector approximate bounds: {}, 67, {} to {}, 71, {}\n\nAssumes an Overworld mansion-region world RNG reset, four nextInt calls, exactly {count} additional unbounded nextInt calls, no other world RNG calls before quantity selection, a normal Fortune harvest, and drops enabled. Redstone ore activation can consume world RNG before the harvest; quartz ore must be brought to the Overworld. Hopper/piston advance mechanisms need separate verification. XP and consecutive ore breaks are not modeled. The original loading grid, its calibration, and this mining setup have not been validated as a complete build. Test in a disposable 1.12.2 world.\n", mining.0, mining.1, mining.2, grid.display(), grid_x+194, grid_z+9, grid_x+206, grid_z+17))?;
    warn_control_boundary(&plan, region_x, region_z, view)?;
    finish_detector_export(path)?;
    println!("Saved {} and {}", grid.display(), plan.display());
    Ok(())
}

// Fresh single-player PlayerChunkMap insertion order; movement retains list history.
fn portal_tick_order(player_x: i32, player_z: i32, view: i32) -> Vec<(i32, i32, i32)> {
    let (cx, cz) = (player_x.div_euclid(16), player_z.div_euclid(16));
    let mut chunks = Vec::new();
    for x in cx - view..=cx + view {
        for z in cz - view..=cz + view {
            let dx = (x * 16 + 8 - player_x) as f64 - 0.5;
            let dz = (z * 16 + 8 - player_z) as f64 - 0.5;
            if dx * dx + dz * dz < 16384.0 {
                chunks.push((x, z, (x - cx + view) * (2 * view + 1) + z - cz + view));
            }
        }
    }
    chunks
}

fn portal_main(
    args: &[String],
    skip: usize,
    exact_advances: bool,
    tick_model: bool,
    required: usize,
) -> Result<(), Box<dyn std::error::Error>> {
    if tick_model && exact_advances {
        return Err("Choose tick model or exact advances, not both".into());
    }
    if args.len() != 9 || args[1].trim().is_empty() {
        return Err("Portal mode requires seed, difficulty (1–3), X, Z, radius, maximum World.rand advances, view distance and output directory".into());
    }
    let seed = parse_seed(&args[1]);
    let difficulty: i32 = args[2].parse()?;
    let x: i32 = args[3].parse()?;
    let z: i32 = args[4].parse()?;
    let radius: i32 = args[5].parse()?;
    let advances: i32 = args[6].parse()?;
    let view: i32 = args[7].parse()?;
    if !(1..=3).contains(&difficulty)
        || !(0..=128).contains(&radius)
        || !(0..=1000).contains(&advances)
        || !(3..=32).contains(&view)
        || x.unsigned_abs() > 29_000_000
        || z.unsigned_abs() > 29_000_000
    {
        return Err("Invalid difficulty, coordinates, radius, advances or view distance".into());
    }
    let (rx, rz) = ((x + 128).div_euclid(1280), (z + 128).div_euclid(1280));
    let mut found = None;
    let mut remaining = skip;
    'search: for distance in 0..=radius {
        for dx in -distance..=distance {
            let dz = distance - dx.abs();
            'region: for signed_z in if dz == 0 { vec![0] } else { vec![-dz, dz] } {
                let (a, b) = (rx + dx, rz + signed_z);
                let position = if tick_model {
                    (a * 1280 - view * 16 - 24, 66, b * 1280 + 8)
                } else {
                    control_position(a, b, view)
                };
                if tick_model {
                    let order = portal_tick_order(position.0 + 16, position.2, view);
                    let rank = order
                        .iter()
                        .position(|&(cx, cz, _)| {
                            (cx, cz) == (position.0.div_euclid(16), position.2.div_euclid(16))
                        })
                        .ok_or("Portal chunk is outside the ticking area")?
                        + 1;
                    if let Some((attempt, roll)) =
                        portal_tick_candidate(seed, a, b, rank, difficulty, required)
                    {
                        if remaining > 0 {
                            remaining -= 1;
                            continue 'region;
                        }
                        found = Some((a, b, position, (rank + 4) as i32, attempt, roll));
                        break 'search;
                    }
                    continue 'region;
                }
                let mut rng = mansion_reset_rng(seed, a, b);
                if exact_advances {
                    for _ in 0..advances {
                        rng.next_int_unbounded();
                    }
                }
                let counts = if exact_advances {
                    advances..=advances
                } else {
                    0..=advances
                };
                for count in counts {
                    let mut target_rng = rng.clone();
                    if let Some((attempt, roll)) = portal_success(&mut target_rng, difficulty, required)
                    {
                        if remaining > 0 {
                            remaining -= 1;
                            continue 'region;
                        }
                        found = Some((a, b, position, count, attempt, roll));
                        break 'search;
                    }
                    rng.next_int_unbounded();
                }
            }
        }
    }
    let (a, b, pos, count, attempt, roll) =
        found.ok_or("No matching region for the requested successful random ticks within the chosen radius and advance limit")?;
    let (gx, gz) = if tick_model {
        (a * 1280 - 208, b * 1280)
    } else {
        (a * 1280 - 112, b * 1280 - 112)
    };
    let path = Path::new(&args[8]);
    if ["rng-combined.schematic", "rng-combined-plan.txt", "autosave-detector.schematic"].iter().any(|name| path.join(name).exists()) {
        return Err("Output files already exist; choose another directory".into());
    }
    std::fs::create_dir_all(path)?;
    let grid = path.join(if tick_model {
        "tile-tick-grid.schematic"
    } else {
        "xcom-original-grid.schematic"
    });
    let plan = path.join("rng-finder-plan.txt");
    let portal = path.join("portal-platform.schematic");
    let detector = path.join("autosave-detector.schematic");
    if grid.exists() || plan.exists() || portal.exists() || (tick_model && detector.exists()) {
        return Err("Output files already exist; choose another directory".into());
    }
    let grid_bytes: &[u8] = if tick_model {
        include_bytes!("../reference/command-tile-tick-grid-1.12.schematic")
    } else {
        include_bytes!("../reference/xcom-shared-detector-grid.schematic")
    };
    std::fs::write(&grid, grid_bytes)?;
    std::fs::write(&portal, portal_schematic(tick_model))?;
    if tick_model {
        std::fs::write(&detector, include_bytes!("../reference/command-autosave-detector-1.12.schematic"))?;
    }
    let portal_x = pos.0 - 9;
    let portal_z = pos.2 - 9;
    let (portal_x1, portal_x2) = (portal_x + 1, portal_x + 16);
    let (portal_z1, portal_z2) = (portal_z + 1, portal_z + 16);
    std::fs::write(&plan, format!("Minecraft Java 1.12.2 portal pigman RNG candidate (experimental)\nWorld seed: {seed}; difficulty: {difficulty}\nSearch center: {x}, {z}; radius: {radius} mansion regions; server view distance: {view}\nMansion region: {a}, {b}\nSuggested player position: {:.1}, {}, {:.1} (stand here; verify effective server view distance)\nMansion reset model: World.setRandomSeed(regionX, regionZ, 10387319), then four bounded nextInt(60) draws as in WoodlandMansion.canSpawnStructureAtCoords.\nModeled advances: {count} unbounded World.rand.nextInt() calls between those four bounded RNG draws and the target portal section\nConditional portal check: attempt {attempt} of 3, World.rand.nextInt(2000) = {roll} < difficulty {difficulty}\n\nPortal-array schematic: {}\nPlacement minimum corner (local 0,0,0): {portal_x}, 64, {portal_z}\nDimensions: 18 x 33 x 18; target portal section is one chunk wide and 16 blocks high\nPlatform: y=64; portal blocks: y=80..95; obsidian frame y=79,96\nPortal array: 16 adjacent valid 16 x 16 portal planes; interior blocks x={portal_x1}..{portal_x2}, y=80..95, z={portal_z1}..{portal_z2}. Each Z slice has a shared obsidian frame; ignite each slice separately. This avoids relying on sliced unsupported portal blocks. The MCP 1.12.2 BlockPortal.Size code accepts portal interiors up to 21 x 21.\n\nBUILD AND USE\n1. Use a disposable vanilla Java 1.12.2 world while validating. Place the standalone portal-array schematic at its reported minimum corner, or use the combined schematic's reported minimum corner. Place the original grid at its separate reported corner if using CLI component files. Air in schematic volumes overwrites existing blocks.\n2. Keep the 16 x 16 platform at the reported height and the entire 16 x 16 x 16 portal volume inside one ticking chunk section. Build/light one portal sheet at each Z coordinate; verify all 16 sheets remain intact after adjacent sheets are lit.\n3. Use the Overworld, the reported difficulty, doMobSpawning=true and randomTickSpeed=3. Keep the portal chunk ticking and use the reported player position and actual server view distance. The full portal volume means every updateLCG-selected position in this section is a portal block; updateLCG is not predicted by this tool.\n4. Treat the displayed roll as conditional on the mansion-region reseed being the last relevant World.rand reset, exactly {count} additional unbounded nextInt calls before the target portal section, and no unmodeled World.rand consumers. Confirm the chunk-generation order and intervening calls in your world. The grid's autosave timing and reset cycle are not validated by this tool.\n5. On a passing check, vanilla searches downward for a solid-top block. The bottom obsidian frame is the first such block, so the pigman spawns inside the portal immediately above that frame, not on the lower stone platform. Collection and portal transfer are not designed or verified. A successful earlier check consumes additional RNG for entity construction; this plan only reports the first success and makes no claim about later checks, mob movement, killing or item collection.\n\nGrid schematic: {}\nPlacement minimum corner (local 0,0,0): {gx}, 64, {gz}\nOrientation: unchanged\nAutosave detector approximate bounds: {}, 67, {} to {}, 71, {}\n\nInputs used: world creation seed, difficulty, search center and finite region radius, maximum modeled unbounded RNG advances, and server view distance. Output is a conditional candidate and build layout, not a guaranteed farm rate. A prepared first lever window has been reproduced in a disposable vanilla server; survival construction, modded-server compatibility and farm yield remain unverified. No commands or Carpet rules are required by the schematic.\n", (pos.0+16) as f64 + 0.5,pos.1,pos.2 as f64 + 0.5,portal.display(),grid.display(),gx+194,gz+9,gx+206,gz+17))?;
    if tick_model {
        let mut text = std::fs::read_to_string(&plan)?;
        text = text.replace(&format!("Placement minimum corner (local 0,0,0): {portal_x}, 64, {portal_z}"), &format!("Placement minimum corner (local 0,0,0): {portal_x}, 60, {portal_z}"));
        text = text.replace("Dimensions: 18 x 33 x 18", "Dimensions: 18 x 37 x 20");
        text = text.replace("obsidian frame y=79,96", "obsidian top frame y=96; bottom frame removed (sliced)");
        text = text.replace("Each Z slice has a shared obsidian frame; ignite each slice separately. This avoids relying on sliced unsupported portal blocks. The MCP 1.12.2 BlockPortal.Size code accepts portal interiors up to 21 x 21.",
            "The bottom obsidian is absent; a stepped packed-ice and water platform moves pigmen south through open fence gates into a contained dry receiving channel outside the portal chunk. This is a sliced final-state blueprint. Survival construction requires lighting with a temporary bottom frame and slicing without neighbor updates; ordinary frame removal breaks the portals.");
        text = text.replace("16 adjacent valid 16 x 16 portal planes", "16 adjacent sliced 16 x 16 portal planes");
        text = text.replace("Build/light one portal sheet at each Z coordinate; verify all 16 sheets remain intact after adjacent sheets are lit.",
            "Preserve all 4096 pre-lit portal blocks when importing. Avoid neighbor updates to sliced portals; this schematic does not contain an update suppressor for survival construction.");
        text = text.replace("The bottom obsidian frame is the first such block, so the pigman spawns inside the portal immediately above that frame, not on the lower stone platform.",
            "With the bottom obsidian removed, the packed-ice floors are the first solid surfaces; pigmen spawn at platform Y + 1.1 inside the water stream.");
        text = text.replace(
            &format!("Autosave detector approximate bounds: {}, 67, {} to {}, 71, {}", gx+194, gz+9, gx+206, gz+17),
            &format!("Grid type: scheduled repeater (Command 1.7 reference, adapted for 1.12)\nTile-grid input repeater: {}, 65, {} (pulse toward +Z into the shared two-line control; desktop export supplies the complete route)\nGrid dimensions: 720 x 7 x 512. Its 32 x 32 active lattice is a subset of the selected 80 x 80 mansion region, not a 1.7 reset region.\nAutosave detector schematic: {}\nPlacement minimum corner (local 0,0,0): {}, 63, {}\nThe desktop combined export connects this detector, its enable input, five-chunk priming line, and automatic grid pulses to one AFK lever. Leave the lever on. Natural vanilla autosaves occur every 900 server ticks; allow the first autosave for synchronization. Stand still with server view distance unchanged.\nGrid and route supports are blue terracotta; the old button/delay branch, accidentally captured trees/plants and debug command blocks are absent. Two upside-down slab crossings isolate the enable signal from the pulse lines.", gx+202, gz+20, detector.display(), (pos.0+16).div_euclid(16)*16, (pos.2.div_euclid(16)-view+1)*16-6));
        text = text.replace(
            &format!("Modeled advances: {count} unbounded World.rand.nextInt() calls between those four bounded RNG draws and the target portal section"),
            &format!("Scheduled-reset tick model: playerCheckLight nextInt(1), three nextInt(11), then {} nextInt(16) calls through the portal chunk. These are bounded calls, not arbitrary extra advances or an LCG-step count.", count - 4));
        text = text.replace(
            &format!("exactly {count} additional unbounded nextInt calls before the target portal section"),
            "the modeled player-light and chunk ice/snow calls before the target portal section");
        text = text.replace(
            "maximum modeled unbounded RNG advances, and server view distance",
            "server view distance and the generated portal chunk's tick rank; the advance-limit input is unused in tick-model mode");
        text = text.replace("A prepared first lever window has been reproduced in a disposable vanilla server;", "Two prepared vanilla Survival-player AFK trials of the connected export produced 2143 and 2141 new pigmen in about 161 seconds each, from one lever click with automatic restarts; this is not gold yield or an unlimited-duration guarantee;");
        text.push_str(&format!("\nWater transport: north packed-ice floor y=64; middle packed-ice floor y=63; south packed-ice floor y=62; dry receiving floor y=60. Water source row at z={portal_z1}, flowing toward +Z; receiving rows z={}..{}, outside the portal chunk. Blue terracotta walls contain the water; open fence gates at the outlet hold it back while pigmen drop into the dry receiving channel. Keep those gates open. Keep the stream and headroom clear; the receiving basin has no killing or item-collection system. When replacing the old flat floor, clear its last row at y=64, x={portal_x1}..{portal_x2}, z={} before a non-air paste; the new lower stream needs this headroom.\n", portal_z + 17, portal_z + 18, portal_z + 16));
        text = text.replace("The grid's autosave timing and reset cycle are not validated by this tool.", "The combined export supplies the detector-driven cycle; its environmental conditions must still match the test record.");
        std::fs::write(&plan, text)?;
    }
    let mut text = std::fs::read_to_string(&plan)?;
    text = format!("Requested manipulation: at least {required}/3 successful portal random ticks per aligned game tick.\nThe reported conditional portal check is the requested success number {required}; intervening successful spawns include yaw and baby/jockey World.rand calls. This is not a guaranteed farm-rate multiplier.\n\n{text}");
    if required > 1 {
        text = text.replace("this plan only reports the first success and makes no claim about later checks, mob movement, killing or item collection.", "this search follows the spawn RNG calls through the requested success. It assumes every passing check can spawn; blocked floors or modded spawn hooks invalidate this sequence. Mob movement, killing and collection remain unmodeled.");
    }
    std::fs::write(&plan, text)?;
    let order = portal_tick_order(pos.0 + 16, pos.2, view);
    let mut file = std::fs::OpenOptions::new().append(true).open(&plan)?;
    writeln!(file, "\nCONDITIONAL 1.12.2 CHUNK TICK ORDER\nFresh single non-spectator player list, all chunks initialized; player X/Z use the reported block centers (+0.5). X-major/Z-minor insertion order, chunk-center distance strictly <128 blocks. Old PigmanRNG Chunk Hash Order is for 1.8. Movement, other players, missing/uninitialized chunks and list history invalidate this fresh-list prediction. Tick rank is not an RNG advance count. See research/pigman-rng.md, RandomFT archive correction (2026-11-11).")?;
    if tick_model {
        writeln!(file, "\nTICK MODEL BUILD CONDITIONS\nUse the reported player position. Establish the fresh single-player list by joining at this position after all other players have left; remain in the same position and keep view distance unchanged. Initialize the full view square first, then rejoin without moving.\nThe LAST mansion reset must occur in tickPending (scheduled repeater/block updates), after natural spawning and before updateBlocks/playerCheckLight. Player walking, login loading or a chest update is not this reset phase. Later chunk loads or scheduled RNG consumers invalidate the prediction. Verify the grid's actual last loaded chunk/reset region and pulse phase.\nKeep clear weather. Remove or replace RNG-consuming random-tick blocks in every preceding ticking chunk (all heights), and below the portal section in the target chunk. Grass, lava, crops, leaves and other portals can shift World.rand. The terrain collision scan does not check RNG-consumer clearance. Prevent freezing/block-update side effects too. Initialize lighting/chunks before the reset; no intervening generation or reseeds. Keep doMobSpawning=true and randomTickSpeed=3. The full portal section avoids needing the separate updateLCG state. Detector-driven repeated cycles are reproduced in prepared vanilla 1.12.2 worlds at server view distance 10. Other view distances, survival construction and RNG cleanup in normal terrain remain unverified. See research/experiments/pigman-afk-export/README.md.")?;
    }
    for (index, &(cx, cz, list_index)) in order.iter().enumerate() {
        let target = if (cx, cz) == (pos.0.div_euclid(16), pos.2.div_euclid(16)) {
            " PORTAL"
        } else {
            ""
        };
        writeln!(
            file,
            "Tick #{}; list index {list_index}; chunk ({cx}, {cz}){target}",
            index + 1
        )?;
    }
    drop(file);
    if !tick_model {
        warn_control_boundary(&plan, a, b, view)?;
    }
    finish_detector_export(path)?;
    println!("Saved {} and {}", grid.display(), plan.display());
    Ok(())
}

// Blueprint of the intended final block states; the adjacent frames can be lit individually.
fn portal_schematic(sliced: bool) -> Vec<u8> {
    const W: usize = 18;
    let d = if sliced { 20 } else { 18 };
    let h = if sliced { 37 } else { 33 };
    let offset = if sliced { 4 } else { 0 };
    let mut blocks = vec![0; W * d * h];
    let mut data = vec![0; W * d * h];
    let mut put = |x: usize, y: usize, z: usize, block, meta| {
        let i = (y * d + z) * W + x;
        blocks[i] = block;
        data[i] = meta;
    };
    for z in 1..=16 {
        for x in 1..=16 {
            if !sliced { put(x, 0, z, 1, 0); }
            for y in 16..=31 {
                put(x, y + offset, z, 90, 1);
            }
        }
        for x in 0..W {
            if !sliced {
                put(x, 15, z, 49, 0);
            }
            put(x, 32 + offset, z, 49, 0);
        }
        for y in 16..=31 {
            put(0, y + offset, z, 49, 0);
            put(17, y + offset, z, 49, 0);
        }
    }
    if sliced {
        // Each seven-block floor run ends in a reachable eighth-cell drop; the final basin is outside the portal chunk.
        for z in 1..=18 {
            let floor = if z <= 7 { 4 } else if z <= 14 { 3 } else if z <= 16 { 2 } else { 0 };
            let level = if z == 1 { 0 } else if z == 8 || z == 15 { 8 } else if z <= 7 { z - 1 } else if z <= 14 { z - 8 } else { z - 15 };
            for x in 1..=16 {
                put(x, floor, z, 174, 0);
                if z <= 16 { put(x, floor + 1, z, 8, level as u8); }
                if z == 17 { put(x, 3, z, 107, 4); } // Open south-facing gates stop water but pass pigmen into the dry drop.
                if z == 8 || z == 15 { put(x, floor + 2, z, 8, 7); }
            }
        }
        for z in 0..20 {
            for y in 1..=if z == 0 { 5 } else { 6 } {
                put(0, y, z, 159, 11);
                put(17, y, z, 159, 11);
            }
        }
        for x in 1..=16 {
            for y in 1..=5 { put(x, y, 0, 159, 11); } // Existing detector route runs above this wall.
            for y in 1..=6 { put(x, y, 19, 159, 11); }
        }
    }
    make_schematic(W, h, d, blocks, data, &[])
}

fn golem_player_chunks(view: i32) -> i32 {
    let mut count = 0;
    for x in -view..=view {
        for z in -view..=view {
            let dx = x as f64 * 16.0 - 0.5;
            let dz = z as f64 * 16.0 - 0.5;
            if dx * dx + dz * dz < 128.0 * 128.0 {
                count += 1;
            }
        }
    }
    count
}

fn village_golem_limit(villagers: i32) -> i32 {
    villagers / 10
}

fn golem_candidate(seed: i64, rx: i32, rz: i32, chunks: i32) -> Option<(i32, i32, i32)> {
    let mut rng = mansion_reset_rng(seed, rx, rz);
    // Vanilla playerCheckLight makes one player selection and three coordinate draws.
    rng.next_int(1);
    for _ in 0..3 {
        rng.next_int(11);
    }
    for _ in 0..chunks {
        rng.next_int(16);
    }
    rng.next_int(50); // Village.removeDeadAndOutOfRangeDoors
    if rng.next_int(7000) != 0 {
        return None;
    }
    Some((
        rng.next_int(16) - 8,
        rng.next_int(6) - 3,
        rng.next_int(16) - 8,
    ))
}

// Schematic coordinates are relative to the intended village center.
fn village_schematic(offset: (i32, i32, i32)) -> Option<(Vec<u8>, [usize; 5])> {
    const W: usize = 23;
    const H: usize = 13;
    const D: usize = 29;
    const MIN_X: i32 = -11;
    const MIN_Z: i32 = -14;
    let mut blocks = vec![0_u8; W * H * D];
    let mut data = vec![0_u8; W * H * D];
    let mut set = |x: i32, y: i32, z: i32, id: u8, meta: u8| {
        let i = ((y + 4) as usize * D + (z - MIN_Z) as usize) * W + (x - MIN_X) as usize;
        blocks[i] = id;
        data[i] = meta;
    };
    for x in -9..=9 {
        for z in -6..=6 {
            set(x, 8, z, 1, 0);
        }
    }
    for x in [-10, 10] {
        for z in -6..=6 {
            if z != 0 {
                set(x, -1, z, 1, 0);
                set(x, 0, z, 64, 0);
                set(x, 1, z, 64, 8);
            }
        }
    }
    drop(set);
    // Portal is two blocks wide and four high; its frame cannot obstruct spawn clearance.
    let (sx, sy, sz) = offset;
    if sx - 2 < MIN_X || sx + 1 > 10 || sz - 1 < MIN_Z || sz + 1 > 14 {
        return None;
    }
    let mut portal = Vec::new();
    for x in sx - 2..=sx + 1 {
        for y in sy - 1..=sy + 4 {
            let frame = x == sx - 2 || x == sx + 1 || y == sy - 1 || y == sy + 4;
            portal.push((
                x,
                y,
                sz,
                if frame { 49 } else { 90 },
                if frame { 0 } else { 1 },
            ));
        }
    }
    for &(x, y, z, _, _) in &portal {
        let i = ((y + 4) as usize * D + (z - MIN_Z) as usize) * W + (x - MIN_X) as usize;
        if blocks[i] != 0 {
            return None;
        }
    }
    for (x, y, z, id, meta) in portal {
        let i = ((y + 4) as usize * D + (z - MIN_Z) as usize) * W + (x - MIN_X) as usize;
        blocks[i] = id;
        data[i] = meta;
    }
    let mut slots = Vec::new();
    for x in (-9..=9).step_by(2) {
        for z in (-13..=13).step_by(2) {
            // Reserve the portal frame, portal blocks and complete golem spawn prism.
            if x + 1 >= sx - 2 && x - 1 <= sx + 1 && z + 1 >= sz - 1 && z - 1 <= sz + 1 {
                continue;
            }
            let mut clear = true;
            for base_y in [-3, 0, 3] {
                for y in base_y..=base_y + 1 {
                    for dx in -1..=1 {
                        for dz in -1..=1 {
                            if blocks[((y + 4) as usize * D + (z + dz - MIN_Z) as usize) * W
                                + (x + dx - MIN_X) as usize]
                                != 0
                            {
                                clear = false;
                            }
                        }
                    }
                }
                let floor = ((base_y - 1 + 4) as usize * D + (z - MIN_Z) as usize) * W
                    + (x - MIN_X) as usize;
                if blocks[floor] != 0 {
                    clear = false;
                }
                if base_y == 3 {
                    let roof = ((base_y + 2 + 4) as usize * D + (z - MIN_Z) as usize) * W
                        + (x - MIN_X) as usize;
                    if blocks[roof] != 0 {
                        clear = false;
                    }
                }
            }
            if clear {
                slots.push((x, z));
            }
        }
    }
    if slots.len() < 100 {
        return None;
    }
    slots.sort_by_key(|&(x, z)| (x * x + z * z, x, z));
    let mut set = |x: i32, y: i32, z: i32, id: u8, meta: u8| {
        let i = ((y + 4) as usize * D + (z - MIN_Z) as usize) * W + (x - MIN_X) as usize;
        blocks[i] = id;
        data[i] = meta;
    };
    let mut villagers = Vec::with_capacity(300);
    for base_y in [-3, 0, 3] {
        for &(x, z) in slots.iter().take(100) {
            set(x, base_y - 1, z, 1, 0);
            for y in base_y..=base_y + 1 {
                for dx in -1..=1 {
                    for dz in -1..=1 {
                        if dx != 0 || dz != 0 {
                            set(x + dx, y, z + dz, 20, 0);
                        }
                    }
                }
            }
            if base_y == 3 {
                set(x, base_y + 2, z, 20, 0);
            }
            villagers.push((
                (x - MIN_X) as f64 + 0.5,
                (base_y + 4) as f64,
                (z - MIN_Z) as f64 + 0.5,
            ));
        }
    }
    let counts =
        [1_u8, 20, 64, 49, 90].map(|id| blocks.iter().filter(|&&block| block == id).count());
    Some((make_schematic(W, H, D, blocks, data, &villagers), counts))
}

fn make_schematic(
    w: usize,
    h: usize,
    d: usize,
    blocks: Vec<u8>,
    data: Vec<u8>,
    villagers: &[(f64, f64, f64)],
) -> Vec<u8> {
    fn header(out: &mut Vec<u8>, kind: u8, name: &str) {
        out.push(kind);
        out.extend_from_slice(&(name.len() as u16).to_be_bytes());
        out.extend_from_slice(name.as_bytes());
    }
    let mut nbt = vec![10, 0, 9];
    nbt.extend_from_slice(b"Schematic");
    for (name, n) in [("Width", w), ("Height", h), ("Length", d)] {
        header(&mut nbt, 2, name);
        nbt.extend_from_slice(&(n as i16).to_be_bytes());
    }
    header(&mut nbt, 8, "Materials");
    nbt.extend_from_slice(&5_u16.to_be_bytes());
    nbt.extend_from_slice(b"Alpha");
    for (name, bytes) in [("Blocks", blocks), ("Data", data)] {
        header(&mut nbt, 7, name);
        nbt.extend_from_slice(&(bytes.len() as i32).to_be_bytes());
        nbt.extend_from_slice(&bytes);
    }
    header(&mut nbt, 9, "Entities");
    nbt.push(10);
    nbt.extend_from_slice(&(villagers.len() as i32).to_be_bytes());
    for &(x, y, z) in villagers {
        header(&mut nbt, 8, "id");
        let id = b"minecraft:villager";
        nbt.extend_from_slice(&(id.len() as u16).to_be_bytes());
        nbt.extend_from_slice(id);
        for (name, values) in [("Pos", [x, y, z]), ("Motion", [0.0, 0.0, 0.0])] {
            header(&mut nbt, 9, name);
            nbt.push(6);
            nbt.extend_from_slice(&3_i32.to_be_bytes());
            for value in values {
                nbt.extend_from_slice(&value.to_be_bytes());
            }
        }
        header(&mut nbt, 9, "Rotation");
        nbt.push(5);
        nbt.extend_from_slice(&2_i32.to_be_bytes());
        for _ in 0..2 {
            nbt.extend_from_slice(&0_f32.to_be_bytes());
        }
        for name in ["Age", "Profession"] {
            header(&mut nbt, 3, name);
            nbt.extend_from_slice(&0_i32.to_be_bytes());
        }
        header(&mut nbt, 5, "Health");
        nbt.extend_from_slice(&20_f32.to_be_bytes());
        header(&mut nbt, 1, "PersistenceRequired");
        nbt.push(1);
        nbt.push(0);
    }
    header(&mut nbt, 9, "TileEntities");
    nbt.push(10);
    nbt.extend_from_slice(&0_i32.to_be_bytes());
    nbt.push(0);
    // Emit multiple stored DEFLATE blocks when entity NBT exceeds 65535 bytes.
    let mut crc = !0_u32;
    for &byte in &nbt {
        crc ^= byte as u32;
        for _ in 0..8 {
            crc = (crc >> 1) ^ (0xedb88320 & 0_u32.wrapping_sub(crc & 1));
        }
    }
    let mut out = vec![0x1f, 0x8b, 8, 0, 0, 0, 0, 0, 0, 255];
    let chunks = nbt.chunks(65535);
    let count = chunks.len();
    for (i, chunk) in chunks.enumerate() {
        out.push(if i + 1 == count { 1 } else { 0 });
        let len = chunk.len() as u16;
        out.extend_from_slice(&len.to_le_bytes());
        out.extend_from_slice(&(!len).to_le_bytes());
        out.extend_from_slice(chunk);
    }
    out.extend_from_slice(&(!crc).to_le_bytes());
    out.extend_from_slice(&(nbt.len() as u32).to_le_bytes());
    out
}

fn golem_main(args: &[String], skip: usize) -> Result<(), Box<dyn std::error::Error>> {
    if args.len() != 7 {
        return Err(
            "Golem mode requires seed, X, Z, radius, view distance and output directory".into(),
        );
    }
    if args[1].trim().is_empty() {
        return Err("Enter a world seed".into());
    }
    let seed = parse_seed(&args[1]);
    let x: i32 = args[2].parse()?;
    let z: i32 = args[3].parse()?;
    let radius: i32 = args[4].parse()?;
    let view: i32 = args[5].parse()?;
    if !(0..=128).contains(&radius)
        || !(3..=32).contains(&view)
        || x.unsigned_abs() > 29_000_000
        || z.unsigned_abs() > 29_000_000
    {
        return Err("Radius must be 0..128; view distance 3..32; coordinates must be within 29,000,000 blocks".into());
    }
    let rx = (x + 128).div_euclid(1280);
    let rz = (z + 128).div_euclid(1280);
    let chunks = golem_player_chunks(view);
    let mut found = None;
    let mut remaining = skip;
    'search: for distance in 0..=radius {
        for dx in -distance..=distance {
            let dz = distance - dx.abs();
            'region: for signed_z in if dz == 0 { vec![0] } else { vec![-dz, dz] } {
                let (region_x, region_z) = (rx + dx, rz + signed_z);
                let player = control_position(region_x, region_z, view);
                if let Some(offset) = golem_candidate(seed, region_x, region_z, chunks) {
                    // Keep the 2x2 spawn footprint clear of the villager enclosure.
                    if offset.0 - 1 <= 2 && offset.0 >= -2 && offset.2 - 1 <= 2 && offset.2 >= -2 {
                        continue;
                    }
                    if village_schematic(offset).is_none() {
                        continue;
                    }
                    if remaining > 0 {
                        remaining -= 1;
                        continue 'region;
                    }
                    found = Some((region_x, region_z, player, offset));
                    break 'search;
                }
            }
        }
    }
    let (region_x, region_z, player, offset) =
        found.ok_or("No golem candidate in this search radius under the zero-advance model")?;
    let center = (player.0 + 32, 64, player.2);
    let spawn = (
        center.0 + offset.0,
        center.1 + offset.1,
        center.2 + offset.2,
    );
    // Entity.changeDimension scales Overworld portal coordinates by 1/8 before Nether lookup.
    let nether_target = ((spawn.0 as f64 / 8.0) as i32, (spawn.2 as f64 / 8.0) as i32);
    let grid_x = region_x * 1280 - 112;
    let grid_z = region_z * 1280 - 112;
    let path = Path::new(&args[6]);
    if ["rng-combined.schematic", "rng-combined-plan.txt", "autosave-detector.schematic"].iter().any(|name| path.join(name).exists()) {
        return Err("Output files already exist; choose another directory".into());
    }
    std::fs::create_dir_all(path)?;
    let grid = path.join("xcom-original-grid.schematic");
    let village = path.join("golem-village.schematic");
    let plan = path.join("rng-finder-plan.txt");
    if grid.exists() || village.exists() || plan.exists() {
        return Err("Output files already exist; choose another directory".into());
    }
    std::fs::write(
        &grid,
        include_bytes!("../reference/xcom-shared-detector-grid.schematic"),
    )?;
    let (village_bytes, material_counts) =
        village_schematic(offset).ok_or("Portal or villager housing conflicts with the village")?;
    std::fs::write(&village, village_bytes)?;
    let village_path = village.display();
    let village_x = center.0 - 11;
    let village_z = center.2 - 14;
    std::fs::write(&plan, format!("Minecraft Java 1.12.2 iron-golem candidate (experimental)\nWorld seed: {seed}\nSearch center: {x}, {z}; radius: {radius} regions\nServer view distance: {view}; modeled ticking chunks: {chunks}\nMansion region: {region_x}, {region_z}\nSuggested village center: {}, {}, {} (must be the actual registered center)\nPlayer position: {:.1}, {}, {:.1} (one non-spectator player; remain at this chunk position)\nModeled first spawn offset from village center: {}, {}, {}\nModeled first golem spawn block: {}, {}, {} (verify village radius and clearance)\nSuggested Nether portal search center: {}, {} (spawn X/Z scaled by 1/8 and truncated as in 1.12.2 Entity.changeDimension; build/verify a receiving portal nearby)\n\nVillage schematic: {village_path}\nVillage schematic minimum corner: {village_x}, 60, {village_z}\nVillage schematic dimensions: 23 x 13 x 29 blocks; orientation unchanged\nVillager design: 300 living adults, 100 single-occupant glass cells on each of three levels at center Y offsets -3, 0, +3. All cells are within the village count AABB and the modeled spawn/portal volume is reserved.\nRequired villager count: 300 counted villagers for capacity for 30 successful spawns between 30-tick golem-count refreshes (one success per tick target). `Village.tick` uses floor(villagers / 10): 30 villagers allow {}, 300 allow {}, 301-309 still allow {}, and 310 allow {}. Villagers are recounted every 20 ticks; keep all 300 alive and in the village AABB.\nVillage schematic material counts: stone={}, glass={}, wooden door blocks={} (24 doorways), obsidian={}, portal={}; villager entities=300.\nUse an importer that preserves schematic entities. WorldEdit 6.1 drops them; the desktop combined plan includes 300 `/summon` commands if needed, or bring 300 adults into the enclosed cells. Do not summon twice. The portal is a final-state blueprint: build/light the obsidian frame, then verify golems enter it and transfer to the receiving portal near the suggested Nether coordinates. Nether killing and collection are not included.\n\nGrid schematic: {}\nPlacement minimum corner (local 0,0,0): {grid_x}, 64, {grid_z}\nOrientation: unchanged\nAutosave detector approximate bounds: {}, 67, {} to {}, 71, {}\n\nBuild/conditions: vanilla Java 1.12.2; effective server view distance; Overworld; stable player position and no other players in that dimension; clear weather; doMobSpawning=false; randomTickSpeed=0; one village record in the Overworld VillageCollection; at least 21 valid registered wooden doors (24 are supplied); at least 300 live villagers inside the village AABB; and fewer cached golems than floor(villagers/10). Keep the 2x4x2 spawn volume clear of normal cubes, with a top-solid support below; the portal blocks are non-normal cubes. Verify door sky exposure, actual village center, terrain, and all 300 counts. Ensure no other village records are present; these tick even when distant. Keep all modeled chunks fully initialized.\nThe model follows the mansion-region reset, player-light draws, one nextInt(16) per modeled chunk, one village door-check draw, a passing nextInt(7000), then only the first spawn-position triple. Weather, other village ticks, chunk history, actual village state and failed spawn attempts can shift the stream. The stated gamerules suppress natural-mob and random-block RNG consumers; Village.tick still performs iron golem checks. A blocked first candidate can trigger up to nine more triples, which this candidate does not model. The terrain scan is base generation only. Neither the autosave reset cycle, portal transfer, spawn, nor the design's rate has been reproduced in vanilla gameplay. Test in a disposable 1.12.2 world.\n",center.0,center.1,center.2,player.0 as f64 + 0.5,player.1,player.2 as f64 + 0.5,offset.0,offset.1,offset.2,spawn.0,spawn.1,spawn.2,nether_target.0,nether_target.1,village_golem_limit(30),village_golem_limit(300),village_golem_limit(301),village_golem_limit(310),material_counts[0],material_counts[1],material_counts[2],material_counts[3],material_counts[4],grid.display(),grid_x+194,grid_z+9,grid_x+206,grid_z+17))?;
    warn_control_boundary(&plan, region_x, region_z, view)?;
    finish_detector_export(path)?;
    println!(
        "Saved {}, {} and {}",
        grid.display(),
        village.display(),
        plan.display()
    );
    Ok(())
}

// Keep CLI and desktop detector wiring in the existing Python/NBT implementation.
fn finish_detector_export(path: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let executable = std::env::current_exe()?;
    let tool = executable.ancestors().find(|p| p.join("export_shared_detector.py").is_file())
        .ok_or("Keep the finder binary inside its tool directory; shared detector export requires export_shared_detector.py")?;
    let output = std::process::Command::new(if cfg!(windows) { "python" } else { "python3" })
        .arg(tool.join("export_shared_detector.py")).arg(path).output()?;
    if !output.status.success() {
        return Err(format!("Shared detector export failed: {}", String::from_utf8_lossy(&output.stderr)).into());
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut arguments: Vec<String> = std::env::args().skip(1).collect();
    let portal_requested = arguments.iter().any(|arg| arg == "--portal");
    let required = if let Some(i) = arguments.iter().position(|arg| arg == "--portal-successes") {
        if !portal_requested { return Err("--portal-successes is only valid in portal mode".into()); }
        arguments.remove(i);
        let value: usize = arguments.get(i).ok_or("Missing --portal-successes value")?.parse()?;
        arguments.remove(i);
        if !(1..=3).contains(&value) { return Err("Portal successes must be 1, 2 or 3".into()); }
        value
    } else { 1 };
    let auto_height = if let Some(i) = arguments.iter().position(|arg| arg == "--auto-height") {
        arguments.remove(i);
        true
    } else {
        false
    };
    let exact_advances = if let Some(i) = arguments.iter().position(|arg| arg == "--exact-advances")
    {
        arguments.remove(i);
        true
    } else {
        false
    };
    let tick_model = if let Some(i) = arguments
        .iter()
        .position(|arg| arg == "--portal-tick-model")
    {
        arguments.remove(i);
        true
    } else {
        false
    };
    let skip = if let Some(i) = arguments.iter().position(|arg| arg == "--skip-candidates") {
        if i + 1 >= arguments.len() {
            return Err("Missing candidate skip count".into());
        }
        let value: usize = arguments[i + 1].parse()?;
        arguments.drain(i..=i + 1);
        value
    } else {
        0
    };
    if arguments.first().is_some_and(|arg| arg == "--fortune") {
        return fortune_main(&arguments, skip);
    }
    if arguments.first().is_some_and(|arg| arg == "--golem") {
        return golem_main(&arguments, skip);
    }
    if arguments.first().is_some_and(|arg| arg == "--portal") {
        return portal_main(&arguments, skip, exact_advances, tick_model, required);
    }
    let mut view = 10;
    let mut min_players = 1;
    let mut max_players = 1;
    let mut args = arguments.into_iter();
    while let Some(flag) = args.next() {
        let value: i32 = args.next().ok_or("Missing option value")?.parse()?;
        match flag.as_str() {
            "--view-distance" => view = value,
            "--players-min" => min_players = value,
            "--players-max" => max_players = value,
            _ => return Err(format!("Unknown option: {flag}").into()),
        }
    }
    if !(3..=32).contains(&view)
        || !(1..=100).contains(&min_players)
        || !(min_players..=100).contains(&max_players)
    {
        return Err("View distance must be 3..32 and player range must be within 1..100".into());
    }
    println!("Minecraft Java 1.12.2 world-RNG research finder (experimental)");
    let seed_text = prompt("World creation seed (number or text): ", None)?;
    if seed_text.is_empty() {
        return Err("A world seed is required".into());
    }
    println!("Mob type: 1. Witch, 2. Creeper, 3. Skeleton, 4. Zombie, 5. Spider, 6. Enderman");
    let choice = prompt("Choose [1]: ", Some("1"))?;
    let mob = match choice.to_ascii_lowercase().as_str() {
        "1" | "witch" => Mob::Witch,
        "2" | "creeper" => Mob::Creeper,
        "3" | "skeleton" => Mob::Skeleton,
        "4" | "zombie" => Mob::Zombie,
        "5" | "spider" => Mob::Spider,
        "6" | "enderman" => Mob::Enderman,
        _ => return Err("Choose an available mob type".into()),
    };
    let x = number("Search near block X [0]: ", "0")?;
    let z = number("Search near block Z [0]: ", "0")?;
    let radius = number("Search radius in 80-chunk regions [25]: ", "25")?;
    let bound = number("Assumed random Y bound (multiple of 16) [64]: ", "64")?;
    if !(0..=128).contains(&radius) || !(16..=256).contains(&bound) || bound % 16 != 0 {
        return Err("Radius must be 0..128; Y bound must be a multiple of 16 in 16..256".into());
    }
    if x.unsigned_abs() > 29_000_000 || z.unsigned_abs() > 29_000_000 {
        return Err("Search center is too close to the world border".into());
    }
    let seed = parse_seed(&seed_text);
    let rx = (x + 128).div_euclid(1280);
    let rz = (z + 128).div_euclid(1280);
    let mut found = None;
    let mut remaining = skip;
    'search: for distance in 0..=radius {
        for dx in -distance..=distance {
            let dz = distance - dx.abs();
            for signed_z in if dz == 0 { vec![0] } else { vec![-dz, dz] } {
                for ox in [-456] {
                    for oz in [-616 + (1 - view) * 16] {
                        let bounds: Vec<i32> = if auto_height {
                            (bound..=256).step_by(16).collect()
                        } else {
                            vec![bound]
                        };
                        let mut candidates: Vec<_> = bounds
                            .into_iter()
                            .filter_map(|b| {
                                candidate(seed, rx + dx, rz + signed_z, b, mob, (ox, oz), view)
                            })
                            .collect();
                        candidates.sort_by_key(|c| std::cmp::Reverse(c.initial.1));
                        for c in candidates {
                            // Leave margin for sub-block player movement and avoid immediate distance despawn.
                            if c.attempts.iter().all(|&(x, y, z)| {
                                let dx = x as i64 - c.player.0 as i64;
                                let dy = y as i64 - c.player.1 as i64;
                                let dz = z as i64 - c.player.2 as i64;
                                dx * dx + dy * dy + dz * dz < 120 * 120
                            }) {
                                if remaining > 0 {
                                    remaining -= 1;
                                    continue;
                                }
                                found = Some(c);
                                break 'search;
                            }
                        }
                    }
                }
            }
        }
    }
    let c = found.ok_or(
        "No candidate found in this finite search; expand the radius or change the assumed Y bound",
    )?;
    let bound = c.y_bound;
    println!(
        "\nCandidate: closest matching region by Manhattan region distance in searched bounds"
    );
    println!(
        "World seed: {seed}; mansion region: {}, {}",
        c.region_x, c.region_z
    );
    println!("Server view distance: {view} chunks; player range: {min_players}..{max_players}.");
    println!("All participating non-spectator players must stand at the same reported position, with no other players in the dimension.");
    println!(
        "Region block bounds: ({}, {}) to ({}, {})",
        c.region_x * 1280 - 128,
        c.region_z * 1280 - 128,
        c.region_x * 1280 + 1151,
        c.region_z * 1280 + 1151
    );
    println!(
        "Example player position: {}, {}, {} (chunk {}, {})",
        c.player.0,
        c.player.1,
        c.player.2,
        c.player.0.div_euclid(16),
        c.player.2.div_euclid(16)
    );
    println!(
        "First eligible chunk: {}, {}",
        c.first_chunk.0, c.first_chunk.1
    );
    println!(
        "Initial random block: {}, {}, {}",
        c.initial.0, c.initial.1, c.initial.2
    );
    println!(
        "Modeled {} spawn-attempt positions (not checked for valid blocks; floor is y-1):",
        mob.name()
    );
    for (i, (x, y, z)) in c.attempts.iter().enumerate() {
        println!("  {}: {x}, {y}, {z}", i + 1);
    }
    println!("Attempts 2–4 assume each earlier attempt consumed the expected RNG calls; blocked attempts change the result.");
    let diameter = 2 * view.min(7) + 1;
    println!("Model: stacked players; complete sent {diameter}x{diameter} chunk set; freshly sized Java 8 HashSet; normal-biome hostile list; y bound {bound}; no RNG calls between mansion reset and spawn. Verify terrain, mob cap and call order.");
    println!("One shared set of modeled spawn attempts; no kill-zone design is generated. More stacked players can change the mob cap.");
    println!("Modeled hostile spawning threshold: {} at {min_players} player(s), {} at {max_players} player(s), assuming the complete sent-chunk square and no world-border restrictions. Actual counts and kill capacity are not modeled.", hostile_threshold(view, min_players), hostile_threshold(view, max_players));
    println!("This is a candidate, not a verified farm; verify loading order, biome, timing and the existing world.");
    let grid_x = c.region_x * 1280 - 112;
    let grid_z = c.region_z * 1280 - 112;
    let grid_y = 64.max(c.player.1 - 7);
    println!("Source-grid placement candidate (UNTESTED): {grid_x}, {grid_y}, {grid_z}; orientation unchanged.");
    println!("Use these as the schematic's local minimum-corner coordinates (x,z increase across its footprint)." );
    println!("The derived grid removes its obsolete detector. The connected export includes the Command sand detector, enable/priming routes and one AFK lever; use its combined placement plan. Reset timing remains conditional on the mode's recorded requirements.");
    let dest = prompt(
        "Export the connected grid and this candidate plan? Directory [rng-output]: ",
        Some("rng-output"),
    )?;
    let path = Path::new(&dest);
    if ["rng-combined.schematic", "rng-combined-plan.txt", "autosave-detector.schematic"].iter().any(|name| path.join(name).exists()) {
        return Err("Output files already exist; choose another directory".into());
    }
    std::fs::create_dir_all(path)?;
    let grid = path.join("xcom-original-grid.schematic");
    let plan = path.join("rng-finder-plan.txt");
    if grid.exists() || plan.exists() {
        return Err("Output files already exist; choose another directory".into());
    }
    std::fs::write(
        &grid,
        include_bytes!("../reference/xcom-shared-detector-grid.schematic"),
    )?;
    let attempts = c
        .attempts
        .iter()
        .enumerate()
        .map(|(i, (x, y, z))| format!("{}. {}, {}, {}", i + 1, x, y, z))
        .collect::<Vec<_>>()
        .join("\n");
    std::fs::write(&plan, format!(
        "Minecraft Java 1.12.2 world-RNG candidate (experimental)\nWorld seed: {seed}\nTarget: {}\nMansion region: {}, {}\nSearch center: {}, {}; radius: {} regions\nServer view distance: {view} chunks\nPlayer range: {min_players}..{max_players} (all non-spectators at the exact player position; no other players in this dimension)\nModeled hostile spawning threshold: {} at {min_players} player(s), {} at {max_players} player(s), assuming a complete sent-chunk square and no world-border restrictions. This is a spawning threshold, not a guaranteed maximum mob count.\nAssumed Y bound: {bound}\nPlayer position: {}, {}, {}\nFirst eligible chunk: {}, {}\nInitial random block: {}, {}, {}\nModeled spawn-attempt positions (not terrain-checked; floor blocks would be at y-1):\n{}\n\nKill-zone planning: the modeled players share this one set of spawn attempts; no separate zones or kill mechanism are designed. Actual mob counts, spawn-proofing, kill capacity and rates are not calculated.\n\nGrid schematic: {}\nPlacement minimum corner (local 0,0,0): {}, {grid_y}, {}\nOrientation: unchanged\nAutosave detector approximate bounds: {}, {}, {} to {}, {}, {}\n\nThe plan assumes a complete sent-chunk square, a freshly sized Java 8 HashSet, normal-biome hostile spawn weights, and no intervening world-RNG calls. The blue control platform and detector chunk are within the modeled player view square; farther grid rows are outside. Actual chunk height, biome, world spawn distance, mob cap, previous player/chunk history, terrain, and reset timing can change the result. The 900-game-tick grid cycle, calibration, survival feasibility, and predicted mob result have not been validated as a complete build. Test in a disposable world.\n",
        mob.name(), c.region_x, c.region_z, x, z, radius, hostile_threshold(view, min_players), hostile_threshold(view, max_players),
        c.player.0, c.player.1, c.player.2, c.first_chunk.0, c.first_chunk.1,
        c.initial.0, c.initial.1, c.initial.2, attempts, grid.display(), grid_x, grid_z,
        grid_x + 194, grid_y + 3, grid_z + 9, grid_x + 206, grid_y + 7, grid_z + 17
    ))?;
    writeln!(std::fs::OpenOptions::new().append(true).open(&plan)?,
        "\nRequired height control: an opaque block at {}, {}, {}; keep light-blocking blocks out of the column above it and verify the heightmap.",
        c.initial.0, bound - 2, c.initial.2)?;
    writeln!(std::fs::OpenOptions::new().append(true).open(&plan)?,
        "\nMob roof: opaque bottom stone slabs at y={}; 15-block overhang around the sampled column and all modeled attempts; three clear blocks below. The roof stays below the height-control stone so the modeled Y bound remains {bound}. Bottom slabs prevent roof-top spawns and do not random tick. Clear the reported body/headroom before a non-air paste, including old glass spawn guards. Later pack attempts are conditional on pack length and earlier spawn initialization; only the first attempt has an unchanged call prefix.", c.initial.1 + 3)?;
    warn_control_boundary(&plan, c.region_x, c.region_z, view)?;
    finish_detector_export(path)?;
    println!("Saved {} and {}. The connected schematic preserves the loading grid; its calibration and the predicted gameplay result remain experimental.", grid.display(), plan.display());
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn java_random_values() {
        let mut r = JavaRandom::new(0);
        assert_eq!(r.next_int(16), 11);
        assert_eq!(r.next_int(100), 48);
    }
    #[test]
    fn portal_tick_model_java_reference() {
        assert_eq!(portal_tick_candidate(12345, 6, 7, 82, 3, 1), Some((3, 1)));
        assert_eq!(portal_tick_candidate(12345, 6, 7, 82, 1, 1), None);
        assert_eq!(portal_tick_candidate(12345, 0, 5, 82, 3, 1), None);
        assert_eq!(portal_tick_candidate(12345, 6, 7, 81, 3, 1), None);
    }

    #[test]
    fn portal_multiple_successes_java_reference() {
        assert_eq!(portal_tick_candidate(171656809007210, 0, 0, 82, 3, 1), Some((1, 1)));
        assert_eq!(portal_tick_candidate(171656809007210, 0, 0, 82, 3, 2), Some((2, 2)));
        assert_eq!(portal_tick_candidate(171656809007210, 0, 0, 82, 3, 3), None);
        assert_eq!(portal_tick_candidate(84785424703645, 0, 0, 82, 3, 3), Some((3, 1)));
        for (seed, state) in [(0, 234029835660143), (29, 57156724566644), (16414, 10881443173516)] {
            let mut rng = JavaRandom::new(seed);
            portal_spawn_draws(&mut rng);
            assert_eq!(rng.0, state); // Adult, baby/new-chicken roll, baby/existing-chicken roll.
        }
    }

    #[test]
    fn portal_fresh_list_order() {
        let order = portal_tick_order(8, 8, 10);
        assert_eq!(order.len(), 195);
        assert_eq!(order[0], (-7, -3, 70));
        assert_eq!(order[81], (-1, 0, 199));
        assert_eq!(order[194], (8, 0, 388));
        let shifted = portal_tick_order(-8, -24, 3);
        assert_eq!(shifted.len(), 49);
        assert_eq!(shifted[0], (-4, -5, 0));
        assert_eq!(shifted[17], (-2, -2, 17));
    }

    #[test]
    fn text_seed_is_java_hash() {
        assert_eq!(parse_seed("abc"), 96354);
        assert_eq!(parse_seed("-123"), -123);
        assert_eq!(parse_seed("😀"), 1772899);
    }
    #[test]
    fn java_spawn_reference() {
        let c = candidate(12345, 13, -13, 64, Mob::Witch, (0, 0), 10).unwrap();
        assert_eq!(c.first_chunk, (1066, -1015));
        assert_eq!(c.initial, (17069, 35, -16229));
        assert_eq!(c.attempts[0], (17069, 35, -16226));
        assert_eq!(c.weight, 513);
    }
    #[test]
    fn roof_rejects_height_bound_change() {
        // Independent Java prefix for seed328: Y13,witch weight511 with bound16.
        // A roof at16 would exceed the sampled-column control at14.
        assert!(candidate(328,0,0,16,Mob::Witch,(-456,-760),10).is_none());
    }
    #[test]
    fn height_bounds_recalculate_same_region() {
        // Independent java.util.Random results for the screenshot seed and region.
        for (bound, expected_y) in [(64, 33), (128, 66), (192, 78), (224, 174), (256, 132)] {
            let c = candidate(
                7480190280633614536,
                2,
                1,
                bound,
                Mob::Witch,
                (-456, -760),
                10,
            )
            .unwrap();
            assert_eq!(c.initial, (2585, expected_y, 1100));
            assert_eq!(c.y_bound, bound);
            assert_eq!(c.weight, 512);
        }
    }
    #[test]
    fn carpet_server_spawn_reference() {
        let c = candidate(12345, 13, -13, 16, Mob::Witch, (0, 0), 10).unwrap();
        assert_eq!(c.initial, (17069, 8, -16229));
        assert_eq!(
            c.attempts,
            [
                (17069, 8, -16226),
                (17067, 8, -16227),
                (17066, 8, -16223),
                (17067, 8, -16224)
            ]
        );
    }
    #[test]
    fn first_chunk_reference() {
        assert_eq!(first_spawn_chunk(32, 32, 10), (31, 38));
    }
    #[test]
    fn java_8_view_distance_reference() {
        for (view, expected) in [
            (3, (35, 30)),
            (4, (36, 33)),
            (5, (27, 37)),
            (6, (26, 33)),
            (7, (31, 38)),
            (10, (31, 38)),
        ] {
            assert_eq!(first_spawn_chunk(32, 32, view), expected);
        }
    }
    #[test]
    fn grid_view_intersection() {
        assert!(!grid_in_player_view((17152, 9, -16192), 13, -13, 17));
        assert!(grid_in_player_view((17152, 9, -16192), 13, -13, 18));
    }

    #[test]
    fn proposed_control_boundary_covers_blue_and_detector_only_to_row_one() {
        for view in 3..=32 {
            for (rx, rz) in [(0, 0), (-13, 7), (13, -7)] {
                let (x, _, z) = control_position(rx, rz, view);
                let (gx, gz) = (rx * 80 - 7, rz * 80 - 7);
                let (px, pz) = (x.div_euclid(16), z.div_euclid(16));
                for cx in 8..=13 {
                    assert!((px - (gx + cx)).abs() <= view);
                    assert!((pz - gz).abs() <= view);
                }
                assert!((px - (gx + 12)).abs() <= view);
                assert!((pz - (gz + 1)).abs() <= view);
                assert!((pz - (gz + 2)).abs() > view);
            }
        }
    }
    #[test]
    fn stacked_player_threshold_reference() {
        assert_eq!(hostile_threshold(10, 1), 70);
        assert_eq!(hostile_threshold(10, 2), 85);
        assert_eq!(hostile_threshold(3, 2), 128);
    }
    #[test]
    fn portal_java_reference() {
        let mut rng = mansion_reset_rng(12345, 0, -11);
        assert_eq!(
            [rng.next_int(2000), rng.next_int(2000), rng.next_int(2000)],
            [2, 1501, 446]
        );
        let mut rng = mansion_reset_rng(12345, 0, 5);
        assert_eq!(portal_success(&mut rng, 3, 1), Some((3, 2)));
        let mut rng = mansion_reset_rng(12345, 0, 5);
        assert_eq!(portal_success(&mut rng, 2, 1), None);
        let mut rng = mansion_reset_rng(12345, 2, -11);
        for _ in 0..7 {
            rng.next_int_unbounded();
        }
        assert_eq!(
            [rng.next_int(2000), rng.next_int(2000), rng.next_int(2000)],
            [634, 1908, 518]
        );
    }

    #[test]
    fn portal_exact_advances_match_vanilla_trace() {
        let mut rng = mansion_reset_rng(553, 2, 2);
        for _ in 0..29 {
            rng.next_int_unbounded();
        }
        assert_eq!(portal_success(&mut rng, 3, 1), Some((1, 0)));
    }

    #[test]
    fn fortune_java_reference() {
        let seed = 13_i64 * 341873128712 - 13_i64 * 132897987541 + 12345 + 10387319;
        for (ore, level, expected) in [
            ("diamond", 0, 1),
            ("diamond", 3, 3),
            ("coal", 3, 3),
            ("emerald", 3, 3),
            ("quartz", 3, 3),
            ("lapis", 0, 7),
            ("lapis", 3, 21),
            ("redstone", 0, 5),
            ("redstone", 3, 7),
        ] {
            let mut rng = JavaRandom::new(seed);
            for _ in 0..4 {
                rng.next(32);
            }
            assert_eq!(ore_quantity(&mut rng, ore, level), expected);
        }
        let mut rng = JavaRandom::new(seed);
        for _ in 0..4 {
            rng.next(32);
        }
        for expected in [3, 3, 3, 3, 4] {
            assert_eq!(ore_quantity(&mut rng.clone(), "diamond", 3), expected);
            rng.next(32);
        }
    }
    #[test]
    fn golem_java_reference() {
        assert_eq!(golem_player_chunks(10), 195);
        assert_eq!(golem_candidate(12345, 0, -5, 195), Some((4, -1, 3)));
        assert_eq!(golem_candidate(12345, 0, 0, 195), None);
    }

    #[test]
    fn iron_villager_count_thresholds() {
        for (villagers, limit) in [
            (0, 0),
            (9, 0),
            (10, 1),
            (30, 3),
            (299, 29),
            (300, 30),
            (309, 30),
            (310, 31),
        ] {
            assert_eq!(village_golem_limit(villagers), limit);
        }
    }
}

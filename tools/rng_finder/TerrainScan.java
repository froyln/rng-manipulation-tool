import java.io.*;
import java.lang.reflect.Field;
import java.util.*;
import it.unimi.dsi.fastutil.longs.Long2ObjectMap;
import net.minecraft.init.Bootstrap;
import net.minecraft.world.*;
import net.minecraft.world.storage.*;
import net.minecraft.world.chunk.*;
import net.minecraft.world.gen.*;
import net.minecraft.world.gen.structure.*;
import net.minecraft.profiler.Profiler;
import net.minecraft.util.math.BlockPos;

public class TerrainScan extends World {
    private TerrainScan(long seed) {
        super(null, new WorldInfo(new WorldSettings(seed, GameType.SURVIVAL, true, false, WorldType.DEFAULT), "probe"), new WorldProviderSurface(), new Profiler(), false);
        this.provider.setWorld(this);
        this.mapStorage = new MapStorage(null);
    }

    protected IChunkProvider createChunkProvider() { return null; }
    protected boolean isChunkLoaded(int x, int z, boolean allowEmpty) { return false; }

    private static List<int[]> readPoints(DataInputStream in) throws IOException {
        List<int[]> points = new ArrayList<>();
        while (in.available() > 0) points.add(new int[] {in.readInt(), in.readInt(), in.readInt()});
        return points;
    }

    private static void writeStructures(DataOutputStream out, ChunkGeneratorOverworld generator) throws Exception {
        List<String> structures = new ArrayList<>();
        for (String fieldName : new String[] {"villageGenerator", "strongholdGenerator", "mineshaftGenerator", "scatteredFeatureGenerator", "oceanMonumentGenerator", "woodlandMansionGenerator"}) {
            Field generatorField = ChunkGeneratorOverworld.class.getDeclaredField(fieldName);
            generatorField.setAccessible(true);
            MapGenStructure map = (MapGenStructure)generatorField.get(generator);
            Field startsField = MapGenStructure.class.getDeclaredField("structureMap");
            startsField.setAccessible(true);
            Long2ObjectMap<?> starts = (Long2ObjectMap<?>)startsField.get(map);
            for (Object value : starts.values()) {
                StructureStart start = (StructureStart)value;
                if (!start.isSizeableStructure()) continue;
                StructureBoundingBox box = start.getBoundingBox();
                structures.add(map.getStructureName() + "\t" + box.minX + "\t" + box.minY + "\t" + box.minZ + "\t" + box.maxX + "\t" + box.maxY + "\t" + box.maxZ);
            }
        }
        out.writeInt(structures.size());
        for (String line : structures) out.writeUTF(line);
    }

    private static boolean insideStructure(ChunkGeneratorOverworld generator, int[] p) throws Exception {
        for (String fieldName : new String[] {"villageGenerator", "strongholdGenerator", "mineshaftGenerator", "scatteredFeatureGenerator", "oceanMonumentGenerator", "woodlandMansionGenerator"}) {
            Field generatorField = ChunkGeneratorOverworld.class.getDeclaredField(fieldName);
            generatorField.setAccessible(true);
            MapGenStructure map = (MapGenStructure)generatorField.get(generator);
            Field startsField = MapGenStructure.class.getDeclaredField("structureMap");
            startsField.setAccessible(true);
            Long2ObjectMap<?> starts = (Long2ObjectMap<?>)startsField.get(map);
            for (Object value : starts.values()) {
                StructureBoundingBox b = ((StructureStart)value).getBoundingBox();
                if (p[0] >= b.minX && p[0] <= b.maxX && p[1] >= b.minY && p[1] <= b.maxY && p[2] >= b.minZ && p[2] <= b.maxZ) return true;
            }
        }
        return false;
    }

    public static void main(String[] args) throws Exception {
        Bootstrap.register();
        long seed = Long.parseLong(args[0]);
        List<int[]> points;
        try (DataInputStream in = new DataInputStream(new BufferedInputStream(new FileInputStream(args[1])))) { points = readPoints(in); }
        TerrainScan world = new TerrainScan(seed);
        ChunkGeneratorOverworld generator = new ChunkGeneratorOverworld(world, seed, true, "");
        Map<Long, List<Integer>> byChunk = new TreeMap<>();
        for (int i = 0; i < points.size(); ++i) {
            int[] p = points.get(i);
            long key = (((long)Math.floorDiv(p[0], 16)) << 32) ^ (Math.floorDiv(p[2], 16) & 0xffffffffL);
            byChunk.computeIfAbsent(key, unused -> new ArrayList<>()).add(i);
        }
        byte[] blockIds = new byte[points.size()];
        int firstTerrainHit = -1;
        int terrainHitId = 0;
        for (Map.Entry<Long, List<Integer>> entry : byChunk.entrySet()) {
            long key = entry.getKey();
            Chunk chunk = generator.generateChunk((int)(key >> 32), (int)key);
            for (int i : entry.getValue()) {
                int[] p = points.get(i);
                if (p[1] < 0 || p[1] > 255) { blockIds[i] = (byte)255; continue; }
                int id = net.minecraft.block.Block.getIdFromBlock(chunk.getBlockState(new BlockPos(Math.floorMod(p[0],16), p[1], Math.floorMod(p[2],16))).getBlock());
                blockIds[i] = (byte)id;
                if (id != 0 && !insideStructure(generator, p)) { firstTerrainHit = i; terrainHitId = id; break; }
            }
            if (firstTerrainHit >= 0) break;
        }
        try (DataOutputStream out = new DataOutputStream(new BufferedOutputStream(new FileOutputStream(args[2])))) {
            if (firstTerrainHit >= 0) {
                out.writeInt(-1);
                out.writeInt(firstTerrainHit);
                out.writeByte(terrainHitId);
                return;
            }
            out.writeInt(points.size());
            out.write(blockIds);
            writeStructures(out, generator);
        }
    }
}

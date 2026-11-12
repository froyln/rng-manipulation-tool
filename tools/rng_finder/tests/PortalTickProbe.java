import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Random;
import net.minecraft.entity.player.EntityPlayerMP;
import net.minecraft.init.Blocks;
import net.minecraft.init.Bootstrap;
import net.minecraft.profiler.Profiler;
import net.minecraft.server.management.PlayerChunkMap;
import net.minecraft.world.EnumDifficulty;
import net.minecraft.util.math.BlockPos;
import net.minecraft.world.GameType;
import net.minecraft.world.World;
import net.minecraft.world.WorldProviderSurface;
import net.minecraft.world.WorldServer;
import net.minecraft.world.WorldSettings;
import net.minecraft.world.WorldType;
import net.minecraft.world.chunk.Chunk;
import net.minecraft.world.chunk.storage.ExtendedBlockStorage;
import net.minecraft.world.storage.WorldInfo;
import sun.misc.Unsafe;

/** Runs the pinned Minecraft updateBlocks/playerCheckLight/BlockPortal methods.
 * Lighting, terrain and chunk iteration are controlled fixtures, not gameplay.
 */
public final class PortalTickProbe {
    private static final java.io.PrintStream OUT = System.out;
    private static final java.io.PrintStream ERR = System.err;
    private static final class Stop extends RuntimeException {}
    private static final class ProbeRandom extends Random {
        final List<Integer> rolls = new ArrayList<>();
        @Override public int nextInt(int bound) {
            int result = super.nextInt(bound);
            if (bound == 2000) {
                rolls.add(result);
                // Stop before entity construction changes the stream on success.
                if (result < 3) throw new Stop();
            }
            return result;
        }
    }
    private static final class ProbeWorld extends WorldServer {
        private ProbeWorld() { super(null, null, null, 0, null); }
        @Override public boolean checkLight(BlockPos pos) { return true; }
        @Override public boolean isRaining() { return false; }
        @Override public boolean isThundering() { return false; }
        @Override public BlockPos getPrecipitationHeight(BlockPos pos) { return new BlockPos(pos.getX(), 64, pos.getZ()); }
        @Override public boolean canBlockFreezeNoWater(BlockPos pos) { return false; }
        void runBlocks() { super.updateBlocks(); }
    }
    private static final class ProbeMap extends PlayerChunkMap {
        List<Chunk> chunks;
        private ProbeMap() { super(null); }
        @Override public Iterator<Chunk> getChunkIterator() { return chunks.iterator(); }
    }
    private static final class ProbeChunk extends Chunk {
        final ExtendedBlockStorage[] sections = new ExtendedBlockStorage[16];
        ProbeChunk(World world, int x, int z) { super(world, x, z); }
        @Override public void onTick(boolean skip) {}
        @Override public void enqueueRelightChecks() {}
        @Override public ExtendedBlockStorage[] getBlockStorageArray() { return sections; }
    }
    private static void set(Object object, Class<?> owner, String name, Object value) throws Exception {
        Field field = owner.getDeclaredField(name);
        field.setAccessible(true);
        field.set(object, value);
    }
    public static void main(String[] args) throws Exception {
        try { run(); } catch (Throwable error) {
            ERR.println(error.getClass().getName() + ": " + error.getMessage());
            for (StackTraceElement frame : error.getStackTrace()) ERR.println(frame.toString());
            System.exit(1);
        }
    }
    private static void run() throws Exception {
        Bootstrap.register();
        Field field = Unsafe.class.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        Unsafe unsafe = (Unsafe) field.get(null);
        ProbeWorld world = (ProbeWorld) unsafe.allocateInstance(ProbeWorld.class);
        ProbeMap map = (ProbeMap) unsafe.allocateInstance(ProbeMap.class);
        ProbeRandom random = new ProbeRandom();
        WorldInfo info = new WorldInfo(new WorldSettings(12345L, GameType.SURVIVAL, false, false, WorldType.DEFAULT), "probe");
        info.setDifficulty(EnumDifficulty.HARD);
        info.getGameRulesInstance().setOrCreateGameRule("doMobSpawning", "true");
        info.getGameRulesInstance().setOrCreateGameRule("randomTickSpeed", "3");
        set(world, World.class, "worldInfo", info);
        set(world, World.class, "rand", random);
        set(world, World.class, "profiler", new Profiler());
        set(world, World.class, "provider", new WorldProviderSurface());
        EntityPlayerMP player = (EntityPlayerMP) unsafe.allocateInstance(EntityPlayerMP.class);
        player.posX = 7752.5; player.posY = 66; player.posZ = 8712.5;
        List<net.minecraft.entity.player.EntityPlayer> players = new ArrayList<>();
        players.add(player);
        set(world, World.class, "playerEntities", players);
        map.chunks = new ArrayList<>();
        for (int x = 484 - 10; x <= 484 + 10; x++) {
            for (int z = 544 - 10; z <= 544 + 10; z++) {
                double dx = x * 16 + 8 - player.posX, dz = z * 16 + 8 - player.posZ;
                if (dx * dx + dz * dz >= 16384) continue;
                ProbeChunk chunk = new ProbeChunk(world, x, z);
                if (x == 483 && z == 544) {
                    ExtendedBlockStorage section = new ExtendedBlockStorage(80, true);
                    for (int xx = 0; xx < 16; xx++)
                        for (int yy = 0; yy < 16; yy++)
                            for (int zz = 0; zz < 16; zz++) section.set(xx, yy, zz, Blocks.PORTAL.getDefaultState());
                    chunk.sections[5] = section;
                }
                map.chunks.add(chunk);
            }
        }
        set(world, WorldServer.class, "playerChunkMap", map);
        world.setRandomSeed(6, 7, 10387319);
        for (int i = 0; i < 4; i++) random.nextInt(60);
        try { world.runBlocks(); } catch (Stop expected) {}
        if (!random.rolls.toString().equals("[1723, 1572, 1]")) throw new AssertionError(random.rolls);
        OUT.println("Pinned Minecraft tick pipeline: " + random.rolls);
    }
}

import java.lang.reflect.Constructor;
import net.minecraft.init.Bootstrap;
import net.minecraft.init.Blocks;
import net.minecraft.world.World;
import net.minecraft.world.chunk.Chunk;
import net.minecraft.world.gen.ChunkGeneratorOverworld;
import net.minecraft.util.math.BlockPos;
import net.minecraft.util.math.MathHelper;

class HeightControlProbe {
    private static final java.io.PrintStream ERR=System.err, OUT=System.out;
    public static void main(String[] args) throws Exception {
        try { run(); } catch (Throwable e) { e.printStackTrace(ERR); System.exit(1); }
    }
    private static void run() throws Exception {
        Bootstrap.register();
        Constructor<TerrainScan> constructor = TerrainScan.class.getDeclaredConstructor(long.class);
        constructor.setAccessible(true);
        long seed = 7480190280633614536L;
        World world = constructor.newInstance(seed);
        Chunk chunk = new ChunkGeneratorOverworld(world, seed, true, "").generateChunk(161, 68);
        BlockPos position = new BlockPos(2585, 222, 1100);
        chunk.setBlockState(position, Blocks.STONE.getDefaultState());
        chunk.setBlockState(position.up(), Blocks.GLASS.getDefaultState());
        chunk.setBlockState(new BlockPos(2585, 177, 1100), Blocks.STONE_SLAB.getStateFromMeta(0));
        int height = chunk.getHeight(position);
        int bound = MathHelper.roundUp(height + 1, 16);
        if (height != 223 || bound != 224 || Blocks.GLASS.getDefaultState().getLightOpacity() != 0) {
            throw new AssertionError("Unexpected heightmap or glass opacity: " + height + ", " + bound);
        }
        OUT.println("Heightmap=223; random bound=224; glass opacity=0");
    }
}

import java.io.FileInputStream;
import java.util.HashSet;
import java.util.UUID;
import net.minecraft.entity.Entity;
import net.minecraft.entity.EntityList;
import net.minecraft.entity.passive.EntityVillager;
import net.minecraft.init.Bootstrap;
import net.minecraft.init.Blocks;
import net.minecraft.block.state.IBlockState;
import net.minecraft.util.math.BlockPos;
import net.minecraft.nbt.CompressedStreamTools;
import net.minecraft.nbt.NBTTagList;
import net.minecraft.profiler.Profiler;
import net.minecraft.world.GameType;
import net.minecraft.world.World;
import net.minecraft.world.WorldProviderSurface;
import net.minecraft.world.WorldSettings;
import net.minecraft.world.WorldType;
import net.minecraft.world.chunk.IChunkProvider;
import net.minecraft.world.storage.WorldInfo;

class VillagerEntityProbe extends World {
    private VillagerEntityProbe() {
        super(null, new WorldInfo(new WorldSettings(0, GameType.SURVIVAL, true, false, WorldType.DEFAULT), "probe"),
              new WorldProviderSurface(), new Profiler(), false);
        this.provider.setWorld(this);
    }
    public IBlockState getBlockState(BlockPos pos) { return Blocks.AIR.getDefaultState(); }
    protected IChunkProvider createChunkProvider() { return null; }
    protected boolean isChunkLoaded(int x, int z, boolean allowEmpty) { return false; }

    public static void main(String[] args) throws Exception {
        java.io.PrintStream output = System.out;
        Bootstrap.register();
        if (Blocks.PORTAL.getStateFromMeta(1).isNormalCube() || !Blocks.OBSIDIAN.getDefaultState().isTopSolid())
            throw new AssertionError("Portal or support fails the vanilla golem clearance test");
        NBTTagList list = CompressedStreamTools.readCompressed(new FileInputStream(args[0])).getTagList("Entities", 10);
        if (list.tagCount() != 300) throw new AssertionError("Expected 300 villagers");
        World world = new VillagerEntityProbe();
        HashSet<UUID> ids = new HashSet<>();
        for (int i = 0; i < list.tagCount(); ++i) {
            Entity e = EntityList.createEntityFromNBT(list.getCompoundTagAt(i), world);
            NBTTagList pos = list.getCompoundTagAt(i).getTagList("Pos", 6);
            if (!(e instanceof EntityVillager) || ((EntityVillager)e).isChild() || ((EntityVillager)e).getHealth() <= 0 ||
                e.posX != pos.getDoubleAt(0) || e.posY != pos.getDoubleAt(1) || e.posZ != pos.getDoubleAt(2) || !ids.add(e.getUniqueID())) {
                throw new AssertionError("Villager could not be loaded as a unique adult");
            }
        }
        output.println("Loaded 300 adult villagers with unique IDs through Minecraft 1.12.2 EntityList");
    }
}

import java.lang.reflect.Field;
import java.util.*;
import com.google.common.base.Predicate;
import net.minecraft.block.state.IBlockState;
import net.minecraft.entity.*;
import net.minecraft.entity.player.EntityPlayer;
import net.minecraft.init.*;
import net.minecraft.item.ItemMonsterPlacer;
import net.minecraft.util.*;
import net.minecraft.util.math.*;
import net.minecraft.world.*;
import net.minecraft.world.storage.WorldInfo;
import sun.misc.Unsafe;

/** Exercise real 1.12.2 portal/spawn methods; controlled floor/world services, not gameplay. */
public class PortalSpawnSequenceProbe {
    static final java.io.PrintStream OUT = System.out;
    static class ProbeWorld extends WorldServer {
        int pigmen;
        private ProbeWorld() { super(null,null,null,0,null); }
        @Override public IBlockState getBlockState(BlockPos p) { return (p.getY()<=64 ? Blocks.STONE : Blocks.AIR).getDefaultState(); }
        @Override public DifficultyInstance getDifficultyForLocation(BlockPos p) { return new DifficultyInstance(EnumDifficulty.HARD,0,0,0); }
        @Override public Calendar getCurrentDate() { return new GregorianCalendar(2026,10,12); }
        @Override public boolean spawnEntity(Entity entity) { if (entity instanceof net.minecraft.entity.monster.EntityPigZombie) pigmen++; return true; }
        @Override public void playSound(EntityPlayer p,double x,double y,double z,SoundEvent s,SoundCategory c,float v,float pitch) {}
        @Override public <T extends Entity> List<T> getEntitiesWithinAABB(Class<? extends T> c,AxisAlignedBB box,Predicate<? super T> filter) { return Collections.emptyList(); }
    }
    static void set(Object o,Class<?> owner,String name,Object value) throws Exception {
        Field f=owner.getDeclaredField(name);f.setAccessible(true);f.set(o,value);
    }
    static void spawnDraws(Random rng) {
        rng.nextFloat();
        if(rng.nextFloat()<0.05F && (double)rng.nextFloat()>=0.05D) rng.nextFloat();
    }
    static ProbeWorld world(Unsafe unsafe,Random rng) throws Exception {
        ProbeWorld w=(ProbeWorld)unsafe.allocateInstance(ProbeWorld.class);
        WorldInfo info=new WorldInfo(new WorldSettings(0,GameType.SURVIVAL,false,false,WorldType.DEFAULT),"probe");
        info.setDifficulty(EnumDifficulty.HARD);info.getGameRulesInstance().setOrCreateGameRule("doMobSpawning","true");
        set(w,World.class,"rand",rng);set(w,World.class,"worldInfo",info);set(w,World.class,"provider",new WorldProviderSurface());
        return w;
    }
    public static void main(String[] args) throws Exception {
        try {
            Bootstrap.register();Field f=Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);Unsafe u=(Unsafe)f.get(null);
            // Include every adult/baby/jockey branch without relying on entity RNG seeds.
            for(int test=0;test<513;test++) {
                int seed=test==512 ? 16414 : test;
                Random actual=new Random(seed),expected=new Random(seed);ProbeWorld w=world(u,actual);
                ItemMonsterPlacer.spawnCreature(w,EntityList.getKey(net.minecraft.entity.monster.EntityPigZombie.class),0.5,65.1,0.5);
                spawnDraws(expected);
                if(actual.nextLong()!=expected.nextLong()) throw new AssertionError("Spawn draws seed "+seed);
            }
            long[] seeds={171656809007210L,84785424703645L};int[][] wanted={{1,2,669},{0,2,1}};
            for(int test=0;test<seeds.length;test++) {
                long seed=seeds[test];Random actual=new Random(seed+10387319L),expected=new Random(seed+10387319L);
                for(Random r:new Random[]{actual,expected}) {for(int i=0;i<4;i++)r.nextInt(60);r.nextInt(1);for(int i=0;i<3;i++)r.nextInt(11);for(int i=0;i<82;i++)r.nextInt(16);}
                ProbeWorld w=world(u,actual);List<Integer> rolls=new ArrayList<>();
                for(int i=0;i<3;i++) {
                    int roll=expected.nextInt(2000);rolls.add(roll);if(roll<3)spawnDraws(expected);
                    Blocks.PORTAL.updateTick(w,new BlockPos(0,80,0),Blocks.PORTAL.getDefaultState(),actual);
                }
                for(int i=0;i<3;i++)if(rolls.get(i)!=wanted[test][i])throw new AssertionError(rolls);
                if(w.pigmen!=test+2 || actual.nextLong()!=expected.nextLong())throw new AssertionError("Real portal sequence "+seed);
                OUT.println(seed+": "+rolls+"; actual pigmen="+w.pigmen);
            }
            OUT.println("Pinned spawn methods match World.rand model for 513 initializations and both multi-success sequences");
        } catch(Throwable e) {e.printStackTrace(OUT);System.exit(1);}
    }
}

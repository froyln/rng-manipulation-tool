import java.util.*;
import net.minecraft.block.state.IBlockState;
import net.minecraft.entity.EntityLiving;
import net.minecraft.entity.monster.*;
import net.minecraft.init.*;
import net.minecraft.profiler.Profiler;
import net.minecraft.util.math.*;
import net.minecraft.world.*;
import net.minecraft.world.chunk.*;
import net.minecraft.world.storage.*;

/** Native height/light/collision methods in a controlled empty world; not gameplay. */
public class MobRoofProbe {
 private static final java.io.PrintStream OUT=System.out, ERR=System.err;
 static class RoofWorld extends World {
  Map<Long,Chunk> chunks=new HashMap<>();
  RoofWorld() {
   super(null,new WorldInfo(new WorldSettings(12345,GameType.SURVIVAL,false,false,WorldType.DEFAULT),"roof"),new WorldProviderSurface(),new Profiler(),false);
   provider.setWorld(this);chunkProvider=createChunkProvider();mapStorage=new MapStorage(null);worldInfo.setDifficulty(EnumDifficulty.HARD);worldInfo.setWorldTime(6000);
   for(int x=-4;x<=4;x++)for(int z=-4;z<=4;z++)chunks.put(ChunkPos.asLong(x,z),new Chunk(this,x,z));
  }
  protected boolean isChunkLoaded(int x,int z,boolean empty) {return chunks!=null && chunks.containsKey(ChunkPos.asLong(x,z));}
  protected IChunkProvider createChunkProvider() {return new IChunkProvider(){
   public Chunk getLoadedChunk(int x,int z){return chunks.get(ChunkPos.asLong(x,z));}
   public Chunk provideChunk(int x,int z){return getLoadedChunk(x,z);}
   public boolean tick(){return false;}
   public String makeString(){return "controlled-roof";}
   public boolean isChunkGeneratedAt(int x,int z){return isChunkLoaded(x,z,true);}
  };}
 }
 public static void main(String[] args) throws Exception {
  try {run();} catch(Throwable error){error.printStackTrace(ERR);System.exit(1);}
 }
 static void run() throws Exception {
  Bootstrap.register();RoofWorld world=new RoofWorld();
  IBlockState slab=Blocks.STONE_SLAB.getStateFromMeta(0);
  if(slab.getLightOpacity()!=255 || slab.isTopSolid() || slab.getBlock().getTickRandomly())throw new AssertionError("Roof slab properties");
  BlockPos pos=new BlockPos(0,64,0);
  world.setBlockState(pos.down(),Blocks.CONCRETE.getDefaultState(),2);
  for(int x=-15;x<=15;x++)for(int z=-15;z<=15;z++)world.setBlockState(new BlockPos(x,67,z),slab,2);
  world.setBlockState(new BlockPos(0,78,0),Blocks.STONE.getDefaultState(),2);
  world.setBlockState(new BlockPos(0,79,0),Blocks.GLASS.getDefaultState(),2);
  for(Chunk c:world.chunks.values())c.generateSkylightMap();
  for(int pass=0;pass<2;pass++)for(int y=63;y<=68;y++)for(int x=-17;x<=17;x++)for(int z=-17;z<=17;z++)world.checkLight(new BlockPos(x,y,z));
  int height=world.getChunk(pos).getHeight(pos),bound=MathHelper.roundUp(height+1,16);
  if(height!=79 || bound!=80)throw new AssertionError("Sampled height/bound "+height+"/"+bound);
  for(int x=-1;x<=1;x++)for(int z=-1;z<=1;z++)for(int y=64;y<=66;y++){
   BlockPos p=new BlockPos(x,y,z);
   if(world.getLightFor(EnumSkyBlock.SKY,p)!=0 || world.getLightFromNeighbors(p)!=0)throw new AssertionError("Daylight leak "+p+"="+world.getLightFor(EnumSkyBlock.SKY,p));
  }
  java.lang.reflect.Method sample=WorldEntitySpawner.class.getDeclaredMethod("getRandomChunkPosition",World.class,int.class,int.class);
  sample.setAccessible(true);world.rand.setSeed(123);Random reference=new Random(123);
  int sx=reference.nextInt(16),sz=reference.nextInt(16),sy=reference.nextInt(80);
  BlockPos sampled=(BlockPos)sample.invoke(null,world,0,0);
  if(!sampled.equals(new BlockPos(sx,sy,sz)))throw new AssertionError("Native roof sampling sequence "+sampled);
  EntityLiving[] mobs={new EntityWitch(world),new EntityCreeper(world),new EntitySkeleton(world),new EntityZombie(world),new EntitySpider(world),new EntityEnderman(world)};
  for(EntityLiving mob:mobs){
   mob.setLocationAndAngles(.5,64,.5,0,0);
   if(!world.getCollisionBoxes(mob,mob.getEntityBoundingBox()).isEmpty() || !mob.getCanSpawnHere())throw new AssertionError("Body/light "+mob.getClass());
  }
  if(WorldEntitySpawner.canCreatureTypeSpawnAtLocation(EntityLiving.SpawnPlacementType.ON_GROUND,world,new BlockPos(1,68,1)))throw new AssertionError("Roof creates a spawn floor");
  Random rejection=new Random(328L+10387319L);
  for(int i=0;i<4;i++)rejection.nextInt();
  rejection.nextInt(16);rejection.nextInt(16);
  if(rejection.nextInt(16)!=13)throw new AssertionError("Roof-bound rejection reference Y");
  for(int b:new int[]{6,6,1,1,6,6})rejection.nextInt(b);
  if(rejection.nextInt(515)!=511)throw new AssertionError("Roof-bound rejection reference weight");
  for(int x=-15;x<=15;x++)for(int z=-15;z<=15;z++)world.setBlockState(new BlockPos(x,67,z),Blocks.AIR.getDefaultState(),2);
  if(world.getLightFromNeighbors(pos)<=7 || mobs[0].getCanSpawnHere())throw new AssertionError("Unroofed daytime control must reject hostile spawning");
  OUT.println("Native roof: opacity255/no random ticks/nonspawnable top; daytime sky/block light0; six mob bodies including Enderman/Spider; heightmap79/bound80; unroofed daytime control rejects spawn");
 }
}

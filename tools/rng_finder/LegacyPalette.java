import java.io.*;
import net.minecraft.block.Block;
import net.minecraft.init.Bootstrap;
import net.minecraft.nbt.*;

/** Use the pinned game to translate legacy IDs/metadata, preserving redstone states. */
public class LegacyPalette {
 public static void main(String[] args) throws Exception {
  PrintStream err=System.err;
  try {
   Bootstrap.register();
   NBTTagList states=new NBTTagList();
   try(DataInputStream in=new DataInputStream(new FileInputStream(args[0]))) {
    while(in.available()>0) {
     int legacy=in.readUnsignedShort();
     Block block=Block.getBlockById(legacy>>4);
     if(block==null) throw new IllegalArgumentException("Unknown block ID "+(legacy>>4));
     NBTTagCompound entry=new NBTTagCompound();entry.setInteger("Legacy",legacy);
     entry.setTag("State",NBTUtil.writeBlockState(new NBTTagCompound(),block.getStateFromMeta(legacy&15)));
     states.appendTag(entry);
    }
   }
   NBTTagCompound root=new NBTTagCompound();root.setTag("States",states);
   try(OutputStream out=new FileOutputStream(args[1])) {CompressedStreamTools.writeCompressed(root,out);}
  } catch(Throwable error) {error.printStackTrace(err);System.exit(1);}
 }
}

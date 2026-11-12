import java.util.Random;

public final class PortalRandomProbe {
    private static String portalRolls(long seed, int regionX, int regionZ, int advances) {
        long mansionSeed = (long) regionX * 341873128712L
                + (long) regionZ * 132897987541L + seed + 10387319L;
        Random rand = new Random(mansionSeed);
        for (int i = 0; i < 4; i++) rand.nextInt(60);
        for (int i = 0; i < advances; i++) rand.nextInt();
        return rand.nextInt(2000) + "," + rand.nextInt(2000) + "," + rand.nextInt(2000);
    }

    public static void main(String[] args) {
        // Independent fresh-list fixture from PlayerChunkMap.addPlayer/getChunkIterator.
        java.util.List<int[]> entries = new java.util.ArrayList<>();
        for (int x = -10; x <= 10; x++)
            for (int z = -10; z <= 10; z++) entries.add(new int[] {x, z});
        int rank = 0;
        for (int index = 0; index < entries.size(); index++) {
            int[] chunk = entries.get(index);
            double dx = chunk[0] * 16 + 8 - 8.5;
            double dz = chunk[1] * 16 + 8 - 8.5;
            if (dx * dx + dz * dz >= 128 * 128) continue;
            rank++;
            if (rank == 1 && (chunk[0] != -7 || chunk[1] != -3 || index != 70))
                throw new AssertionError("first ticking chunk");
            if (chunk[0] == -1 && chunk[1] == 0 && (rank != 82 || index != 199))
                throw new AssertionError("portal tick rank");
        }
        if (rank != 195) throw new AssertionError("ticking chunk count");
        System.out.println(portalRolls(12345L, 0, -11, 0));
        System.out.println(portalRolls(12345L, 2, -11, 7));
        System.out.println(portalRolls(12345L, 0, 5, 0));
        System.out.println(portalRolls(553L, 2, 2, 29));
        Random tick = new Random(12345L + 6L * 341873128712L + 7L * 132897987541L + 10387319L);
        for (int i = 0; i < 4; i++) tick.nextInt(60);
        tick.nextInt(1);
        for (int i = 0; i < 3; i++) tick.nextInt(11);
        for (int i = 0; i < 82; i++) tick.nextInt(16);
        String rolls = tick.nextInt(2000) + "," + tick.nextInt(2000) + "," + tick.nextInt(2000);
        if (!rolls.equals("1723,1572,1")) throw new AssertionError(rolls);
    }
}

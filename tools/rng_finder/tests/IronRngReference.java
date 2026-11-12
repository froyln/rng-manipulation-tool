import java.util.Random;

public final class IronRngReference {
    public static void main(String[] args) {
        long seed = 12345L + 0L * 341873128712L - 5L * 132897987541L + 10387319L;
        Random rand = new Random(seed);
        for (int i = 0; i < 4; i++) rand.nextInt(60);
        rand.nextInt(1); // WorldServer.playerCheckLight: one player
        rand.nextInt(11);
        rand.nextInt(11);
        rand.nextInt(11);
        for (int i = 0; i < 195; i++) rand.nextInt(16);
        rand.nextInt(50); // Village.removeDeadAndOutOfRangeDoors
        int roll = rand.nextInt(7000);
        System.out.println(roll);
        if (roll == 0) {
            System.out.println((rand.nextInt(16) - 8) + "," + (rand.nextInt(6) - 3) + "," + (rand.nextInt(16) - 8));
        }
    }
}

package Bug_triggering_input.Compiler_triggering_input.JDK_8189172;


public class PowTest {

   public static void main(String[] args) {
      double b = 0.3333333333333333D;
      double e = 2.0D;
      double r = Math.pow(b, e);

      double n;
      for(n = b * b; r == n; r = b * b) {
         b += 0.3333333333333333D;
         n = Math.pow(b, e);
      }

      System.out.println("found b=" + b + " n=" + n + " r=" + r);

      for(r = n = Math.pow(b, e); r == n; n = Math.pow(b, e)) {
         ;
      }

      System.out.println("bad b=" + b + " n=" + n + " r=" + r);
   }
}

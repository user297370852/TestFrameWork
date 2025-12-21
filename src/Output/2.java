package compiler.interpreter;


public class TestVerifyStackAfterDeopt {

   public static long TRAPCOUNT = 0L;


   public static void main(String[] var0) {
      TestVerifyStackAfterDeopt var7 = new TestVerifyStackAfterDeopt();

      for(int var1 = 0; var1 < 100000; ++var1) {
         var7.test();

         try {
            if(true) {
               throw new OutOfMemoryError("");
            }
         } catch (OutOfMemoryError var6) {
            OutOfMemoryError var2 = var6;

            try {
               if(var2 != null) {
                  throw new OutOfMemoryError("");
               }
            } catch (OutOfMemoryError var5) {
               try {
                  if(var2 != null) {
                     throw new OutOfMemoryError("<");
                  }
               } catch (OutOfMemoryError var4) {
                  ++TRAPCOUNT;
               }

               ++TRAPCOUNT;
            }

            ++TRAPCOUNT;
         }
      }

   }

   private void method(Object[] var1) {
      try {
         if(var1 != null) {
            throw new OutOfMemoryError((String)null);
         }
      } catch (OutOfMemoryError var2) {
         this = null;
         ++TRAPCOUNT;
      }

      new GCObj(new GCObj((GCObj)null, (GCObj)null, (GCObj)null, (GCObj)null, 1), new GCObj((GCObj)null, (GCObj)null, (GCObj)null, (GCObj)null, 8192), new GCObj((GCObj)null, (GCObj)null, (GCObj)null, (GCObj)null, 2097152), new GCObj((GCObj)null, (GCObj)null, (GCObj)null, (GCObj)null, 256), 4);
      this = null;
   }

   private void test() {
      this.method(new Object[0]);
   }
}

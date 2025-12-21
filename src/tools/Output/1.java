package compiler.interpreter;

import java.util.LinkedList;

public class TestVerifyStackAfterDeopt {

   public volatile LinkedList field_6779 = new LinkedList();
   public static long TRAPCOUNT = 0L;


   public static void main(String[] var0) {
      TestVerifyStackAfterDeopt var1 = new TestVerifyStackAfterDeopt();

      for(int var2 = 0; var2 < 100000; ++var2) {
         var1.test();
         GCObj var4;
         GCObj var10000 = var4 = new GCObj;
         var4.<init>((GCObj)null, (GCObj)null, (GCObj)null, (GCObj)null, 131072);
         GCObj var3 = new GCObj((GCObj)null, (GCObj)null, (GCObj)null, (GCObj)null, 256);
         GCObj var10001 = new GCObj(var4, (GCObj)null, (GCObj)null, var3, 2);
         var0 = null;
         var3 = null;
         var4 = new GCObj((GCObj)null, (GCObj)null, (GCObj)null, (GCObj)null, 131072);
         GCObj var10003 = new GCObj(var4, (GCObj)null, (GCObj)null, (GCObj)null, 256);
         var0 = null;
         var0 = new String[16];
         var4 = new GCObj((GCObj)null, (GCObj)null, (GCObj)null, (GCObj)null, 256);
         GCObj var10004 = new GCObj(var4, (GCObj)null, (GCObj)null, (GCObj)null, '\u8000');
         var0 = null;
         var10000.<init>(var10001, (GCObj)null, var10003, var10004, 262144);
         var0 = null;
      }

   }

   private void method(Object[] var1) {
      try {
         if(var1 != null) {
            throw new OutOfMemoryError();
         }
      } catch (OutOfMemoryError var2) {
         this = null;
         this = null;
         ++TRAPCOUNT;
      }

   }

   private void test() {
      this.method(new Object[0]);
   }
}

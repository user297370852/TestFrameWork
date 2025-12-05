# 使用方式
```
# 运行测试（基本用法）
python class_runner.py /path/to/Testcases

# 运行测试并保存详细报告
python class_runner.py /path/to/Testcases my_report.json

# 如果你在Testcases的父目录中
python class_runner.py Testcases
```
# 说明
自动包名解析：
```根据目录名自动推断包结构，需要符合下面规约：
若目录下有子目录，则该目录下全为子目录
若目录下有文件，则该目录下全为文件
我们只考虑.class文件的运行，可以保证：
.class所在的目录名=包名+'.'+类名
例如目录Bug_triggering_input.Compiler_triggering_input.JDK_4343763.Test2
下有文件Bug_triggering_input.Compiler_triggering_input.JDK_4343763.Test2_0101@1761295864593.class，
则该class的包名为Bug_triggering_input.Compiler_triggering_input.JDK_4343763，主类名为Test2。
注意包名不是一定存在的，例如目录ACCModule52下有文件ACCModule52_xxx.class，
此时说明该class源代码并没有package语句，主类是ACCModule52
```
临时目录：使用临时目录运行，不修改原文件

超时控制：防止卡死的测试用例,在TestRun.py的main函数设置超时值

详细报告：生成成功/失败统计和详细错误信息

递归扫描：自动扫描所有子目录中的.class文件，**注意GCObj默认是该项目目录下**

错误处理：妥善处理各种异常情况

输出示例
text
Testing: Testcases/classHistory/Bug_triggering_input.Compiler_triggering_input.JDK_4311383.stmt06501/Bug_triggering_input.Compiler_triggering_input.JDK_4311383.stmt06501-origin.class
  ✓ SUCCESS: Bug_triggering_input.Compiler_triggering_input.JDK_4311383.stmt06501
Testing: Testcases/classHistory/Bug_triggering_input.Compiler_triggering_input.JDK_4311383.stmt06501/Bug_triggering_input.Compiler_triggering_input.JDK_4311383.stmt06501_0101@1761296994580.class
  ✓ SUCCESS: Bug_triggering_input.Compiler_triggering_input.JDK_4311383.stmt06501

============================================================
TEST REPORT
============================================================
Total class files tested: 156
Successful: 142
Failed: 14
Success rate: 91.03%
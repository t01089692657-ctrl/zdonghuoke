"""本地 fake 适配器：确定性、无外部调用、无费用。

用途：Mac mini 本地开发、CI 测试、演示。行为可预测（同输入同输出），
因此可以写断言测试。切到 ADAPTER_MODE=cloud 即换成 real 适配器。
"""

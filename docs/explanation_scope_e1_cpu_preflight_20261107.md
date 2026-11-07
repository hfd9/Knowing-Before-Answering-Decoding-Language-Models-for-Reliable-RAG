# E1 CPU联检及用户GPU预检入口

日期：2026-11-07，Asia/Shanghai。用户要求助手完成不依赖GPU的工作，GPU相关命令由用户运行。现有真实采集门禁仍关闭；本文件提供的是设备检查命令，不是采集命令。

## CPU端完成情况

[两项跨组件合成联检](../tests/test_explanation_scope_e1_end_to_end.py)分别贯穿：模拟48条完整生成→随机转包→逐主张封存→人工声明连接→12对汇总→重放；以及第五条模拟空输出→立即停止→四条可评分/一条空/43未生成→部分封存和完整12对识别界。测试中的模型、回答、评审和端点均是人工合成数据，没有真实语义结果。完整案例各J=no，差为0；部分案例仅第一对完整，剩余11对未决，界为[-11/12, 11/12]，仅用于检验计算与分母。

[实际CPU文件核验](review/2026-11-07-explanation-scope-e1/cpu-preflight-20261107.json)于2026-11-07 12:30:58 UTC完成：七个模型文件包括两权重分片SHA均与冻结参考匹配；同时核对E1协议、旧计划、执行锁和新增评分接收的五项源哈希。环境Python 3.11.15、PyTorch 2.5.1+cu121、Transformers 4.56.2、Accelerate 1.10.1、safetensors 0.6.2、tokenizers 0.22.2。检查仅流式读取模型文件和包元数据，不将权重加载到模型、不调用CUDA或前向；版本号和哈希不能证明运行时兼容或GPU就绪。时点和源文件以JSON为准，正式运行前须重新核验。

CPU核验器：[verify_explanation_scope_e1_cpu.py](../scripts/verify_explanation_scope_e1_cpu.py)。用户GPU预检器：[verify_explanation_scope_e1_gpu.py](../scripts/verify_explanation_scope_e1_gpu.py)；其4项测试仅mock设备，不接触真实GPU。

## 用户自行运行的设备预检

在项目根目录执行（默认查询`nvidia-smi`的GPU 0；如需其他设备，替换数字）：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_explanation_scope_e1_gpu.py --gpu-id 0
```

程序先核对E1当前代码锁，再查询GPU信息与计算进程；若检测到计算进程则停止，不初始化PyTorch CUDA。空闲时按GPU UUID设置可见设备并查询PyTorch CUDA、设备名和bf16能力；CUDA设备探测可能初始化GPU上下文，但不加载模型、不分配实验输入、不生成或训练。输出是当时的设备快照，不能保证独占，也不能证明真实模型/CUDA兼容。请把JSON输出返回给助手；如命令报错或显示busy，保留输出以便排查。

门禁仍关闭，`formal_gate=false`、`gpu_launch_ready=false`，尚无可以合法启动48条真实采集的命令。对E1最新[执行者补充](explanation_scope_e1_user_execution_addendum_20261107.md)，未来需要GPU的正式采集由用户执行；在取得设备证据并完成正式门禁及执行版本审查前，不提供绕过关闭门禁的命令。

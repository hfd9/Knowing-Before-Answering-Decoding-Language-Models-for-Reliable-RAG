# 2026-11-07：E1 CPU端到端联检、模型哈希与用户GPU预检

时间与时区：2026-11-07，Asia/Shanghai。状态：授权范围内CPU准备完成；GPU预检待用户自行运行，正式门禁保持关闭。操作者：助手；GPU实际操作者按用户最新指令为用户。

## 用户要求与范围

用户要求助手直接完成不需要GPU的工作，任何需要GPU的工作提供命令由用户运行。这取代旧E1-r1中未来由助手启动的表述；已另存[执行者约定补充](../explanation_scope_e1_user_execution_addendum_20261107.md)，不改冻结协议或历史事实。新增[CPU联检和设备预检说明](../explanation_scope_e1_cpu_preflight_20261107.md)、[CPU文件核验器](../../scripts/verify_explanation_scope_e1_cpu.py)、[用户GPU预检器](../../scripts/verify_explanation_scope_e1_gpu.py)、跨组件和GPU检查mock测试。没有执行GPU预检或生成模型回答。

## CPU实际结果

- [跨组件联检](../../tests/test_explanation_scope_e1_end_to_end.py)2项，16.224秒，exit 0。真实tokenizer、临时目录、显式模拟门禁/CPU假模型生成，连接E1执行器→随机部分包→逐主张封存→封存后人工声明端点→12对汇总→私有临时重放。完整48条的全部合成J=no、差0；第五条空输出后4条可评分/1空/43未生成，第一对已审，其余11对未决，界[-11/12,11/12]。全部都是synthetic假回答/假声明，不是实验、独立评分或语义结论。
- [CPU文件预检](../../scripts/verify_explanation_scope_e1_cpu.py)exit 0，20.531秒；[实际JSON](../review/2026-11-07-explanation-scope-e1/cpu-preflight-20261107.json)记录UTC 12:30:58，7个模型文件SHA均匹配，两个权重分片约6.17 GB为流式读文件而非模型加载；E1执行锁、旧计划及评分接收5个源哈希均匹配，两个真实run目录不存在。Python 3.11.15、torch 2.5.1+cu121、transformers 4.56.2、accelerate 1.10.1、safetensors 0.6.2、tokenizers 0.22.2；未调用CUDA，版本号与文件哈希不能认证GPU/模型实际兼容。
- [用户GPU预检器](../../scripts/verify_explanation_scope_e1_gpu.py)四项mock测试0.036秒exit 0：GPU忙时在PyTorch CUDA前停止、按UUID选设备、不可用及nvidia-smi失败。测试没有访问真实GPU。真实预检命令见[CPU联检说明](../explanation_scope_e1_cpu_preflight_20261107.md)；只查询设备/占用和CUDA/bf16，不加载模型或开启门禁，设备状态不能保证独占。

## 门禁与后续

E1协议/代码锁、旧v1和此前55/48实际复评原件未改；源文件公开导致48问题+文档可全文再识别条件的局限保留。正式独立批准0、formal_gate=false、gpu_launch_ready=false、collection_allowed=false，拟合预算0、正式标签null、380题封存，48真实新回答0。

用户可自行执行文档中的**GPU设备预检命令**并返回输出；这不是采集命令。正式采集前仍需结合用户实际设备证据、明确采集决定，形成绑定执行者补充及更新代码指纹的新版本并审查门禁；本轮没有绕过原关闭门禁或准备可用的真实采集入口。待放行后涉及GPU的采集命令由用户运行，助手随后核验和分析。实验指标未更新；按长期约定提交推送，实际哈希以Git及回复为准。

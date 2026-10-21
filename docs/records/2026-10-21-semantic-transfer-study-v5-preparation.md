# 2026-10-21：v5跨表达执行版本CPU准备与门禁实测完成

状态：v5_executor_CPU_prepared_verified / review_gate_closed / no_GPU。

用户要求直接开始后续工作。本轮已完成绑定v5材料的新执行入口、实际CPU prepare/独立进程verify、门禁实测、240输入独立桥接和持久交接。独立审核条件保持原样；未将上一轮有历史暴露的作者验收用作训练标签。没有新的迁移成绩或模型行为结果。

## 新版本及冻结复用

新增scripts/semantic_transfer_study_v5.py、run_semantic_transfer_study_v5.sh、test_semantic_transfer_study_v5.py。新入口固定使用runs/qwen2.5-3b-semantic-transfer-materials-v5；新准备目录为runs/qwen2.5-3b-semantic-transfer-study-v5-preparation-v1。

旧scripts/semantic_transfer_study.py与旧准备目录保持原样。新入口复用其冻结的审核接收、生成前旧probe回调、严格缓存、开发触发、最多一次拟合、评估锁及离线报告实现，只另存材料验证/CPU协议绑定和CLI。没有修改旧模块的全局默认值、源码或指纹。

v5绑定新增检查：材料version=5、v5 spec、131段修订声明及来源快照；重放上一轮作者验收封存，绑定其风险和清单哈希。验收的116/60/60/4unknown仅作为已知风险的来源记录，绝不传给approval_labels、拟合或评价标签。四条扑克unknown与13组A/B细节风险继续保留；CPU准备不能使它们自动通过。

新入口拒绝将准备输出写入旧study、v4/v5材料、intake或验收封存目录。正式运行还扫描其他study目录中同一冻结设计的fit_attempt，已有尝试时禁止通过新版本/新目录重置一次拟合预算；同目录续跑仍按冻结核心的attempt/metadata规则处理。

## 实际执行与结果

以下两条均已实际执行，exit0：

```sh
sh scripts/run_semantic_transfer_study_v5.sh --stage prepare
sh scripts/run_semantic_transfer_study_v5.sh --stage verify
```

verify由不同进程执行，PYTHONHASHSEED=59。只加载真实tokenizer，流式读取完整两分片权重计算SHA256，不反序列化模型或旧probe。

| 检查项 | 实际结果 |
| --- | --- |
| 材料规模 | 240条；训练/开发/评估96/48/96 |
| v5提示/输入token逐条对应 | 240/240与材料preflight一致 |
| 输入长度 | 341–3055 tokens，总323081 |
| 上下文与输出 | 32768上下文，单条128输出，总输出预算30720 |
| 与旧v4准备比较 | 83条提示改变、157条相同；82条token数改变，总输入减少171 |
| 实现/来源指纹 | 18/19 |
| 权重指纹 | 两分片完整SHA256，与旧准备结果完全相同 |
| 正式批准标签 | 240条全部null |
| 独立上下文审计收据 | 0 |
| GPU门禁 | false |

新准备目录只含protocol.json、review_gate.json、approved_labels.json、preflight.json四文件。批准文件和审核状态以后改变时必须新建对应就绪运行协议，不能向当前目录原地追加批准。

本轮还实际执行了新入口的`--stage run`，按预期exit1，错误为`Review gate closed: independent audited semantic labels are missing; model/probe loading forbidden`。检查发生在昂贵prepare、缓存访问、模型/probe加载之前，四个准备文件未变。这是冻结研究门禁的预期中止，不是GPU加载失败或工具自动批准审查拒绝；没有启动真实GPU推理。

## 测试和独立重放

最终28相关CPU测试通过，8.107秒：本轮6项新绑定测试、冻结核心原16项、验收原6项。新增覆盖保护目录拒绝、v4版本/错误修订快照拒绝、作者判断不能填正式标签、三个真实CLI推理/分析阶段在门禁前停止、跨版本一次拟合预算和旧默认/来源不变。原核心的合成流程继续覆盖144/96阶段对应的锁顺序逻辑、缓存/中断、临时CPU拟合和匿名行为导出等；这些使用小型合成材料、模拟模型和临时探针，不是本机3B GPU实验。旧53/120全套未重跑。

独立代码直接读取新旧preflight和v5原输入重建[240行桥接CSV](2026-10-21-semantic-transfer-study-v5-preparation-inputs.csv)，核对每条token/提示哈希、83/157及82计数、−171总差和240个null标签。两分片权重哈希、四个准备文件和[350旧路径保存清单](2026-10-21-semantic-transfer-study-v5-preparation-preserved.json)全部一致，旧材料/旧执行器/旧标签与上一轮验收封存均保留。

原始CPU日志和CSV另存runs/qwen2.5-3b-semantic-transfer-study-v5-preparation-audit-v1：prepare.log、verify.log、tests.log、run-gate.log、input_bridge240.csv。机器指标、源码、日志、新产物及保存清单哈希见[结构化记录](2026-10-21-semantic-transfer-study-v5-preparation.json)。

## 当前停止点

v5执行版本的CPU准备已经完成；独立语义标签仍0、语义覆盖0，原全体及各分区90%要求不变。现有两份空匿名包不是两次实际评分，作者验收也不会成为批准文件。用户暂无外部渠道，不反复询问、不用被AGENTS注入的新上下文冒充独立审核。

以后的实质条件仍是两份实际独立输入评分、完整接收上下文审计及显式批准。满足后另存就绪run，保持训练/开发144条→开发触发→最多一次train A拟合→评估锁→评估96条→语义与行为分开分析。L28/原生成设置不变，最多240回答，不扩大网格或消耗380保留题。新3B GPU路径仍未实测，真实行为评分导入仍需生成后另存对应分析。满预算可按历史容量预留30–120分钟，非本轮实测，长期GPU由用户启动；当前没有就绪GPU命令。

本轮正式模型/probe加载、GPU前向、回答、语义probe训练与干预均0；旧80.67%发布类别结果、no_qualified_baseline及既有行为结果不变。代码和记录保留工作区，未提交推送。

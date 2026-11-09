# 冻结probe：中性附注与冗余否定的等token长度对照

**后续状态（2026-11-09）：** 用户已运行并报告完成，13条前向及桥接通过核验；[逐题结果与来源归档](../2026-11-09-probe-neutral-control-results-v1/README.md)。下文“等待用户运行”与准备状态是采集前历史快照，现无须重跑。

2026-11-09。状态：**CPU准备完成，等待用户运行GPU；本目录没有新的probe结果。** 这项有限开发诊断直接针对[既有50单元结果](../../records/2026-10-20-probe-support-expression-verified.md)中无法分开“否定后缀”与“额外token”两个因素的问题。此前六个既定val底题在直接/改写两种表述上，添加冗余否定后conflict概率均上升，但每个完整提示同时增加20–28 tokens；本对照不将既有方向称为新发现。

## 固定设计

保留原6个已暴露底题、2种表达、问题、三个背景槽、两个目标核心及文档顺序；每个目标核心后分别追加同一中性格式附注，形成12条新输入。每条新输入与同底题同表达的已有否定版本在**完整chat提示token总数严格相等**，并复用该正面核心与否定版本的保存状态和冻结L28 probe概率。附注不同于否定句，不能把相同长度当作词汇、token位置、信息或语义完全相同；附注本身是新的格式信息，可能造成输入分布变化。作者知情检查不构成独立语义金标准。

| 既有底题 | D和P的中性附注（加到两个目标文档） | 新中性与既有否定完整prompt token数：D / P |
| --- | --- | --- |
| val_14 | Archive note: This record appears in a standard text format. | 605 / 617 |
| val_3 | Archive note: This is a standard text record. | 766 / 770 |
| val_31 | Archive note: This is a standard text record. | 2945 / 2948 |
| val_28 | Archive note: This entry is in standard text form. | 544 / 545 |
| val_17 | Archive note: A standard text record. It is a text entry. | 668 / 663 |
| val_13 | Archive note: A standard text record. It is a text entry. | 906 / 901 |

附注从有限候选中按真实token长度选择，未根据新probe输出筛选；但作者已知既有结果，不能称前瞻注册。主比较固定为每底题和表达的 **P(conflict)：既有否定 − 等长中性附注**，分别列D、P各6对及均值；D/P是同6底题的重复条件，不是12个独立底题。另报两种后缀分别相对原核心的三概率、类别及长度，不能推导这些新输入的回答行为。

若两种等长后缀的读出不同，说明仅以token总数不能完整解释该具体对照；相近也不能证明长度是原因。不同词语、格式、文本语义、token身份和位置仍混杂。结果属于单模型、六个已暴露val题的探索，不证明一般否定词机制、可靠语义解码、自然任务泛化或生成器因果使用；不扫描阈值、选层、重训或追加底题。

## CPU准备与运行边界

计划13次新decoder前向：先重算既有长输入 `support06_D1` 进行技术桥接，再运行12条中性附注；不调用生成头、不生成答案、不拟合。第1条的36层相对L2误差须≤0.02、冻结probe三概率最大差须≤0.01，失败立即停止。该单条桥接只能检查这一输入的运行一致性，不能保证其他输入逐位一致。

[固定协议](protocol.json)、[完整输入](materials/inputs.json)、[逐对材料和token身份](materials/comparisons.json)是待运行目录的逐字节归档。CPU准备重新验证旧协议、依赖、旧probe和24个核心/否定端点特征及预测；独立CPU脚本重建12对文本及完整chat token、核对24个旧特征SHA和3份归档副本，全部匹配。模型权重7个文件的完整SHA、GPU空闲、单可见设备及BF16由采集命令在用户启动时检查；准备阶段没有实时设备检查或模型前向。代码持有运行锁，逐条先写attempt再保存特征及记录；异常、未提交attempt或孤立文件会阻断，保留现场。

13条合计15,823输入tokens，最大2,948；按先前相同模型40条新前向中排除首条加载后的最大elapsed/token估算，提供2倍–10倍计算余量并加模型加载/IO约3–8分钟，得到约**4–9分钟容量规划**；源文件/模型权重哈希及实际排队可能额外耗时，建议预留**10–20分钟**，不是本次实测或保证。

## 用户运行

进入项目根目录后执行：

```sh
CUDA_VISIBLE_DEVICES=0 TOKENIZERS_PARALLELISM=false OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/probe_neutral_length_control_20261109.py --stage collect --operator user
```

运行前确认没有其他任务占用GPU。完成后把末尾输出交给助手，助手将先只读核验记录、桥接、源文件和12对统计，再解释结果。若中断或报错，请保留整个run和终端输出；助手先检查attempt及失败标记，不手工删除文件、不重跑未提交attempt。正常完成后重复命令只复验现有完成缓存，不再前向。

运行目录 `runs/qwen2.5-3b-probe-neutral-length-control-20261109-v1` 被Git忽略；本包归档固定材料，未包含用户将产生的新特征。旧E1不重跑，旧v1/E1-r1门禁false、正式独立批准0、正式标签null、原拟合预算0及380底题封存继续保持。

# 同题证据对照：开发小试验运行说明

本轮使用冻结Qwen2.5-3B-Instruct、已有chat自由回答模板及chat L28探针。目标是检查同题证据改变时，探针和实际行为是否随之变化。正式40条输入分别做自由回答和固定分类，共80条生成；另有4输入技术smoke、8条生成。材料/CPU准备及后续用户GPU运行均已完成，当前状态见下。

**2026-10-20当前状态：全部88次生成及正式40条显式行为复核、CPU分析/完整重放均已完成。** 正式末条于10月18日14:46:15保存，无空/截断，主表探针13/30、固定分类12/30；行为S有据正确10/10、I作答4/10（探针判不足后1/2）、C选边7/10，198字段确定/2已审歧义保留unknown。progress仍pending因两unknown，不表示40行仍空。评分来源有材料/历史暴露，非独立金标准。详见[行为复核](records/2026-10-20-controlled-evidence-pilot-behavior.md)和[生成核验](records/2026-10-20-controlled-evidence-pilot-verified.md)；**无需重跑下面的GPU入口**，下述准备快照和启动说明保留用于追溯。

2026-10-18准备与核验已完成：93项CPU测试52.405秒通过，正式40和smoke4真实tokenizer预检查及准备只读重放均通过，两目录prepared_not_started、新GPU0。最大自由输入2977、分类3289，分别加128/8低于32768；容量规划8–26分钟，保守预留10–30分钟。完整证据见[准备记录](records/2026-10-18-controlled-evidence-pilot-preparation.md)及[清单](records/2026-10-18-controlled-evidence-pilot-preparation.json)。

## 材料与评价口径

固定复用此前已审阅的10个验证开发底题，顺序为val_81、14、3、94、35、31、28、17、13、86。每题四配置：S充分、I缺一个必要前提、C同实体/时间/属性明确互斥、D仅无关信息改写。主表只用S/I/C共30条；D10条单列配对稳定性，避免重复充分类进入主分数。

每题统一澄清问题的范围/时间，写两篇短目标证据，保留原refuse配置中按字符数最短的三篇完整干扰文档（同长度按原槽位）。两目标槽位在十题中平衡，四条件固定同一位置和顺序。I从两篇目标中同步替换必要事实；C只改目标B；D只改目标A的档案位置、颜色或形状。所有替换与原题改编均有记录，原发布输入不改。

这是有历史暴露的当前作者制作的合成开发材料，既有探针的原val选层/校准也包含这些底题。明确互斥用语、短目标文本、问题改写、编辑数量及长度变化都可能影响结果；不是独立金标准、自然RAG测试或探针独立泛化评估，不把新材料上表现当原发布val候选达标。旧no_qualified_baseline与门槛不变，保留380底题不使用。

原始设计见[建议记录](records/2026-10-18-next-controlled-pilot-proposal.md)。显式材料在prompts/controlled_evidence_pilot_v1.json，生成/校验实现独立于旧冻结依赖。

## 用户启动与续跑

项目根目录执行：

```sh
sh scripts/run_controlled_evidence_pilot_review.sh
```

入口先运行固定最长文本底题val_31的四种配置：4自由回答、4分类。技术gate要求自由回答非空、EOS结束且未触及128token上限，分类4条均为完整标签+EOS。gate不检查语义成绩，不因预测错了而阻止正式，也不自动加提示或重试。smoke失败立即退出，终端打印最后30行日志；正式不会启动。正式入口会重新校验相同代码/材料/探针下的smoke缓存，不能靠单独伪写gate文件绕过。

通过后自动跑40自由回答+40固定semantic_rules分类；只加载一次模型，顺序执行。输出预算128/8，分类标签trie最长3token含EOS；BF16、SDPA、greedy。固定chat L28探针不重训、不重新校准；概率只是原校准映射在新分布上的读出，不能解释为已校准的新语义置信度。探针在prefill中、首个生成logits前计算，不反馈给生成器。

完整顺序任务建议预留10–30分钟；具体容量推算保存在preflight.json，来自旧chat汇总耗时、128token满预算和4倍余量，并非新GPU实测或完成保证。GPU争用另加；不能保证低于10分钟，按长期任务由用户启动。

GPU加载前会列出活动计算进程并拒绝继续，不停止其他任务。逐条原子保存，目录锁保护并发。中断后原样重跑上述命令；缓存身份/顺序、完整提示、输出、token/EOS、特征及探针概率验证通过才跳过。代码/材料/模型变化使用新run_dir/protocol，不改指纹绕过。

## 路径与进度

正式目录runs/qwen2.5-3b-controlled-evidence-pilot-v1/，smoke目录runs/qwen2.5-3b-controlled-evidence-pilot-smoke-v1/。

```sh
tail -f runs/qwen2.5-3b-controlled-evidence-pilot-v1/launch/smoke.log
```

正式启动后：

```sh
tail -f runs/qwen2.5-3b-controlled-evidence-pilot-v1/launch/full.log
```

| 文件 | 内容 |
| --- | --- |
| protocol.json | 材料/实现/旧探针/模型来源指纹、固定设置、开发暴露与边界 |
| materials/inputs.json、input_review.html | 40条完整五文档与可直接阅读全文的页面 |
| materials/input_judgments.json、review_seal.json | 显式逐条理由、必要/缺失事实、冲突双方、引文及生成前封存 |
| materials/edit_provenance.json | 原题/新题、完整来源文档槽、每个Unicode改写偏移 |
| preflight.json | 真实tokenizer输入长度、每条件长度差、预算/上下文、容量估时 |
| progress.json、last_failure.json | 当前阶段和失败记录；历史失败不等于当前仍失败 |
| free_answer/predictions.json、features/ | 原始回答/token/EOS、生成前探针概率、FP16的36×2048状态及哈希 |
| classification/predictions.json | 固定semantic_rules标签对照；没有提示候选搜索 |
| reports/pilot.json、pilot.md | 主30条、D10条、每题概率变化、行为上下界 |
| review/blind_review.html、annotations_template.csv | 生成后导出行为审核页和空白评分模板，隐藏显式类别与探针结果 |

## CPU检查与生成后核验

以下只做准备/检查，不加载3B模型或启动GPU：

```sh
sh scripts/run_controlled_evidence_pilot.sh --stage check
sh scripts/run_controlled_evidence_pilot.sh --stage check --smoke --run_dir runs/qwen2.5-3b-controlled-evidence-pilot-smoke-v1
```

准备状态的独立只读重放：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_controlled_evidence_pilot.py --prepared_only
```

GPU生成并导出报告后，助手进行完整只读核验：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_controlled_evidence_pilot.py
```

同脚本可用--run_dir指定smoke目录。核验重建材料、协议、真实输入长度和所有缓存/特征/概率，复算主表/配对/完整分母，独立重导审核页面到临时目录比较，不修改原产物。

## 行为评分与后续分析

本轮已使用显式评分路径review/assistant-behavior-2026-10-20-v1/annotations.csv完成分析，原模板保留；若重放，使用同一--annotations路径，勿仅执行默认analyze导致切回不存在的根annotations.csv。当前只读复查可执行`python -B scripts/verify_controlled_evidence_behavior_review.py`（使用上方kba-rag绝对Python），不需再次分析或生成。以下为原通用流程说明。

GPU生成完成后，行为仍待显式审核；分类标签、关键词和探针预测不自动生成评分。沿用has_substantive_answer、acknowledges_insufficiency、acknowledges_conflict、selects_single_answer、answer_correct五字段，yes/no/unknown，未明确项保留完整分母。当前作者熟悉材料，若由其继续判断须披露来源，不称独立盲审。

用户无需现在填写表格。生成后可由助手直接复核并另存已填副本；评分文件须显式放到新run的annotations.csv，或给--annotations路径，然后CPU执行：

```sh
sh scripts/run_controlled_evidence_pilot.sh --stage analyze
```

分析会保留旧报告快照及已消费评分副本，原空白模板不覆盖。报告单列主30的不足作答/探针判不足后作答、冲突选边/报告冲突、充分有据回答与拒答；D10单列S→D探针类别/概率变化和已评分行为不变性。未评分时点估计null并给上下界，不把空/截断当拒答。十底题只做开发诊断，不外推总体、追认旧基线或自动开启确认/patching。

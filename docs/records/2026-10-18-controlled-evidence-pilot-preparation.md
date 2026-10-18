# 2026-10-18：同题证据对照材料、实现与全部CPU准备完成

记录日期与时区：2026-10-18，Asia/Shanghai。
状态：prepared_verified_not_started；正式40输入/80生成、smoke4输入/8生成均新GPU输出0。
操作者：助手；用户明确要求除长期GPU之外其余工作现在全部完成。

## 目标与固定设计

接续[试验建议](2026-10-18-next-controlled-pilot-proposal.md)，完成可审阅材料、显式判断/来源、独立代码、冻结协议、CPU测试与预检查、估时及启动/续跑入口。研究定位见[原理与问题](2026-10-18-research-framing.md)，原无合格分类基线不追认，未使用保留380底题。

固定沿用已暴露的十个验证开发底题val_81/14/3/94/35/31/28/17/13/86。每题统一问题，再制作S充分/I缺必要前提/C明确相关互斥/D无关改写四配置。正式40条独立于原发布数据；主表S/I/C各10共30，D10单列不变性，不重复计入主分类分数。

## 已完成材料与语义阅读

prompts/controlled_evidence_pilot_v1.json保存逐项手写问题、两篇支持目标、缺证替换、互斥替换、无关替换、必要事实、答案/缺失前提、四条件判断理由。四道宽泛类别题已限定为dog/cat、magazine/newspaper、mountain/plateau、novel/play；其他题明确事件时间、单事件、唯一音乐署名或个人排名范围。改题统一应用于同题四条件，不改旧题/旧判断。

每题保留其原refuse配置按字符数最短的三篇完整文档（同长度按原槽位），另写两篇目标证据。十题遍历全部十种目标槽位组合，每槽出现4次；四条件固定同一槽位及顺序。I同时替换两目标的同一必要前提，C只替换目标B，D只改目标A的无关档案位置/颜色/形状。

当前作者已逐项阅读所用30个完整来源文档槽、全部手写替换及生成后四条件映射；完整200文档槽可复用相同全文阅读，共89篇不同文本，另核对40条最终问题。40条显式输入判断（20充分/10不足/10冲突）、60逐字引文/偏移与十题每处Unicode改写偏移已校验；全文页面可直接审阅。体育题C还引入同一目标文档内部的事件运动互斥，已在理由中披露，并未强制只认跨文档矛盾。

这是当前有历史/模型输出暴露的作者制作的合成开发材料，不是独立评分或现实事实认证。WWW公开可用日期等目标可为刻意反事实值；旧探针原val选层与校准也包含这十底题，不能称独立泛化评估。显式互斥、短目标、问题澄清、两目标重复及新措辞与原分布不同。I改变两段、C/D改变一段，编辑量没有完全匹配；长度影响仍可能存在，不能由这轮直接认定神经机制或纯语义效应。

## 实现与运行约定

新增controlled_evidence_materials.py、controlled_evidence_pilot.py、verify_controlled_evidence_pilot.py、两个sh入口及10项测试；不修改旧冻结模块。固定Qwen2.5-3B-Instruct/BF16/SDPA/greedy、chat原自由回答指令/128token和旧chat L28探针，冻结标准化器/路由器，不训练、不校准、不调阈值。探针在首次prefill内、首个生成logits前计算，不反馈给生成器。另以固定semantic_rules/8token/标签trie作分类对照，不再搜索候选。

每条保存身份/条件/来源、完整提示哈希、原始回答/token/EOS/截断、36×2048 FP16状态及哈希、预生成探针类别与概率。读取缓存重放来源/顺序/文本/token/输入长度/EOS/特征/概率，拒绝损坏与补零；每条原子保存并用run lock防并发。探针概率是旧校准映射在新分布的输出，不称新的校准置信度。

技术smoke固定最长文本底题val_31的四条件、4自由+4分类；自由非空/EOS/无截断且分类4合法才过gate，无语义分数门槛。入口通过后自动40自由+40分类；正式推理还会重验同设置smoke协议及完整缓存，不靠gate文件单独放行。GPU活动计算进程存在时拒绝加载，保留PID/进程/显存信息，不停止其他任务。失败输出最后30行日志，模型加载/行级失败写last_failure，原样重跑验证后续接。

生成后导出隐藏显式类别/探针的行为页面与原五字段空白CSV。标签、关键词和探针不自动产生行为评分；unknown保留完整分母和上下界。S/I/C主表、D控制、每题概率变化/已评分行为不变性分开。显式评分后重分析会保留旧报告及字节一致的消费评分副本（含CRLF）；空白模板不覆盖。当前用户无需填写空表，生成后可由助手按披露来源另存判断。

## 实际检查与产物

最终全套已执行：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B -m unittest discover -s tests
```

**93项全部通过，52.405秒**，包含新10项。覆盖四条件与目标槽平衡、全部引用/Unicode变更重放、来源/编辑篡改、模型输入完整保留和元数据隔离、主30/控制10/unknown分母、技术而非语义gate、缓存文本/token/条件/特征/概率篡改、GPU忙/未smoke阻止正式、smoke失败阻止full、小型CPU Qwen真实生成前钩子时序、真实本地tokenizer/旧探针的临时合成smoke→审核/报告→独立重放→无模型缓存续跑→评分历史快照及CRLF保留。合成输出与小型随机CPU模型不属于本机3B GPU实验。

开发中一次CPU临时集成重放在测试期间修改核验脚本后触发实现指纹保护而失败；停止修改依赖后，最终完整版本93项通过。正式两run仅用最终实现做CPU准备，没有旧代码GPU输出；未改指纹绕过。

两个sh语法和git diff --check通过。实际执行正式与smoke check，以及两次prepared_only只读重放均通过：

```sh
sh scripts/run_controlled_evidence_pilot.sh --stage check
sh scripts/run_controlled_evidence_pilot.sh --stage check --smoke --run_dir runs/qwen2.5-3b-controlled-evidence-pilot-smoke-v1
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_controlled_evidence_pilot.py --prepared_only
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_controlled_evidence_pilot.py --prepared_only --run_dir runs/qwen2.5-3b-controlled-evidence-pilot-smoke-v1
```

| 真实tokenizer检查 | 正式40 | smoke4 |
| --- | ---: | ---: |
| 自由回答最大输入 | 2977 | 2977 |
| 自由回答平均输入 | 1178.80 | 2968.50 |
| 分类最大输入 | 3289 | 3289 |
| 分类平均输入 | 1490.80 | 3280.50 |

分别加128/8输出，均小于32768；两任务实际最长均val_31。I−S自由输入差−21至0token，C−S为0至+11，D−S全部0；字符长度仍有变化，明细在preflight。两run各18实现/提示指纹、5旧探针来源哈希及完整模型规格/权重文件统计绑定。准备只读重放未读取大激活数组或加载3B模型。

正式protocol SHA256：98650b290d29779242cb4727e43a1625d5fe187bae275c9ed2fb8bdf445baf6f。

smoke protocol SHA256：ca8c52a01df554d88d0fd9164d0ea966309a7dedb19262156c1fd54a7e9c8e52。

两目录均prepared_not_started，预测文件不存在、GPU新输出0。旧两语义分类run的全部代码/提示指纹仍匹配，没有修改旧依赖/协议/原始输出。未查宿主实时GPU、未启动新3B推理或确认集。

## 时间估算、用户入口与下一步

历史chat汇总为300条、650.30秒、平均42.13输出token，仅用于容量参考，不读取原test行/预测。按44条自由满128预算、44分类最长3token、4倍余量及加载/IO，preflight给完整smoke+正式8–26分钟；保守建议预留**10–30分钟**，非新实测或完成承诺，争用另加。不能保证低于10分钟，按约定交用户启动。

```sh
sh scripts/run_controlled_evidence_pilot_review.sh
```

正式目录runs/qwen2.5-3b-controlled-evidence-pilot-v1/，smoke目录runs/qwen2.5-3b-controlled-evidence-pilot-smoke-v1/；日志正式目录launch/smoke.log、full.log。中断原样重跑；不要改运行依赖或另起同GPU任务。完成后助手完整只读核验、逐项行为判断与分析，无需用户现在填表。

详细文件/审核/命令说明见[运行文档](../controlled_evidence_pilot.md)。[准备清单](2026-10-18-controlled-evidence-pilot-preparation.json)、[40显式输入判断](2026-10-18-controlled-evidence-pilot-input-judgments.json)、[来源与改写偏移](2026-10-18-controlled-evidence-pilot-edit-provenance.json)保存轻量持久副本；全40原文留新run的materials/input_review.html及inputs.json。

## 维护与边界

本轮授权的非长期GPU准备已经完成；余下实际GPU与其后依赖输出的行为审核待进行。同步AGENTS、索引、activity_log；本轮无新实验指标，不向experiments.csv登记进行中结果。不覆盖历史建议、旧标签或评分，不自动提交推送。

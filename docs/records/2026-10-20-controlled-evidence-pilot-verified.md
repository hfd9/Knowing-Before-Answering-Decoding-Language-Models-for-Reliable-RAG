# 2026-10-20：同题证据对照生成完成与只读核验

记录日期与时区：2026-10-20，Asia/Shanghai；精确检查时间见同名JSON。
状态：generation_complete / generation_and_report_verified_behavior_pending。
操作者：用户于10月18日启动GPU；助手本轮实际执行CPU只读核验及独立计数。

## 目标与实际操作

用户要求检查上次代码是否跑完。承接[准备记录](2026-10-18-controlled-evidence-pilot-preparation.md)和[运行快照](2026-10-18-controlled-evidence-pilot-running-submission.md)，读取正式/smoke进度、末尾日志和保存报告，执行以下两条命令，均exit 0：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_controlled_evidence_pilot.py
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_controlled_evidence_pilot.py --run_dir runs/qwen2.5-3b-controlled-evidence-pilot-smoke-v1
```

使用冻结Qwen2.5-3B-Instruct、chat自由回答128token、固定semantic_rules分类8token预算与原chat L28探针；不重训或校准。正式目录runs/qwen2.5-3b-controlled-evidence-pilot-v1，smoke目录runs/qwen2.5-3b-controlled-evidence-pilot-smoke-v1。

只读重建材料、输入封存、协议、真实tokenizer预检查、完整提示、输出token/EOS、特征哈希/形状、探针概率及报告；审核页和空白模板在临时目录重导后逐字节比较。另直接从两组保存records独立计数，复核主表正确数、逐条件分布、同题概率方向、D控制类别稳定性和完成时间；证据及文件哈希另存[JSON](2026-10-20-controlled-evidence-pilot-verified.json)。未启动模型或新GPU，不修改冻结实现、协议、材料、预测、原报告或空白行为模板。本轮不增加行为评分，也不重复已通过的93项CPU测试。

## 完成证据

- 正式40自由回答+40分类，smoke4+4，共88次保存生成；两份progress均analysis_complete_behavior_pending。正式日志以classification [40/40]和Analysis complete正常结束；两目录均无last_failure.json。
- 正式最后自由回答于2026-10-18 **14:46:04.546490**保存，最后分类于**14:46:15.200661**保存；smoke最后分类14:44:23.292781。均为输出completed_at换算北京时间，不把文件mtime当实际运行时间。
- 正式自由回答40条、smoke4条均非空、EOS结束、未触及128token上限；正式自由回答含EOS长度21–103token。分类44条均技术合法、严格格式通过、EOS结束且未触及预算，长度2–3token。
- 40+4个FP16状态数组及缓存探针读出通过重放；所有保存记录均标记生成首token前读出，固定层28。两run各18实现/提示指纹、5探针来源哈希匹配。
- 正式协议SHA256：98650b290d29779242cb4727e43a1625d5fe187bae275c9ed2fb8bdf445baf6f；smoke：ca8c52a01df554d88d0fd9164d0ea966309a7dedb19262156c1fd54a7e9c8e52。
- 两个核验器返回verified_complete指**保存产物与报告重放成功**；不代表行为审核完成、语义正确或基线达标。

## 已核验的开发分类结果

主表仅S/I/C三条件共30条，D10条不计入主准确率。下表“判对”仅指与生成前显式作者设计类别一致：

| 条件 | 条数 | 冻结探针判对 | 固定分类提示判对 |
| --- | ---: | ---: | ---: |
| S：充分 | 10 | 1 | 4 |
| I：不足 | 10 | 2 | 8 |
| C：明确冲突 | 10 | 10 | 0 |
| 主表合计 | 30 | 13（43.33%） | 12（40.00%） |

探针Macro-F1 35.29%，固定分类32.35%。探针把S的9/10和I的6/10也判为冲突，主表共25/30预测conflict；因此C召回10/10不能单独说明其可靠地区分冲突。固定分类将10个C全部判refuse，从未预测conflict。I→answer两方法均2/10；这些都是分类判断，不能等同实际缺证作答。

同题配对方面，I的refuse概率相对S在10/10题增加，C的conflict概率相对S在10/10题增加；但完整类别转换S=answer→I=refuse为0/10、S=answer→C=conflict仅1/10。D无关改写的探针类别和固定分类类别均10/10与S相同；概率并非完全不变，原报告逐题保留变化。类别稳定性不表示实际回答行为稳定。

## 解释边界与未完成项

正式40条行为五字段仍全部未评分，annotations.csv不存在、annotation_sha256为null；unknown_behavior_rows=40。smoke另4条未评分。当前缺证后作答、冲突选边、正确有据回答及S/D行为不变性的点估计仍null，上下界保留完整分母；不能把未评分项算拒答。

材料由有历史暴露的当前作者改写，旧probe曾在这些底题所在val选层/校准；新分布概率未重新校准。问题改写、目标文本简化及长度/编辑量差异可能影响读出。本轮只说明该冻结设置在这些合成开发材料上的结果；不是独立金标准、自然RAG泛化或确认成绩，也不是隐藏状态因果机制证明。旧no_qualified_baseline不变，380保留底题未使用，未patching。

下一步无需重跑GPU：按原问题、完整证据与自由回答逐条显式复核40条行为，披露同助手/材料暴露来源，另存已填评分副本并保留原空白模板，再CPU分析和只读重放；不从分类标签、探针结果或关键词自动产生行为标签。

## 记录维护

新增本记录和JSON，更新AGENTS、索引、活动日志及运行说明的当前状态；历史准备/运行快照保持原样。行为尚未审核，不将本轮登记为完整行为实验到experiments.csv。上一轮提交e0094c60bfb5343ffd006aa8ece33ea3a3cca857及推送核验已在会话完成，本轮初始HEAD仍为该提交；本次检查未提交或推送。

# 2026-10-18：代码推送完成，新语义分类完整核验与失败诊断

记录日期与时区：2026-10-18，Asia/Shanghai。
状态：verified_complete（技术重放与已有判断对照）；没有新增独立语义评分。
操作者：用户启动此前GPU生成；助手按本轮授权先提交推送，再执行CPU核验与分析。

## 目标与背景

接续[背景恢复](2026-10-18-context-restored.md)与[代码归档](2026-10-18-code-submission.md)，完成正式570条/smoke18条完整重放、逐类与配对比较，并对齐已完成的30条开发语义判断。用户无需重新填写同一批表。

## 提交与远端核验

- 此前全部代码/测试/提示/配套记录已提交：65a3f26ee385e41fef77124494a1d33556cda28c，73文件、8539行新增/10行删除。提交前79项CPU测试通过，10.895秒；新增JSON解析、shell语法与git diff --check通过。
- 实际执行git push origin main成功，随后git ls-remote origin refs/heads/main返回同一完整哈希；推送后工作区干净，再开始本轮新核验/分析。
- git add首次因.git只读失败，按授权获得沙箱外索引写入许可后成功；push首次因沙箱DNS失败，获沙箱外网络许可后成功。没有force push、修改认证配置或发布凭据。
- 本记录及新分析代码/结果是在65a3f26推送之后产生，当前保留为后续本地改动；不要把其误称为已经包含在该远端提交。

## 实际命令与技术核验

以下两条均已执行并成功，输出分别保存为[正式重放JSON](2026-10-18-classification-semantic-baseline-full-replay.json)与[smoke重放JSON](2026-10-18-classification-semantic-baseline-smoke-replay.json)：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_classification_semantic_baseline.py --output docs/records/2026-10-18-classification-semantic-baseline-full-replay.json
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_classification_semantic_baseline.py --run_dir runs/qwen2.5-3b-classification-semantic-smoke-v1 --output docs/records/2026-10-18-classification-semantic-baseline-smoke-replay.json
```

完整重建协议、来源、13份代码/提示指纹、运行版本、tokenizer输入长度、原生完整提示、逐条身份顺序、输出哈希、token/text/EOS/解析与8token预算、旧chat8对照、30条辅助判断来源及报告。正式570条、smoke18条完整；三组各10000次、seed42、按95底题保留三配置的配对bootstrap与保存报告逐字段相同。smoke技术9/9×2通过，不作语义筛选。旧报告与预测均未覆写。

新增独立标准库计数脚本scripts/analyze_classification_semantic_failure.py，不修改冻结推理依赖。实际执行默认入口，在新目录runs/qwen2.5-3b-classification-semantic-postanalysis-2026-10-18-v2/生成summary.json、cases.csv、report.md与manifest.json；连续运行两次逐字节一致。独立复算285条及29确定开发输入的混淆矩阵、P/R/F1、错误可答率与配对翻转，均与已重放报告相符。14个源文件分析前后哈希相同，50条旧引文逐字验证并保存字符偏移。

新增4项测试覆盖invalid完整分母/F1/FAR、unknown隔离/重复或错位ID、配对方向及错到错、已有产物保护含CSV CRLF。最终全套83项CPU测试通过，10.380秒。首次新分析v1导出完成但重复运行时CSV换行归一化导致误判不同而拒绝覆写；修正为字节比较后另存v2，原v1及实现快照保留。此为新导出工具问题，没有改旧模型结果。

## 发布类别结果与预设门槛

两候选模型/输入/解码沿用冻结protocol，不新增推理；每类95条。全部严格格式100%、invalid/空输出/触及输出上限均0。预测顺序均answer/refuse/conflict/invalid：

| 方法 | 正确/285 | Accuracy | Macro-F1 | 输出answer/refuse/conflict | 分类错误可答 |
| --- | ---: | ---: | ---: | --- | ---: |
| legacy_chat8 | 114 | 40.00% | 28.03% | 39/246/0 | 20/190=10.53% |
| semantic_rules | 118 | 41.40% | 30.57% | 53/230/2 | 31/190=16.32% |
| semantic_examples | 106 | 37.19% | 24.13% | 19/265/1 | 9/190=4.74% |

| 方法 | 发布answer→answer/refuse/conflict | 发布refuse→answer/refuse/conflict | 发布conflict→answer/refuse/conflict |
| --- | --- | --- | --- |
| legacy_chat8 | 19/76/0 | 0/95/0 | 20/75/0 |
| semantic_rules | 22/73/0 | 1/94/0 | 30/63/2 |
| semantic_examples | 10/85/0 | 0/95/0 | 9/85/1 |

充分/不足/冲突召回分别为旧20.00/100.00/0%、rules23.16/98.95/2.11%、examples10.53/100.00/1.05%。两组充分和冲突均未达60%预设门槛；其他门槛通过不能补偿，eligible=[]、selected=null、no_qualified_baseline不变。rules仅是诊断最高分，不是入选基线。

## 配对变化：规则微增正确伴随更多错误可答，示例更偏refuse

以下均为左减右，百分点及95%底题配对区间；不是新独立确认结果，也未包含训练随机性或多重比较校正。

| 对照 | Accuracy差 [95%区间] | Macro-F1差 [95%区间] | 分类错误可答率差 [95%区间] |
| --- | --- | --- | --- |
| rules−legacy | +1.40 [−1.40,+4.21] | +2.54 [−1.20,+6.38] | +5.79 [+2.11,+9.47] |
| examples−legacy | −2.81 [−5.26,−0.35] | −3.89 [−7.77,−0.05] | −5.79 [−9.47,−2.11] |
| examples−rules | −4.21 [−7.02,−1.75] | −6.43 [−10.19,−2.88] | −11.58 [−16.32,−7.37] |

rules对旧：10条由错变对（8充分、2冲突）、6条由对变错（5充分、1不足），净+4。充分召回净+3/95，冲突仅新增val_37_conflict/val_83_conflict两条，发布conflict→answer由20增30，不足→answer由0增1。12条原refuse预测在发布conflict上变answer，仅2条反向变refuse；这解释错误可答净增10条，不等于新增的answer都语义错误。

examples对旧：3条由错变对、11条由对变错，净−8；对rules为2改善/14退步，净−12。输出refuse达265/285=92.98%，充分召回下降；错误可答减少同时大量充分/冲突也判refuse，不能据此称可靠三分类改善。旧新对照同时改变指令/解码，不能分离提示效应；examples与rules共用解码，但也同时改变示例内容和输入长度，不能声称已识别内部机制。

## 30条开发输入对照与可观察失败

本轮复用10月16日明确判断12充分/13不足/4冲突/1unknown，全部已参与开发且有历史暴露；非独立/人工金标准，不新增评分或改发布标签。完整30条见[对照CSV](2026-10-18-classification-semantic-baseline-development.csv)及run目录逐条理由/引文。

| 方法 | 充分一致 | 不足一致 | 冲突一致 | 总一致（排除1unknown） |
| --- | ---: | ---: | ---: | ---: |
| legacy_chat8 | 2/12 | 13/13 | 0/4 | 15/29 |
| semantic_rules | 3/12 | 13/13 | 0/4 | 16/29 |
| semantic_examples | 0/12 | 13/13 | 0/4 | 13/29 |

examples在全30条均输出refuse，其13/29完全来自不足一致。rules在全30为5answer/25refuse；比旧新增P005充分杂志题、P024按直接三人关系判断可答，失去P013兼容类别题，净+1；high23子集旧/rules均13/23、examples11/23，仅事后敏感性，不能作独立性能或挑选门槛。

可观察错误类型已逐条保存，以下使用既有判断的题意与保留条件，而不推测模型内部理由：

- **明确支持仍判不足：** P011/val_3_answer，文档1直接称Tucson与El Paso分别为public，joint civil-military不否认public；两新组均refuse。P019/val_31_answer直接给Billy Elliot的music by Elton John，两组也refuse。这类错误不依赖发布conflict是否错标。
- **同一时点相关矛盾漏判：** P001/val_86_conflict，两篇均2018年6月，却把Selena个人排名写成第一/第二，rules/examples均refuse。P009/val_81_conflict的同日期德国总统辞职报道主体不同，rules为answer、examples为refuse。不能只用偏保守概括所有冲突失败，rules还存在将冲突判可答。
- **兼容表述仍未转为有据可答：** P012/val_3_conflict的public与international、P013/val_28_conflict的magazine与print publication、P014/val_14_conflict的dog与mammal，按已有判断兼容，两组均refuse。没有预测conflict也不意味着正确识别了兼容关系。
- **确实缺证的配置仍一致判不足：** 原13条语义不足，两组均13/13，包括所问available日期不能由inception替代、只出现snooker赛事却缺三个指定人物关系。不能把所有refuse都称错误拒答。
- **unknown保持隔离：** P008/val_31_conflict存在竞争但不明确排他的音乐署名；rules=answer、examples=refuse，仅展示，不计入29确定分母，也不替换原unknown。P004、P024、P025等既有moderate题意条件继续保留。

本轮额外全文重读四条（val_86_conflict、val_13_conflict、val_3_answer、val_28_answer）的全部20文档槽，与已有相关引文一致；没有声称重新独立阅读全文285条或全部30条。其余逐项判断来源是已完成复核，程序引用匹配也不认证蕴含或语义真值。四条确定冲突中两条high、两条moderate，均漏判；现象并非仅因moderate案例。

## 结论、限制与下一步

完成了“完整核验—逐类比较—30条开发诊断对照”三项任务。当前新规则未建立可靠基线；在已有开发判断下也同时有充分漏判和明确冲突漏判。格式/缓存/截断已排查，发布标签质量仍限制全285解释，却不能解释全部错误。

本轮只能定位行为失配，不能回答内部为何不输出conflict。输出只有类别，没有证据选择或推理轨迹；token trie是逐token受约束greedy，不是三个完整标签的似然比较。未比较的标签竞争、指令复杂度、证据整合困难均只能列为待检验假设，不据当前结果定因。后续若继续实验，优先预先固定同提示/同输入的读取方式对照，以分离分类解码选择与语义辨别，避免继续同时叠加多种规则与示例；这尚未实现或启动，不承诺能改善结果。

仍只用val，30条只作开发；剩余380底题未用，暂不确认或patching，不改阈值、原标签、旧报告或既有评分。新GPU必须新协议/目录、预检查、估时并按长期任务约定交用户启动。

## 产物与维护

结构化指标、配对翻转和来源哈希见[持久JSON](2026-10-18-classification-semantic-baseline-verified.json)；该文件单列两份完整重放与新分析来源，原始生成留runs。同步AGENTS、索引、activity_log和两条已核验val实验登记；test指标列留空，不用val冒充test。后续新文件尚未提交推送。

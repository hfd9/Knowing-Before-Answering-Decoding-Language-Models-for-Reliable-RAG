# 实验与动作记录索引

这个目录保存项目的持久实验记录、操作记录和交接快照。
新会话先读根目录 [AGENTS.md](../../AGENTS.md)，再读本索引和最新交接记录；无需一次性加载所有 JSON。
最新背景恢复：[2026-10-18-context-restored.md](2026-10-18-context-restored.md)（正式v4的600行/132未知与哈希一致；新分类正式570+smoke18已保存analysis_complete，26份代码指纹匹配，报告仍no_qualified_baseline；本轮仅轻量核对，完整指标/缓存/bootstrap重放待做，无新GPU）。
最新研究定位：[原方法与我们的问题](2026-10-18-research-framing.md)（核对原论文与原代码；原论文已有生成级patching，自由生成/替换本身不能当新增贡献。当前主线具体化为发布类别与语义有效性、生成前读出与实际行为失配、后续因果使用，区分已探索与待确认；无新实验）。
最新受控试验准备：[40正式+4smoke材料/代码/CPU全部完成](2026-10-18-controlled-evidence-pilot-preparation.md) / [JSON](2026-10-18-controlled-evidence-pilot-preparation.json) / [40显式输入判断](2026-10-18-controlled-evidence-pilot-input-judgments.json) / [改写偏移](2026-10-18-controlled-evidence-pilot-edit-provenance.json)（用户授权除长期GPU外完成；200槽/89全文/60引文，93CPU52.405秒，真实tokenizer与两次准备重放通过；40自由+40分类、4+4smoke，18指纹，GPU0；用户入口sh scripts/run_controlled_evidence_pilot_review.sh，保守10–30分钟。[运行说明](../controlled_evidence_pilot.md)。有暴露合成开发，主30/控制10分开、旧门槛不变）。[先前建议](2026-10-18-next-controlled-pilot-proposal.md)保留历史。
最新受控试验运行：[14:45:34快照与授权归档](2026-10-18-controlled-evidence-pilot-running-submission.md) / [JSON](2026-10-18-controlled-evidence-pilot-running-submission.json)（用户已启动；smoke4+4技术通过，正式自由24/40、分类0，18实现/5探针来源匹配；不改运行依赖或重启，不提前登记最终成绩）。
最新分类核验与诊断：[正式570+smoke18完整重放](2026-10-18-classification-semantic-baseline-verified.md) / [JSON](2026-10-18-classification-semantic-baseline-verified.json) / [30条CSV](2026-10-18-classification-semantic-baseline-development.csv)（协议/缓存/提示/token/EOS/指标/三组bootstrap一致；rules118/285、examples106/285，仍无合格候选。旧30判断复用，16/29与13/29非独立准确率；新分析v2幂等与全83测试通过，无新GPU）。[正式重放](2026-10-18-classification-semantic-baseline-full-replay.json)与[smoke重放](2026-10-18-classification-semantic-baseline-smoke-replay.json)另存。
此前分类准备：[两组语义规则分类候选](2026-10-16-classification-semantic-baseline-preparation.md)及[清单](2026-10-16-classification-semantic-baseline-preparation.json)保留当时0输出与79CPU检查快照；用户已运行完成，无需重启入口。
历史运行快照：[新分类持续推进](2026-10-16-classification-semantic-baseline-running.md)及[JSON](2026-10-16-classification-semantic-baseline-running.json)保留20:33:27的227/285，当前以10月18日完整核验为准。
最新追加判断：[当前助手完成全30条](2026-10-16-validation-semantic-followup.md)（用户要求直接判断；12充分/13不足/4冲突/1unknown、50引文/已填CSV/封存核验通过，P004与P025题意解释明确后改为answer/refuse，其余28模式不变。相对本轮v4一致7/29，非独立准确率；同助手追加复核30完成，独立新评分0，原判断和模板保留）。
最新语义诊断：[30条固定val复核与归因](2026-10-16-validation-semantic-pilot.md)（用户要求前三步直接完成；seed42固定10底题/30条，完整原文判断先封存，11充分/12不足/4冲突/3未知；27确定中v4类别一致7、不一致18、技术invalid2，30手工归因/54引文校验与3项流程测试完成。当前助手有背景/部分日志暴露，非独立金标准，不导入旧标签）。
最新导出核验：[CPU诊断报告与空白复核包正式完成](2026-10-16-validation-semantic-diagnosis-verified.md)及[JSON](2026-10-16-validation-semantic-diagnosis-verified.json)（用户运行、10文件哈希/全部内容重放/原始来源通过；30行空白、7优先项，新独立评分0条。下一步填写新评分副本，无需重跑GPU）。[代码准备](2026-10-16-validation-semantic-diagnosis-preparation.md)保留当时快照。
最新完成与根因核验：[v4生成完成与测试设计审计](2026-10-16-validation-evidence-audit-v4-verified.md)及[JSON](2026-10-16-validation-evidence-audit-v4-verified.json)（用户完成285正式+9smoke，17指纹/两阶段缓存/独立计数核验通过；正式277结构合法、43合法unknown+8截断，与发布标签一致100/285，非语义准确率；已见无关引用/假冲突，下一步语义复核而非自动新GPU）。[v3失败与v4准备](2026-10-16-validation-evidence-audit-v3-failure-v4-preparation.md)及更早版本保留历史。
最新版本归档：[本轮受控试验代码与记录](2026-10-18-controlled-evidence-pilot-running-submission.md)（用户授权将65a3f26之后的分析/研究定位/受控试验代码、测试、材料和记录提交推送；提交标识以该记录所在提交为准，实际远端核验在本轮回复报告）。此前[65a3f26归档](2026-10-18-code-submission.md)与[10月13日归档](2026-10-13-code-submission.md)保留历史。
当前研究结论综合：[2026-10-12-research-conclusions.md](2026-10-12-research-conclusions.md)（生成前发布类别可解码、实际行为失配，冲突更普遍；提示词基线未合格，语义质量与非独立人工评分限制，确认/因果未完成）。
最新动作：[2026-10-12验证集新提示词完成核验](2026-10-12-classification-prompt-validation-verified.md)（用户启动，855正式+27smoke生成/分析/核验完成；三候选均未达预设门槛，no_qualified_baseline，未使用test或确认集）。最新行为交接：[第二评分与v4裁定](2026-10-12-semantic-review-adjudication.md)（300第二输入、232第二行为+2协调补评，148分歧字段裁定完成，正式v4已核验，132未知保留）。当天更早的准备/恢复及旧0评分均为历史快照。四条件分类核验：[2026-10-11-classification-grid-verified.md](2026-10-11-classification-grid-verified.md)。生成完整核验：[2026-10-09-free-answer-generation-verified.md](2026-10-09-free-answer-generation-verified.md)。
背景交接：[2026-10-09-project-context-and-records.md](2026-10-09-project-context-and-records.md)；10 月 11 日恢复与中断检查记录为首轮审核完成前的历史快照。

## 记录列表

| 日期 | 文件 | 内容与状态 |
| --- | --- | --- |
| 2026-10-18 | [controlled-evidence-pilot-running-submission.md](2026-10-18-controlled-evidence-pilot-running-submission.md) / [JSON](2026-10-18-controlled-evidence-pilot-running-submission.json) | 14:45:34 smoke4+4技术通过、正式自由24/40分类0，运行指纹匹配；用户授权归档全部当前修改并推送，提交前只读检查 |
| 2026-10-18 | [controlled-evidence-pilot-preparation.md](2026-10-18-controlled-evidence-pilot-preparation.md) / [JSON](2026-10-18-controlled-evidence-pilot-preparation.json) / [判断](2026-10-18-controlled-evidence-pilot-input-judgments.json) / [偏移](2026-10-18-controlled-evidence-pilot-edit-provenance.json) | 40输入/4smoke、200文档槽/89全文/60引用，固定chat L28与分类对照，93CPU及两目录只读准备核验完成；GPU0，由用户启动完整10–30分钟任务 |
| 2026-10-18 | [next-controlled-pilot-proposal.md](2026-10-18-next-controlled-pilot-proposal.md) | 用户询问下一步；拟准备40条同题证据对照，优先测语义变化/探针/行为，冻结前仅建议；核对标签路径后将完整标签评分降为补充 |
| 2026-10-18 | [research-framing.md](2026-10-18-research-framing.md) | 解释冻结模型/线性读出原理，区分发布标签/语义/探针/行为；原论文已有生成级patching，独立贡献仍需确证；无新实验 |
| 2026-10-18 | [classification-semantic-baseline-verified.md](2026-10-18-classification-semantic-baseline-verified.md) / [JSON](2026-10-18-classification-semantic-baseline-verified.json) / [开发CSV](2026-10-18-classification-semantic-baseline-development.csv) | 先推送65a3f26并核验，再完整重放570+18、三组bootstrap、独立计数/翻转与30旧判断对照；无合格候选，全83CPU通过，无新GPU；新分析尚未提交 |
| 2026-10-18 | [code-submission.md](2026-10-18-code-submission.md) | 用户授权归档现有证据诊断/语义复核/分类基线代码与记录；79CPU测试通过，提交推送结果随后核对 |
| 2026-10-18 | [context-restored.md](2026-10-18-context-restored.md) | 背景恢复；新分类正式570+smoke18已生成分析、保存报告无合格候选，完整只读重放待做；v4的600行/132未知/哈希一致，无新实验 |
| 2026-10-16 | [classification-semantic-baseline-running.md](2026-10-16-classification-semantic-baseline-running.md) / [JSON](2026-10-16-classification-semantic-baseline-running.json) | 20:33:27两smoke各9/9通过，正式首组227/285、第二组0，持续保存/13指纹一致，无截断，未完成指标 |
| 2026-10-16 | [classification-semantic-baseline-preparation.md](2026-10-16-classification-semantic-baseline-preparation.md) / [JSON](2026-10-16-classification-semantic-baseline-preparation.json) | 两候选各285val/9smoke，三标签约束/EOS，79CPU测试与两个预检查通过；正式0/570、smoke0/18，新GPU交用户，旧筛选门槛不变 |
| 2026-10-16 | [validation-semantic-followup.md](2026-10-16-validation-semantic-followup.md) / [判断](2026-10-16-validation-semantic-followup-ratings.json) / [CSV](2026-10-16-validation-semantic-followup-ratings.csv) / [汇总](2026-10-16-validation-semantic-followup-summary.json) | 用户授权同助手全30追加复核完成，12/13/4/1、50引用核验，2条由unknown作有条件解释；v4一致7/29仅诊断，不是独立评分，不改原首轮/模板 |
| 2026-10-16 | [validation-semantic-diagnosis-verified.md](2026-10-16-validation-semantic-diagnosis-verified.md) / [JSON](2026-10-16-validation-semantic-diagnosis-verified.json) | 用户正式CPU导出完成、10文件哈希/内容重放通过，30空白/7优先；全确定7/27、high5/23为旧助手判断一致计数，新独立评分0条 |
| 2026-10-16 | [validation-semantic-diagnosis-preparation.md](2026-10-16-validation-semantic-diagnosis-preparation.md) / [校验清单](2026-10-16-validation-semantic-diagnosis-preparation.json) | 用户自行启动CPU报告/全文HTML/全30条空白评审材料；5项测试与临时真实导出通过，正式待启动，新评分0条 |
| 2026-10-16 | [validation-semantic-pilot.md](2026-10-16-validation-semantic-pilot.md) / [汇总](2026-10-16-validation-semantic-pilot-summary.json) / [输入判断](2026-10-16-validation-semantic-pilot-input-ratings.json) / [归因](2026-10-16-validation-semantic-pilot-attributions.json) / [CSV](2026-10-16-validation-semantic-pilot-comparison.csv) | 固定30条、全文输入复核先封存再揭示，11/12/4/3，27确定中v4一致7；来源暴露披露，54引文与3项流程测试通过，不是独立金标准 |
| 2026-10-16 | [validation-evidence-audit-v4-verified.md](2026-10-16-validation-evidence-audit-v4-verified.md) / [JSON](2026-10-16-validation-evidence-audit-v4-verified.json) | 285正式+9smoke生成与CPU重放完成；277结构合法、43合法unknown+8截断；标签一致100/285非语义准确率，2个全文例子与技术/语义根因分层审计，不自动再跑GPU |
| 2026-10-16 | [validation-evidence-audit-v3-failure-v4-preparation.md](2026-10-16-validation-evidence-audit-v3-failure-v4-preparation.md) | v3已完成9条，8条前置分析截断，门槛1/9，正式0/285；v4扩大分析预算且保留完整检查/门槛，62项CPU测试与285/9预检查通过，GPU交用户 |
| 2026-10-16 | [validation-evidence-audit-v3-preparation.md](2026-10-16-validation-evidence-audit-v3-preparation.md) | 用户要求修复继续285条；受约束两字段JSON与原文ID，新schema/协议，58项CPU测试及285/9检查通过，v3尚未GPU；用户顺序入口smoke通过自动正式 |
| 2026-10-16 | [validation-evidence-audit-v2-smoke-failed.md](2026-10-16-validation-evidence-audit-v2-smoke-failed.md) | v2生成9/9，3合法unknown、6 invalid，门槛失败exit1；正式0/285，14指纹/输出哈希/冻结解析一致；保留v1/v2，先语义复核 |
| 2026-10-16 | [validation-evidence-audit-v2-preparation.md](2026-10-16-validation-evidence-audit-v2-preparation.md) | v2新指令/入口与终端失败提示准备，50项CPU测试和285/9检查通过；v1冻结文件未改，v2正式/技术smoke尚未启动，交用户执行 |
| 2026-10-16 | [validation-evidence-audit-smoke-failed.md](2026-10-16-validation-evidence-audit-smoke-failed.md) | 用户完成9条GPU smoke，结构/引用0/9通过，正式仍0/285；11指纹、输出哈希与冻结解析重放一致，无空/截断；保留v1，新设计须新目录 |
| 2026-10-16 | [context-restored.md](2026-10-16-context-restored.md) | 按交接入口恢复背景；v4哈希/600行/132未知、val三候选855条/无合格候选及证据诊断0输出轻量核对一致，保留既有暂存改动；未启动实验或查实时GPU |
| 2026-10-13 | [context-restored-02.md](2026-10-13-context-restored-02.md) | 提交归档及启动阻止后恢复背景；v4哈希/600行/132未知、val三候选855条/无合格候选及证据诊断0输出轻量核对一致，未查实时GPU或启动实验 |
| 2026-10-13 | [code-submission.md](2026-10-13-code-submission.md) | 用户授权提交推送；14个代码/测试/提示/文档文件归档，代码版本匹配此前46项CPU测试，c76ab6e已推送且远端哈希核验一致 |
| 2026-10-13 | [validation-evidence-audit-launch-blocked.md](2026-10-13-validation-evidence-audit-launch-blocked.md) | 用户启动尝试被GPU活动进程保护阻止；入口已退出、模型未加载，smoke0/9/正式0/285；占用PID及实时GPU状态未检查 |
| 2026-10-13 | [validation-evidence-audit-preparation.md](2026-10-13-validation-evidence-audit-preparation.md) / [JSON](2026-10-13-validation-evidence-audit-preparation.json) | 仅val的带原文引用证据草稿、空白盲审包及四组旧输出诊断代码完成；285/9条CPU检查与46测试通过，未启动GPU，用户顺序执行 |
| 2026-10-13 | [context-restored.md](2026-10-13-context-restored.md) | 按入口恢复背景；正式v4哈希/600行/132未知与验证集v3的855条/无合格候选轻量核对一致；无新实验、完整指标重算或GPU占用核查 |
| 2026-10-12 | [code-submission.md](2026-10-12-code-submission.md) | 代码、测试、提示词、v4及实验/研究记录归档；36项CPU测试与语法检查通过，本地提交标识见Git；未推送 |
| 2026-10-12 | [research-conclusions.md](2026-10-12-research-conclusions.md) | 综合全部已核验结果的8项结论及边界；使用当前v4和最新val结果，没有新实验或指标修改 |
| 2026-10-12 | [classification-prompt-validation-verified.md](2026-10-12-classification-prompt-validation-verified.md) / [JSON](2026-10-12-classification-prompt-validation-verified.json) | 三组val提示词855正式+27smoke完成并核验；Accuracy37.89/36.14/36.49%，冲突召回0/3.16/3.16%，无合格候选；确认集未用 |
| 2026-10-12 | [semantic-review-adjudication.md](2026-10-12-semantic-review-adjudication.md) / [JSON](2026-10-12-semantic-review-adjudication.json) / [v4](2026-10-12-semantic-review-adjudication-annotations.csv) / [字段裁定](2026-10-12-semantic-review-adjudication-adjudications.csv) | 300第二输入、232第二行为+2协调补评；117行148分歧逐字段裁定，正式v4分析核验，468确定/132未知；36CPU测试及新提示词v3准备通过，未启动GPU |
| 2026-10-12 | [context-restored.md](2026-10-12-context-restored.md) | 背景恢复与轻量产物核查；第二评审300输入/232行为保存并通过结构校验，缺B0594/B0596，汇总与裁定未完成；正式v3不变，新提示词无生成输出 |
| 2026-10-11 | [independent-semantic-review-preparation.md](2026-10-11-independent-semantic-review-preparation.md) / [JSON](2026-10-11-independent-semantic-review-preparation.json) | 独立盲审输入、重新编号、234条优先队列和CSV保护校验准备完成；独立评分0条，尚未启动第二评审；正式v3与报告不变 |
| 2026-10-11 | [classification-grid-verified.md](2026-10-11-classification-grid-verified.md) / [JSON](2026-10-11-classification-grid-verified.json) | 四条件正式2340条（2040新+300复用）生成、分析及核验完成；plain8/64均50%准确率，chat8/64均43%；格式修正及预算增加未建立可靠三分类基线 |
| 2026-10-11 | [classification-grid-launch.json](2026-10-11-classification-grid-launch.json) | 12:08 运行中历史快照：22项CPU测试、preflight/audit及四条件GPU smoke通过；正式分类由助手启动，未登记最终指标 |
| 2026-10-11 | [free-answer-followup-audit.md](2026-10-11-free-answer-followup-audit.md) / [JSON](2026-10-11-free-answer-followup-audit.json) / [v3 标注](2026-10-11-free-answer-followup-audit-annotations.csv) / [冲突质量](2026-10-11-free-answer-followup-audit-conflict-quality.csv) | 70 条同助手重点复核，16 行20字段改变；正式 v3 分析及计数核验；100 条冲突配置为68明确/13兼容/19含糊，显式改写元数据检查与独立空白包准备完成 |
| 2026-10-11 | [free-answer-semantic-review.md](2026-10-11-free-answer-semantic-review.md) / [JSON](2026-10-11-free-answer-semantic-review.json) / [600 条标注](2026-10-11-free-answer-semantic-review-annotations.csv) / [未知项](2026-10-11-free-answer-semantic-review-uncertain.csv) | 全部 600 条单一 LLM 首轮语义审核与正式分析；缺证且探针判缺证仍作答 plain 8/80、chat 12/82；199 条有歧义字段，未做独立人工复核 |
| 2026-10-11 | [review-interruption-check.md](2026-10-11-review-interruption-check.md) | 定位 600 条审核已保存到 item_0040，接续入口 item_0041；找到上次临时读取/保存脚本，中断原因未确定 |
| 2026-10-11 | [context-restored.md](2026-10-11-context-restored.md) | 按入口恢复背景；默认分类目录仅准备产物；行为 CSV 40 条部分判断、560 条全 unknown，批次/格式校验通过，内容未复核 |
| 2026-10-09 | [free-answer-generation-verified.md](2026-10-09-free-answer-generation-verified.md) / [JSON](2026-10-09-free-answer-generation-verified.json) | 自由回答生成已完成；2,370 个特征及 600 条探针预测核验，plain/chat 探针与长度分析；600 条行为待审核 |
| 2026-10-09 | [context-restored.md](2026-10-09-context-restored.md) | 按入口恢复背景与协作边界；未核验实时实验进度，未运行新实验 |
| 2026-10-09 | [ssh-push-verified.md](2026-10-09-ssh-push-verified.md) | 公钥已授权，SSH 推送成功，远端哈希与本地一致；认证阻塞已解决 |
| 2026-10-09 | [ssh-push-setup.md](2026-10-09-ssh-push-setup.md) | 长期 SSH 443 初次配置及当时等待公钥授权的历史快照；后续完成见上一条 |
| 2026-10-09 | [code-submission.md](2026-10-09-code-submission.md) | 本地代码归档及当时 HTTPS 凭据阻塞的历史记录；已通过 SSH 完成推送 |
| 2026-10-09 | [project-context-and-records.md](2026-10-09-project-context-and-records.md) | 项目入口/记录体系整理；用户正在运行自由回答；状态只读快照与下一步 |
| 2026-10-09 | [evidence-behavior-preparation.json](2026-10-09-evidence-behavior-preparation.json) | 四条件分类与同模板自由回答代码准备、固定设置、22 项测试、长度检查和审计；不是新 GPU 结果 |
| 2026-10-09 | [prompt-baseline-result.json](2026-10-09-prompt-baseline-result.json) | 已完成纯文本基线、严格解析失败、首行事后结果与路由器配对分析 |
| 2026-10-09 | [prompt-baseline-preparation.json](2026-10-09-prompt-baseline-preparation.json) | 旧 8-token 分类基线的准备和运行协议 |
| 2026-10-08 | [kba-record.json](2026-10-08-kba-record.json) | 最初代码审查、环境建立、数据审计、路由器复现和结果快照；含较多细节，按需读取 |

## 新记录怎么写

- 使用 `YYYY-MM-DD-主题.md` 写人工可读动作/实验记录；同日同主题再次记录可加 `-02` 或时间，保留旧记录。
- 需要结构化指标、清单或校验值时另存同主题 `.json`；可以在 Markdown 中链接它。
- 参考 [TEMPLATE.md](TEMPLATE.md)，写清目标、操作者、实际命令/修改、证据与产物、结论限制、状态和下一步。
- 明确区分 `prepared`、`running`、`generation_complete`、`review_complete`、`verified_complete` 和 `failed`。
  用户说“正在运行”只证明启动意图/报告；已保存一部分状态只证明部分进度，不能填写最终指标。
- 已完成实验汇总到 [experiments.csv](../experiments.csv)；连续历史摘要追加到 [activity_log.md](../activity_log.md)。
- 每次追加后更新本索引；当前交接状态同步到 [AGENTS.md](../../AGENTS.md)。

## 产物与记录的区别

完整输入、原始生成、探针、模型协议和激活数组保留在 `runs/`；数据来源保留在 `dataset/`。
`runs/` 不随 Git 保存，因此这里保存必要的轻量设置、汇总和校验值，便于跨会话恢复。
历史快照可能反映当时状态，最新状态以最新交接记录及实际产物为准。
不要把大权重、整批激活或凭据放进此目录；不要修改旧原始预测来匹配新的解析规则。

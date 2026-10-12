# 实验与动作记录索引

这个目录保存项目的持久实验记录、操作记录和交接快照。
新会话先读根目录 [AGENTS.md](../../AGENTS.md)，再读本索引和最新交接记录；无需一次性加载所有 JSON。
当前研究结论综合：[2026-10-12-research-conclusions.md](2026-10-12-research-conclusions.md)（生成前发布类别可解码、实际行为失配，冲突更普遍；提示词基线未合格，语义质量与非独立人工评分限制，确认/因果未完成）。
最新动作：[2026-10-12验证集新提示词完成核验](2026-10-12-classification-prompt-validation-verified.md)（用户启动，855正式+27smoke生成/分析/核验完成；三候选均未达预设门槛，no_qualified_baseline，未使用test或确认集）。最新行为交接：[第二评分与v4裁定](2026-10-12-semantic-review-adjudication.md)（300第二输入、232第二行为+2协调补评，148分歧字段裁定完成，正式v4已核验，132未知保留）。当天更早的准备/恢复及旧0评分均为历史快照。四条件分类核验：[2026-10-11-classification-grid-verified.md](2026-10-11-classification-grid-verified.md)。生成完整核验：[2026-10-09-free-answer-generation-verified.md](2026-10-09-free-answer-generation-verified.md)。
背景交接：[2026-10-09-project-context-and-records.md](2026-10-09-project-context-and-records.md)；10 月 11 日恢复与中断检查记录为首轮审核完成前的历史快照。

## 记录列表

| 日期 | 文件 | 内容与状态 |
| --- | --- | --- |
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

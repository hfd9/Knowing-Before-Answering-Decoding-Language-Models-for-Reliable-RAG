# 55条审查工作的完成状态与文件位置

更新日期：2026-11-06，Asia/Shanghai。最新证据见[隔离CLI复评记录](records/2026-11-06-isolated-cli-review.md)、[机器记录](records/2026-11-06-isolated-cli-review.json)及[结果与接续建议](isolated_cli_review_results.md)。此前文件完整性核验见[状态说明修正记录](records/2026-11-06-review-status-clarification.md)。

**原55条作者侧输入复核、155条主张判断保留；新增一个隔离CLI会话已完成55输入、55回答、172主张并实际接收。** 接收器不会自动认证独立性或正式标签，不能把正式批准0误说成没有实际审核文件。

此前内置代理尝试以 `fork_turns="none"` 启动，但报告仍有历史暴露，已停止，见[原审计记录](records/2026-11-06-agent-review-context-audit.md)。本轮改用项目目录外CLI新会话，先审计、再输入封存、后交付回答；实际未向它提供作者结果或协调映射，详见[新复评包](review/2026-11-06-isolated-cli-review-v1/README.md)。目录、自述和可见轨迹支持观察到的隔离，不证明完整私有上下文来源或语义金标准。

## 已完成工作

| 工作 | 当前产物与数量 | 本轮实际核验 |
| --- | --- | --- |
| 审查材料准备 | [材料目录](review/2026-10-23-semantic-claims-v1/README.md)，55条、275文档槽、140篇去重全文、82个原句候选单元，两阶段ZIP及空白表。 | 17个Git文件存在，与本轮父提交逐字节一致；包内容、来源、ZIP成员和原文连接核验通过。82是机械原句单元数。 |
| 作者侧输入及逐主张复核 | [作者复核目录](review/2026-10-23-semantic-claims-author-v1/README.md)，55条输入、155个主张实例、244处文档引用。 | 17个Git文件存在，与本轮父提交逐字节一致；从手写判断、显式补记和原文重放计数、引用、端点及CSV，通过。 |
| CPU接收准备 | 本地 `runs/qwen2.5-3b-semantic-claim-review-intake-v1` 的protocol、intake_report、normalized_reviews、endpoint_comparison四个JSON。 | 四文件存在，实际只读verify通过；状态为 `pending_no_review_files`。 |
| 新CLI两阶段复评与接收 | [CLI20261106R01](review/2026-11-06-isolated-cli-review-v1/README.md)，55输入/55回答/172主张；另开 `runs/qwen2.5-3b-semantic-claim-review-intake-cli20261106r01-v1`。 | validate、prepare及异进程verify通过，完整提交；原始评分和四JSON接收快照本轮纳入Git，原无提交run保持历史状态。 |

作者复核当前使用[analysis-v2/report.json](review/2026-10-23-semantic-claims-author-v1/analysis-v2/report.json)和[可读主张](review/2026-10-23-semantic-claims-author-v1/analysis-v2/claims.md)：101 supported、34 unsupported、13 ambiguous、7 contradicted。155包含重复主张，且拆分依赖本次作者判断，不能作为155个独立样本或总体准确率分母。

此前助手参与材料设计并已读项目历史及旧输出，因此这份已完成的复核标记为有历史暴露；技术重放不会改变这个事实。

## 旧run中的0与新run的实际接收

接收工具读取指定评分副本，不自动把作者复核转成独立评分。旧无提交run仍为0/0/0；本轮新run已实际接收55/55/172。新报告 `complete_submission_context_audit_pending` 表示收件完整、独立性不由工具认证；其 `independent_semantic_approvals=0` 和 `formal_gate=false` 不表示新复评没有发生。

原输入与回答空白模板各55行，全部 `status=unreviewed`、`reviewer_id=null`；作者判断另存，有意没有覆盖这些模板。程序核验和“独立实现核验”均为结构、算术、引文及字节检查，不能当作另一位独立语义评审。

前轮限定查找46候选、仅两空表是当时的检查快照。本轮已经产生新审核文件，不能继续引用旧查找作为当前无文件的依据。新评审的首次版本、元数据澄清版及备份属于同一评审，不计作多位独立评审。

## 本地存在与Git备份

审查材料目录17文件和作者复核目录17文件均受Git管理，归档于4ce17d6，当前仍与Git版本一致。

接收run的四个JSON受 `.gitignore` 第3行 `runs/` 规则忽略，当前仅确认本机存在及核验通过；正常 `git push` 不包含这四个载荷。文档中的哈希和核验结果能追溯本次检查，不能替代这些载荷本身的远端备份。原run继续保留，不为修正文案而强制加入Git或回写。

新run的四个JSON也受相同忽略规则管理，但本轮另将其相同字节保存到[coordinator/intake-snapshot](review/2026-11-06-isolated-cli-review-v1/coordinator/intake-snapshot/intake_report.json)，连同新原始评分纳入Git。新快照与本地四载荷已核对一致。

## 后续接续与汇报约定

按[已定决策](semantic_claim_review_decision.md)，本轮已在新run接收真实提交并保存引用、封存、暴露声明与分歧。下一项是人工审阅这些证据，决定是否采纳[条件性草案](explanation_evidence_scope_draft.md)。三条原关注案例的新复评均支持保留未知、反对无据冲突；其他9项输入/8项目标支持/6项解释支持分歧保留待裁定。自述未暴露或工具exit0均不自动认证独立性。

后续状态汇报同时列出作者复核完成量与独立审核接收量，并标明数字属于哪个流程。只有实际检查到已存在文件丢失或不符封存，才报告文件缺失或损坏；“尚未产生提交”和“Git未跟踪的本地文件”分别明确说明。

现有CPU配套与本轮新复评已完成，不要求用户重做已有55条审核，也不反复索要暂缺的外部渠道。是否接受本轮可观察上下文隔离的证据边界、如何裁定分歧及是否采纳草案仍需作出决策。原拟合预算0、正式gate=false、正式标签null及380题封存保持，当前没有新GPU就绪任务。

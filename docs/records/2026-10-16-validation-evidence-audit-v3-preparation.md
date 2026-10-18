# 2026-10-16：约束解码修复与285条v3执行准备

记录日期与时区：2026-10-16，Asia/Shanghai。
状态：prepared；v3 smoke0/9、正式0/285，均prepared_not_started。
操作者：助手实现和CPU检查；长期GPU仍由用户运行。

## 目标与背景

用户明确要求修复并继续285条。接续[v2失败](2026-10-16-validation-evidence-audit-v2-smoke-failed.md)，不再只追加格式提示，也不绕过门槛。实现可验证的生成时结构约束和原文ID引用，准备新的v3协议/目录与顺序入口。

## 实际操作

新增evidence_decision_grammar.py、validation_evidence_audit_v3.py、v3指令、两个sh入口和8项测试，无新增依赖。查阅本地Transformers4.56.2的prefix_allowed_tokens_fn实现并接入model.generate。先生成256token以内的自由证据分析，再用token trie限制两字段JSON决策，最多128tokens。词法/ID约束由解码过程实现；不事后填字段、去围栏或猜配引文。

完整五文档另附24词/步长16引用索引及原偏移；模型选择片段ID，程序从原文还原quote。answer允许1–4个ID，conflict两个不同文档ID，refuse/unknown空列表。未知保留，不强制确定类别。新schema为semantic_mode/citation_ids，所需/缺失事实与理由保留在自由分析中；不伪称原五字段协议保持不变。结构通过不证明语义能力或独立确认。

复用未修改v1的数据来源/旧输出核验、盲审包、逐条原子保存、GPU保护和6/9数量门槛。v3缓存额外核对两阶段原token/解码/预算/提示/输出哈希及来源解析；保存分析与决策，不将二者混为同一原始生成。辅助页面分别标出两阶段。报告区分合法确定决策和合法unknown。

## 证据、检查与产物

- 全套58项CPU测试通过，12.193秒；新增8项覆盖所有模式/多引文路径、早停与非法键/ID/同文档冲突、原偏移和Unicode、重复键/截断、两阶段缓存篡改、本地Qwen2.5 tokenizer、实际HF generate小型CPU Qwen、门槛失败阻断正式。两个sh语法及diff检查通过。
- 正式285条CPU check通过，最长首阶段14447tokens、第二阶段估算输入上界14849；smoke9条为13247/13649。256+128总预算384，每阶段运行时再检查32768上下文，不裁剪证据。全285条决策语法最长39tokens<128。
- 正式协议SHA256：`46c3635e2dd5b25e0aad432443de5b217235d202feaee7e82151963417a5706c`；smoke：`d7e45c2cc1147d42e290593a995aa7437bb7ac4e74211504d95050caffe8e410`。
- 两个v3目录protocol/preflight/progress及空白盲审包已保存，状态prepared_not_started，均无草稿预测。未启动本机3B GPU smoke或正式。
- v1/v2全部冻结代码/指令指纹仍一致；两份旧smoke预测SHA256仍为`62aca7443d8771552709398542d160c8b92aaa6df8bb08fdf4b937b3c98e1e90`、`faae35e64345aaa7226908b832956b8baf9b5655689ce54a0c99453dd3bfc07d`。

## 启动、估时与下一步

用户执行`sh scripts/run_validation_evidence_audit_v3_review.sh`。先9条，达到新schema的6/9技术门槛后自动继续285条；中断原样续跑。失败终端显示阶段/退出码/日志末尾。目录分别为runs/qwen2.5-3b-validation-evidence-audit-v3及同前缀smoke-v3。

预检查按12–25tokens/秒、每条满384输出、两次prefill与余量规划：smoke7.3–14.8分钟，正式78–162分钟，完整建议预留90–180分钟。v1/v2观测约21.5tokens/秒，v3未实测；估时不保证，GPU仍交用户。运行后助手核验原始输出、技术与语义unknown、引用和诊断报告，再继续语义复核。

## 解释边界

新schema/受约束解码属于方法变化，不能把结构通过解释为模型自由JSON遵循改善；更不能证明所选引用支持、语义冲突正确或模型自知。源文片段存在可由程序保证，语义仍需复核。新smoke是据v1/v2失败修订后的同三个val底题技术检查；全部285仅val，不改变旧候选选择，不使用380保留底题或开展patching。v4/132未知不变。

## 索引更新

新增本记录和[v3说明](../validation_evidence_audit_v3.md)，同步AGENTS、记录索引、旧执行说明与活动日志。不登记未完成GPU指标；不改旧代码/配置/protocol/输出，保留既有改动，未提交推送。

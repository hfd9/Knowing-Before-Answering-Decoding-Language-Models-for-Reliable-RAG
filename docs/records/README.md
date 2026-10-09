# 实验与动作记录索引

这个目录保存项目的持久实验记录、操作记录和交接快照。
新会话先读根目录 [AGENTS.md](../../AGENTS.md)，再读本索引和最新交接记录；无需一次性加载所有 JSON。
最新操作：[2026-10-09-ssh-push-verified.md](2026-10-09-ssh-push-verified.md)；背景交接：[2026-10-09-project-context-and-records.md](2026-10-09-project-context-and-records.md)。

## 记录列表

| 日期 | 文件 | 内容与状态 |
| --- | --- | --- |
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

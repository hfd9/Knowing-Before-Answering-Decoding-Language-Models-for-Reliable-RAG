# 验证集证据诊断v3：约束输出并继续285条

最新状态：用户已生成9/9，9条决策JSON完整，但8条前置分析触及256上限，技术门槛1/9失败，正式未启动。当前请使用[v4扩大分析预算入口](validation_evidence_audit_v4.md)；下文为v3历史说明，不原样重跑失败缓存。

2026-10-16代码与CPU准备完成：58项测试通过，smoke9条/正式285条预检查通过，两个新目录均prepared_not_started、0输出。未启动本机3B GPU smoke。

## 启动与续跑

GPU空闲时在项目目录执行：

```sh
sh scripts/run_validation_evidence_audit_v3_review.sh
```

入口先生成9条smoke，至少6/9条通过新协议的结构/来源检查后自动生成285条正式草稿并分析。不需要分两次启动；失败显示阶段、退出码和日志末尾，中断原样重跑可续跑。已有GPU任务时保护检查拒绝加载模型。

另一个终端查看日志：

```sh
tail -F runs/qwen2.5-3b-validation-evidence-audit-v3/launch/smoke.log runs/qwen2.5-3b-validation-evidence-audit-v3/launch/full.log
```

两阶段每条最长256+128=384个新tokens，两次prefill、引用索引增加输入长度；保守规划smoke约7–15分钟，正式约78–162分钟，完整入口建议预留约90–180分钟。使用12–25tokens/秒假设及加载余量，v1/v2实测约21.5tokens/秒；v3未实测，以上非时限保证。预计超过10分钟，因此按项目约定由用户启动，助手后续核验。

## 修复内容与协议差异

v1/v2依靠提示词让模型输出自由JSON，GPU实际出现漏字段、语法错误和改写引文。v3改为生成期间限制可用token，不事后修补旧结果，也不要求模型抄写整段原文。

1. 保留完整问题与五篇原文，另建24词、步长16的重叠引用索引，记录原字符偏移和片段编号。
2. 模型先写最多256tokens的纯文本证据分析，说明所需事实、支持/缺失和相关明确矛盾；此阶段仍可能判断错误或截断。
3. 第二阶段通过本地Transformers的prefix_allowed_tokens_fn约束生成JSON：`semantic_mode`及`citation_ids`两个字段。四类均允许，unknown不被禁止或改成refuse。answer须1–4个有效引用ID，conflict须两个不同文档的ID，refuse/unknown使用空列表。只有JSON完整后才能结束。
4. 程序根据ID从原文位置解析引用；不接受不存在ID，不把改写句子猜配到原文。原始分析、受约束JSON、两阶段token序列/提示/哈希及解析后的引用分别保存。

这是预先固定的新v3输出schema和解码方法，与原5字段JSON协议不同；所需事实/缺失事实/理由保留在自由分析文本中，不制造其结构字段。旧v1/v2的失败保持失败。6/9门槛数量不变，但v3结构由解码器保证，技术通过不能当作自由JSON遵循能力或语义能力提升。

## 检查、产物与边界

- 新路径：`runs/qwen2.5-3b-validation-evidence-audit-v3/`、`runs/qwen2.5-3b-validation-evidence-audit-smoke-v3/`。protocol/preflight/progress和空白盲审包已准备。
- 正式首阶段最长14447输入tokens；第二阶段估算上界14849，再预留128，小于32768。smoke为13247/13649。实际每阶段运行前重新检查上下文；不裁剪原文。
- 全285条的决策语法最长token上界39，低于128预算。真实Qwen2.5 tokenizer语法路径、CPU小型Qwen的实际HF生成、非法引用/早停/重复键/缓存篡改/Unicode偏移/标签隔离及包装入口阻断均已测试。58项CPU测试通过不等于本机3B GPU运行完成。
- 逐条断点仍为`drafts/predictions.json`；草稿报告`reports/diagnosis.{json,md}`；辅助页同时显示自由分析及约束决策。JSON报告另记合法确定类别数与合法unknown数，避免把结构合法unknown误称确定判断。
- 空分析或分析截断、决策不完整保留invalid/unknown。缓存复核两阶段token解码/预算、提示哈希、源引用及解析一致性；失败不补默认字段或行为标签。
- 仅val，不读test/确认预测；旧三候选仍no_qualified_baseline。引用ID有效只保证来源，不能保证引用支持结论、冲突语义正确或模型分析正确。适应性smoke仍复用原三个val底题；结果不是独立语义金标准。

完整生成后仅重做草稿分析：

```sh
sh scripts/run_validation_evidence_audit_v3.sh --stage analyze
```

复核评分规范沿用现有空白评分包，须显式`--stage analyze --ratings 本轮评分文件`并披露来源；不将模型分析或约束决策自动导入正式语义标签。

# 证据诊断v4：扩大分析预算后继续285条

最新状态（2026-10-16）：用户已完成smoke9条（8通过）及正式285条，CPU逐条重放/17指纹/独立计数核验通过。正式277结构合法、43合法unknown、8分析截断；与发布标签一致100/285仅标签一致率，语义复核未完成。详见[完成与根因审计](records/2026-10-16-validation-evidence-audit-v4-verified.md)。不需重跑下文GPU命令；下一步复核语义，不将技术通过当金标准。以下准备说明保留历史。

2026-10-16当前入口，代码与62项CPU测试、285/9条预检查完成，v4均prepared_not_started、0输出，未启动GPU。

## 启动

GPU空闲时执行：

```sh
sh scripts/run_validation_evidence_audit_v4_review.sh
```

先9条技术smoke，至少6/9条完整通过后自动继续285条。中断原样重跑。日志：

```sh
tail -F runs/qwen2.5-3b-validation-evidence-audit-v4/launch/smoke.log runs/qwen2.5-3b-validation-evidence-audit-v4/launch/full.log
```

v3已生成9/9，但8条分析触及256tokens且未EOS，门槛1/9失败，正式0/285。9条最终受约束JSON全部完整且EOS结束；失败原因是前置分析预算，不是JSON格式。v3结果保持原判定，不原样重跑。

v4复用v3约束JSON/片段ID与严格完成检查，把分析上限从256提高至1024tokens，决策仍128，总上限1152。另要求分析用2–4短句。预算是允许上限，不会强制每条生成满1024；仍截断则invalid/unknown，不放宽6/9，不自动改作refuse。代码、指令和协议均在新v4目录冻结，不改v3。

## 耗时与检查

v4未实测。按每条用满1152输出、12–25tokens/秒的保守容量规划，smoke约12–24分钟，正式约224–466分钟；完整入口满预算情形约4–8小时。若分析提前结束，耗时会缩短；v3的截断输出不能确定其完整分析长度，当前不把更短耗时当保证，启动后按v4实测更新排期。超过10分钟任务继续由用户启动。

正式最长首阶段输入14478tokens、第二阶段估算输入上界15648，预留128仍小于32768；smoke13278/14448。决策语法最长39tokens<128。实际运行每阶段再检查长度，不裁剪原文。

62项CPU测试通过，包括完整分析超过256但不超过1024的缓存校验、旧截断依然invalid、完整新预算的上下文检查、协议真实预算绑定，以及既有约束解码与GPU保护/续跑测试。CPU通过不代表本机3B GPU smoke已成功。

仅val、未知完整分母、来源/语义限制、原文片段规则和两阶段产物沿用[v3说明](validation_evidence_audit_v3.md)。引用存在不证明支持/矛盾正确；不选择新分类候选、不消费380保留底题、不导入模型草稿。生成完成后可用`sh scripts/run_validation_evidence_audit_v4.sh --stage analyze`重做派生报告。

# 2026-10-13：验证集证据诊断代码与用户运行准备

记录日期与时区：2026-10-13，Asia/Shanghai。
状态：prepared；正式和smoke均prepared_not_started，未进行新GPU推理。
操作者：助手完成代码与CPU检查；用户要求完成代码后交给其执行。

## 目标与背景

接续[背景恢复](2026-10-13-context-restored.md)及三候选no_qualified_baseline结果，按AGENTS仅在val诊断所需事实、明确矛盾、可能过度refuse和直接答题。先准备可复核的证据判断草稿与独立空白评分入口，后续再决定新候选；不放宽旧门槛追认最高分。

## 实际操作

新增`validation_evidence_audit.py`、两个sh入口、固定审核指令JSON及10项CPU测试。仅加载固定val、val特征来源元数据和旧四组val分类输出，校验数据、来源、对照和缓存。模型提示隔离发布标签、gold_answer和旧分类输出，保留完整五文档。

固定Qwen2.5-3B-Instruct、BF16/SDPA、chat、greedy、512-token预算。严格JSON草稿须记录所需事实、缺失事实、理由和逐字引用；引用错误/解析失败/非EOS截断保持unknown。逐条原子保存、协议冻结、缓存一致性校验、GPU空闲保护及断点续跑已实现。

顺序入口先运行3底题/9条技术smoke，结构与引用检查至少6条通过才启动95底题/285条正式。结构合法unknown也计结构通过，不作语义质量批准。新formal/smoke独立目录，不改变旧实验代码或产物。

重新编号盲审页只显示问题与五文档，空CSV保持全unknown；协调映射独立保存。辅助页面显示草稿和原分类输出，并明确其背景暴露。仅显式传入--ratings才单列复核统计，不自动导入草稿，不认证评审是否人类/独立；unknown和invalid保留全分母。队列保留全部旧输出，直接答题需后续语义复核。

## 证据、检查与产物

- 实际完成正式CPU check：285条、保存输出0；最长输入5370tokens，预留512，小于32768。四组旧val输出来源/完整性校验通过。
- 实际完成smoke CPU check：9条、保存输出0；最长4917tokens，预留512，小于32768。
- 最新全套CPU测试46项通过，10.680秒（旧36项+新增10项）。覆盖标签隔离、仅val来源、严格JSON/引用、截断未知、批次/评分保护、草稿与复核统计隔离、旧无逐输出哈希缓存的整文件校验、缓存损坏、模拟中断续跑和smoke停止门槛。
- 两个新sh入口语法检查通过；代码与新增JSON读取/编译检查及本次diff检查见同名结构化记录。没有实际加载大模型或检查宿主GPU占用。
- 初次CPU预检查因旧chat8记录不含raw_output_sha256而中止；在写入新protocol前修正为按旧搜索protocol的整文件哈希验证旧对照，新候选仍逐输出验证。新增对应测试并重新完成正式check；没有改旧输出、指纹或补默认数据。
- 正式目录`runs/qwen2.5-3b-validation-evidence-audit-v1/`；smoke目录`runs/qwen2.5-3b-validation-evidence-audit-smoke-v1/`，协议/预检查/进度及盲审包已经保存。尚无drafts/predictions.json或新GPU报告。

## 估时、启动与续跑

正式规划27.3–65.8分钟、smoke3.8–6.9分钟；完整顺序入口建议预留约35–75分钟。基于每条满512输出tokens、假设40–100tokens/秒和加载余量，未实测，不保证时限。用户执行：

```sh
cd '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG'
sh scripts/run_validation_evidence_audit_review.sh
```

中断原样重跑；日志为正式目录`launch/{smoke,full}.log`，逐条断点为各目录`drafts/predictions.json`，失败位置为last_failure.json。smoke不通过时停止正式，不绕过门槛；新代码/提示须新目录与协议。详细复核及单独分析命令见[执行说明](../validation_evidence_audit.md)。

## 结果与解释边界

本次交付为可执行代码与CPU准备，没有新模型语义结果，未登记实验指标。同模型审核草稿是辅助诊断，原文引用的存在不证明支持或矛盾关系，不能把“旧refuse、草稿answer”自动称误拒。独立语义金标准仍缺，旧三候选继续no_qualified_baseline。

原正式自由回答v4、132未知、300诊断test和380保留确认底题保持原状态。没有新候选选择、确认预测、patching、提交或推送。

## 未完成项与下一步

用户启动实际GPU smoke和正式生成；助手随后检查输出、引用/截断/解析与诊断报告，按完整文档复核验证集语义质量，再决定新提示设计。技术smoke尚未执行，当前代码通过CPU准备不等同GPU生成成功。后续评分来源、项目背景暴露与同模型限制须继续披露。

## 索引更新

更新AGENTS、记录索引、执行说明入口和活动日志。准备状态不更新experiments.csv；旧记录和运行产物不覆写。

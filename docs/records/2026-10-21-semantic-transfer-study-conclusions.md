# 2026-10-21：语义迁移研究结论整合与后续决策

记录时间与时区：2026-10-21，Asia/Shanghai。
状态：existing_evidence_synthesis_complete / verified / history_exposed / independent_gold=false。
操作者：助手；用户要求“直接开始后面的工作”。

## 目标与实际操作

承接已完成的240条采集、行为复核、同题配对和唯一一次作者参照重训，将其整理为可审阅的研究结论、证据对应关系和后续决策。先读取既定计划、执行约定与最新设计，实际重放最新v2离线分析及行为核验，再整理已有数值。没有新增研究指标、假设检验、评分或实验。

新增[综合报告](../semantic_transfer_conclusions.md)、[结构化证据JSON](2026-10-21-semantic-transfer-study-conclusions.json)、[16条证据指针CSV](2026-10-21-semantic-transfer-study-conclusions-evidence.csv)与[核验JSON](2026-10-21-semantic-transfer-study-conclusions-verification.json)。证据值从三个已存机器报告的明确JSON指针原样复制，不重算bootstrap或选择新切片；摘要表只沿用已有统计结果。汇总和校验使用本轮临时CPU脚本，不新增项目执行入口或测试。

## 实际检查

- `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/semantic_transfer_exploratory_retrain_analysis_v2.py --stage verify`实际exit0，累计真实fit=1、本次新fit=0、剩余0，评估来源一致率0.6458333333333334。
- 相同线程环境执行`python -B scripts/semantic_transfer_exploratory_behavior_review.py --stage verify`实际exit0，240行、869既有路径校验通过；没有新增行为判断。
- 重训记录的901旧路径及拟合seal的12文件逐项SHA256检查匹配；结构化证据16条与原JSON指针逐值匹配，三个源报告SHA256已保存。旧新probe的评估来源完整分母行为字典相同。
- 本轮没有修改冻结实验实现、协议、原模型、attempt、原回答或评分，也没有重跑旧单元测试。纯文档和既有证据汇总未新增单元测试。

## 决策与边界

现有证据支持本批证据编辑的方向性信号响应、缺证后总体作答减少及仍存在的行为失配。旧probe可靠语义测量未确证，一次重训也有冲突漏检代价：评估来源57/96→62/96、差+5.21pp的区间[−5.21,+16.67]，冲突召回18/24→11/24。因此结束本轮既定构造/拟合预算内实验，保留行为描述和测量失配结果，不进入依赖可靠读出的因果干预。

独立语义批准仍0、原正式门禁false、标签null；评估来源输出已见。来源为当前助手已有历史暴露的作者参照，不能称独立金标准或前瞻确认。原一次预算耗尽，后续独立审核也不恢复预算；不因换目录或报告修复再fit。unknown保留，不把识别上下界当采样区间，不以条件分母变化声称行为变化。

## 后续与交接

本轮综合报告与证据对应表已完成。后续可使用现有报告、图表和v2只读verify；若未来独立审核渠道实际具备，另存评分来源/上下文审计与封存probe比较口径，当前不反复索要。380保留题继续封存，新增确认或因果实验需另定范围，不由本轮报告自动启动。

同步AGENTS、记录索引、活动日志与设计文档入口。没有新实验或新指标，不新增docs/experiments.csv行；该文件此前已有未提交修改保持。本轮无新GPU/模型前向/回答/评分/拟合/380输入访问，未提交推送。

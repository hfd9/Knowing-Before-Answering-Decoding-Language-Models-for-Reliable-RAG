# 2026-11-09：FaithEval条款、问题排重和语义参照

记录时间与时区：2026-11-09，Asia/Shanghai。状态：verified_complete（本轮核查完成，条款和最终语义参照仍有未决项）；操作者：助手。

## 背景与实际操作

用户要求直接完成前述三步并做好记录。完成[来源条款清单、实际问题文本聚合排重、五文档语义参照判断](../review/2026-11-09-faitheval-feasibility-followup-v1/README.md)。原始资料包括FaithEval、MRQA、SQuAD、AI2 DROP/TQA、RACE、NewsQA及BioASQ/SearchQA发布方页面；一处AI2 TQA网页403，记录未能直接查证，不解释其原因。Data card声明论文研究用途，代码许可不能代替数据和上游；RACE原作者有非商业研究限制，NewsQA原作者说明CNN内容权益；各自派生使用/再发布仍未统一解决。

固定此前两个FaithEval commit，严格同qid同subset的785个记录对照旧项目200训练、95验证、100已用诊断和30作者问题。网络只解析qid/subset/question到内存，未读取候选context/answers、不保存样本或逐题匹配；HTTP范围可能含邻近压缩字节。三份旧项目文件及manifest SHA、行数和原已用chat记录ID逐项一致，30作者问题材料SHA `561f491e734447b6d71490ed739c6d7afca9a14d06a0aa043958b8d9331e4ac8`。没有读取原测试归档或380封存题。

## 结果、验证与限制

785个I/C问题经NFKC/casefold/Unicode词元规范化后相同；1个候选qid的问题与旧train200规范化相同，subset为TriviaQA-web。词元集合Jaccard≥0.8且两侧≥5不同词的固定开发规则无额外命中；28候选问题过短，仅做精确比对。其余784不代表无重叠：未审上下文/答案、其他历史数据、句义改写、预训练或380；精确问题命中不自动证明底题身份/文档相同。[主计算](../../scripts/faith_eval_question_overlap_20261109.py)和[异进程倒排索引复算](../../scripts/verify_faith_eval_question_overlap_20261109.py)一致，共享固定读取/规范化；合成Unicode、精确、近似、短问和空问检查通过。[汇总](../review/2026-11-09-faitheval-feasibility-followup-v1/summary.json)只留计数，无qid/正文。

FaithEval论文报告原I/C三人多数审核，但既没有逐个原票，也没有项目最终五文档S/I/C或表达版本，故原参照不能认证改造后输入。报告明确每种状态需逐槽证据、缺证见证或冲突归属及A/B关系审核，保留unknown和实际评审暴露；未执行新评分、不要求用户逐条审核。目前许可及语义覆盖未成立，不满足确认/GPU条件。原v1/E1-r1门禁false、正式独立批准0、标签null、原拟合预算0、380封存；无样本选择、模型、GPU、拟合或patching。

## 记录与后续

本轮为所授权的三步核查，不构成候选实验协议。后续须确定可使用的来源及适用条款、非封存范围排重覆盖、可审计最终输入与分歧处理，再评估研究增量，必要GPU由用户执行。按项目长期约定更新索引、活动日志及交接，并提交推送；实际Git状态以回复为准。

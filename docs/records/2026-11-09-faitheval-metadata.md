# 2026-11-09：FaithEval固定版本元数据与安全排重范围

记录时间与时区：2026-11-09，Asia/Shanghai。状态：verified_complete（元数据计数完成；语义、跨数据集排重及许可尚未通过）；操作者：助手。

## 目标与操作

按用户“直接开始”接续来源计划，锁定FaithEval缺证main `4a14e0e9860e270a8c9ff57c511821f4f50dce57`与冲突main `e29508db3955db2c82a80a1f3c3aadc11f93fc3f`，参见[结果和来源](../review/2026-11-09-faitheval-metadata-v1/README.md)。先通过`git ls-remote`核实commit，再按固定URL用严格HTTP range及Parquet列投影读取`qid`/`subset`；只在内存中连接，保存聚合JSON，不保存逐题ID或文件，不解析question/context/answers等正文。网络范围可能含邻近压缩字节，故不宣称传输只含这两列；未对全文件重算SHA。

## 结果与验证

I共2492行/2491唯一qid，1个重复qid；C共1500行/1500唯一qid。交集785，全部两侧各一行且subset相同；I重复qid不在交集中。十来源计数及分布见报告；非HotpotQA/NaturalQuestionsShort/TriviaQA-web的七来源交集557，但来源名不同不证明题目无重叠，也不等于有效实验样本。

实测[原计数器](../../scripts/faith_eval_metadata_counts_20261109.py)和[异进程SQLite复算](../../scripts/verify_faith_eval_metadata_counts_20261109.py)一致；共享远程读取和列解码，仅称独立聚合。合成Parquet检查重复、跨subset、空ID和不输出正文通过。首次HTTP库因环境缺`aiohttp`失败，改为严格206范围读取；沙箱内网络失败后按权限机制放行同一只读远程统计，独立复算同样只读。

## 范围与后续

既有chat train/val/已用诊断test仅字段级检查：600/285/300记录含本地original_id但无FaithEval qid，不能直接等值跨集排重。未打开380或原完整test成员，无法断言与封存题无碰撞；未进行文本/语义比对或适配成五文档。FaithEval数据卡研究用途、代码Apache以及上游数据条款仍需分别处理。当前无可认证确认样本或新实验协议；原v1/E1-r1门禁false、正式独立批准0、标签null、拟合预算0、380封存。不自动扩样、拟合、重训、调阈值或patching；没有新语义评审、模型/探针加载或GPU。

后续若评估来源，先确定使用许可和受限文本级排重的可行范围，保持380不可访问的风险；适配后的S/I/C、表达和参照需另审。本轮按长期约定更新交接、索引、日志并提交推送；实际提交及远端以Git和回复为准。

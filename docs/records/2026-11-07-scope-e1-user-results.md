# 2026-11-07：E1用户版48条结果核验及知情主张评分

时间与时区：2026-11-07，Asia/Shanghai。状态：用户完成48回答，助手完成来源/输出核验与有历史暴露评分；操作者：用户GPU采集、助手CPU核验及评分。

## 用户要求与实际来源

用户报告`validated_complete_unreviewed`、48条，并已要求完成后助手继续。实际只读`--stage inspect`确认48记录/48 attempt、四smoke通过、全48技术complete、无failure marker；`--stage package`生成匿名packet及协调映射，协调端归档[56份原始来源副本与清单](../review/2026-11-07-e1-user-results-v1/source-manifest.json)。运行manifest标`synthetic_fixture=false`，用户版release/计划与指纹绑定；用户报告和本地记录支持实际运行，但未独立认证所有模型输出来源。48输出均EOS、非空、未截断，28–109 tokens、合计2411；记录生成耗时合计368.774秒，首末完成12:55:29至13:01:36 UTC，不等于完整加载总时长。没有重复前向、额外smoke、拟合或访问380题。

## 评分与结果

助手完整阅读48问题/240文档槽及48回答，形成104个手写主张实例，原始[逐主张判断](../review/2026-11-07-e1-user-results-v1/review-sealed/review.json)及暴露声明在13:08:55 UTC封存后连接映射。可见引用104答案/299文档实例全部逐字匹配，主张实例有重复不算独立样本；摘要、引文及可观察阅读不证明语义真值。当前助手已见条件、设计和旧结果，非独立或人类评审，正式独立批准0。

初版[analysis](../review/2026-11-07-e1-user-results-v1/analysis/summary.json)形成并查看后，同一助手对R005/R020/R026/R034“先给值、后称不能确定”保守改为最终选择unknown；保留初版及原始封存，当前用[analysis-v2](../review/2026-11-07-e1-user-results-v1/analysis-v2/summary.json)。差异仅4行各2个端点字段，另控制条件转换理由同步澄清；非新增盲审/预先独立裁定，两版主比较相同。七条“没有分配”字面范围不清的W保留unknown。

主比较12对全部已审：I0与IU狭义E各0 yes/12 no，故两组J各0/12，J(IU)−J(I0)=0，识别界[0,0]；即使W未知，只要E=no，三值J仍为no。W分别I0 3 yes/5 no/4 unknown、IU 5 yes/4 no/3 unknown；未撤回目标值I0 5/12、IU 4/12。S记录相对支持目标回答11 yes/1 unknown；CT目标冲突识别6 yes/6 no，无消解选边9 yes/3 unknown。所有范围都是本批完整分母上的识别范围，不是置信区间；零事件不证明等效或总体安全。R039/R047错误声称另一单位不同字段冲突，R032目标值有记录支持但误称两独立字段冲突；这些不是I0/IU狭义目标字段E正例。详细见[结果说明及表格](../review/2026-11-07-e1-user-results-v1/README.md)。

## 实际验证及后续

- [独立只读重放](../../scripts/verify_e1_user_results_20261107.py)exit 0：56原件与归档哈希、48 attempt/记录/输入输出绑定和本地tokenizer解码、104答案及299文档引用、各端点计数和12对主比较独立复算均一致；[结果](../review/2026-11-07-e1-user-results-v1/audit/independent-verify-v2.json)。检查不认证语义或模型来源。
- 接收器`verify`对v1及v2各exit 0；原始主张和两版转换均逐字节重建；3项[结果边界回归](../../tests/test_e1_user_results_20261107.py)0.009秒通过，覆盖四例修订、目标/其他单位冲突分离和完整配对。两个CSV由单独只读导出脚本生成。
- 旧55条CLI只读核验exit 0，72个旧来源、12个拟合封存及4个接收快照保持；新运行已按现有23列格式登记`experiments.csv`，其合成场景不是原val或test分区。
- 本轮结果、来源快照及核验实现的81项文件哈希保存在[制品清单](../review/2026-11-07-e1-user-results-v1/audit/artifact-inventory.json)，清单不包含自身，不认证语义或模型来源。
- 用户版release按既定单次计划完成，原v1/E1-r1旧门禁保持false、正式独立批准0、原拟合预算0、正式标签null及380封存。原始run忽略Git，56文件逐字节快照与评分、映射和结果归档于review包；不将缓存声明当独立来源认证。用户无需逐条审核。

当前计划的48条已完成，不应重复GPU；后续根据研究问题解释/整理结果，任何新材料、扩样、重训、阈值搜索或patching均需新协议，不能以零事件为由自动继续。按长期约定更新索引及实验清单后提交推送，实际哈希以Git及回复为准。

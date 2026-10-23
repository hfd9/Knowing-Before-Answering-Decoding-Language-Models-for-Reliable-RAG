# 2026-10-23：旧缺证作答与虚构绑定的差异审计及新对照样例

日期与时区：2026-10-23，Asia/Shanghai。
状态：offline_structural_audit_and_design_examples_complete；非完整材料准备、非采集就绪、无新实验结果。
操作者：当前助手；已接触作者判断、旧输出与项目历史，independent_gold=false。

## 目标与设计修正

用户要求直接执行上一轮提出的“差异审计＋一个有明确增量的新对照草案”。本轮复用旧23条缺证作答细分、原240行为、48虚构绑定结果及原提示材料，完成逐条结构对照与新草案/少量样例。先读研究计划与运行说明；未调用模型、probe或外部服务。

核对发现，“目标关系缺失但另一实体有同属性候选”已经被原48绑定完整覆盖。新草案不重复该设计，而明确区分候选所属实体与属性：TQ目标/所问属性、OQ另一实体/所问属性、TA目标/另一属性、OA另一实体/另一属性；唯一主要比较TA−OA，两端均缺证，只改变候选附着实体。所有候选始终在文中，不声称检验有/无候选效应。

## 实际审计与新产物

本轮读旧23条完整I输出和相关I引用，复用旧已封存全文审计，不冒称重新全文阅读121篇。原分类8事实挪用/9关系提升/6新增值保持，8条解释边界保持，不重评任何旧行为/输入标签。

新13底题/23行结构对应为：3条同目标另一关系直接启发、3条已覆盖的跨实体轴、4条仅有角色类比、13条在新代码草案之外。它们只是作者侧设计对应，不是内部机制分类，也不估计总体频率。

从保存预测连接输入长度：全部旧I60为341–3045tokens、均值1336.88；选中I23为341–2537、均值1263.22；旧绑定I24均238。五槽文档字符范围分别922–11694、922–9901、300–300。token来自历史记录，无新分词。长度、问法、实体、推理及文档形式同时改变；不据此归因单一因素。原60不足中23实质作答/37不答与绑定24中0作答由封存评分连接重核；不比较选出的23/23与0/24，不把跨批差当干预效果。

新[设计说明](../behavior_relation_attachment_design.md)/[设计JSON](../../prompts/behavior_relation_attachment_design_v1.json)固定拟定上限6场景×4格×2值=48，12充分/36不足，主要12对，按场景等权；不拟合/采状态、不新增bootstrap或显著性检验，unknown保留识别界，失败不默认为拒答，TQ失败不筛场景。只制作2场景16样例，完整48的其余四场景、顺序、smoke、真实分词/采集代码未准备。保留的16例计入将来48上限，不另算技术smoke。

16样例/80文档槽已由当前助手全文读取，另存有暴露作者逐行检查。主比较通过候选句和冗余ledger句交换实体，平衡实体提及与词/数字多重集；不能称一个子串或完全相同token位置。共享背景明确字段独立且允许同值；每条不足样例配两个不同目标赋值的兼容完整世界，既允许目标恰等候选，也允许不同，不设隐藏I真答案。共12不足/24世界、4充分、24结构配对，其中4主要比较；每对仅一槽变化，无协调代码泄漏。

明确独立字段规则可能使任务易于拒答，单句型和两字段方向仍非常狭窄。新草案能增加同实体另一属性的受控行为证据，不能解释旧23/60与0/24根因、修复旧probe、认证自然文档泛化或内部因果机制。若零事件，按上限结束，不再添网格追错误。

## 实际检查与边界

新stdlib入口`scripts/behavior_structure_audit.py`只有build/verify，无采集或模型入口。实际build及PYTHONHASHSEED=239异进程verify均exit0，按字节重放10个新数据/样例产物。实际独立`scripts/verify_behavior_structure_audit.py`不导入主脚本，另从原评分重连60/24分母、23旧行/分类/边界、五统计切片误差0、16样例/作者记录、24兼容世界与24配对，exit0；核验JSON另存。

实际检查旧1132路径及校准CPU run10路径，共1142旧路径SHA256匹配，包含12唯一拟合封存文件和共享预算；未改原代码、协议、评分、回答、特征、probe或runs集合。新脚本读取的是必要输入/输出JSON和哈希清单，不反序列化probe或载入激活计算。原旧测试套件未重跑；仅做新Python AST、JSON及文档差异检查，不把新离线核验写成GPU/新统计结果。

本轮开始已有上一步背景恢复的AGENTS/索引/活动日志及新恢复记录改动，予以保留，在这些交接文档继续追加本轮状态。未提交、未推送。原拟合预算0、独立语义0/正式gate=false/标签null、380封存不变。没有新行为评分、前向、生成、拟合或实验完成指标，不新增experiments.csv行。

## 主要文件与后续

- [审计JSON](2026-10-23-behavior-structure-audit.json)、[23行CSV](2026-10-23-behavior-structure-audit-cases.csv)、[13底题CSV](2026-10-23-behavior-structure-audit-bases.csv)、[五统计切片](2026-10-23-behavior-structure-audit-statistics.csv)、[七差异维度](2026-10-23-behavior-structure-audit-dimensions.csv)。
- [16完整输入Markdown](2026-10-23-behavior-structure-audit-samples.md)/[JSON](2026-10-23-behavior-structure-audit-samples.json)、[协调世界](2026-10-23-behavior-structure-audit-worlds.json)、[24结构配对](2026-10-23-behavior-structure-audit-pairs.csv)、[作者检查](2026-10-23-behavior-structure-audit-author-review.json)。
- [1142旧路径清单](2026-10-23-behavior-structure-audit-preserved.json)、[独立核验JSON](2026-10-23-behavior-structure-audit-verification.json)、[事后结构对应口径](../../prompts/behavior_relation_attachment_audit_v1.json)。

当前授权的差异审计、可审阅设计与少量样例交付完成。若继续，应先完成完整48材料及CPU采集准备，再按既有分工提供用户GPU命令；本轮不自动推进该阶段，不将草案当就绪运行协议。复核使用`python3 -B scripts/behavior_structure_audit.py --stage verify`或`python3 -B scripts/verify_behavior_structure_audit.py`，无需GPU。

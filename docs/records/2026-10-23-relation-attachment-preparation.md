# 2026-10-23：关系附着六场景48条材料与CPU采集准备

日期与时区：2026-10-23，Asia/Shanghai。
状态：prepared_not_started_cpu_verified。操作者：当前助手；有作者/历史暴露，非独立语义审核。

## 目标和范围

用户要求“继续推进研究”。本轮承接已交付差异审计与两场景16例，完成六场景48材料、全文作者检查、固定评分与严格采集入口、CPU测试、真实prepare/verify与独立重建。GPU按既有分工留给用户启动，助手不新增前向、回答或拟合。

新任务只观察行为：目标/另一实体×所问/另一属性四格TQ/OQ/TA/OA，每场景两个候选版本；唯一主要比较TA−OA、12对，六场景等权。新[材料spec](../../prompts/behavior_relation_attachment_materials_v1.json)显式允许该探索性行为采集，旧设计文件中的未准备/collection=false为草案时状态，原文件保持不变；不是修改原语义实验门禁或恢复拟合预算。

## 材料与作者检查

原16例精确问题/文档保留，计入48。剩余四场景按新spec中的seed42规则，在tokenizer检查前固定实体、值、排列和槽位；新数字及有/无事件未知，不根据模型结果选择材料。两个提问字段方向各3场景，实体大小顺序3/3，代码v1/v2/协调见证六种排序各一次；候选槽[1,4,2,5,3,1]，场景内八格相同。

当前助手实际全文读48问题/240文档槽、57不同全文，分别核对六场景两值与四格，另存[作者检查](../../prompts/behavior_relation_attachment_author_review_v1.json)。仅TQ12条有直接目标关系；其余36条每条配两个兼容世界，每个世界为四个实体—字段对赋值（两个实体×两个字段），共72完整世界，只改变所问目标字段；允许恰等候选或不同，不设I隐藏真值。正式训练标签不新增，独立语义批准0。

全部72结构配对逐字核对仅一个文档槽变化，含12主要TA/OA配对。通过候选句与冗余ledger句交换实体保持词/数字多重集；独立真实token检查也发现12组主要配对的完整输入token多重集相同，序列不同，不等于相同位置/注意力或机制控制。字段独立背景明确，可能使拒答容易；一个句型六场景不认证自然文档泛化，不解释旧23/60与0/24根因。

## 实现与采集规则

新`scripts/relation_attachment_study.py`、sh入口和10项测试，复用未改的旧behavior_binding_study的模型指纹、单条生成与原renderer；新代码自行校验48预算、6场景、缓存/marker和新导出，不改旧冻结实现。缓存验证只查询一次tokenizer词表大小，避免逐token重复len查询；未提交attempt或孤立临时文件在加载模型前停止。普通提交前缀可续跑，已有输出不重答。

固定四条技术smoke为rel01_TQ_v1、rel02_OQ_v2、rel05_TA_v1、rel06_OA_v2，计入48；技术门槛非空/EOS/未触顶，不考答案或拒答。失败停止且保留标记。最多48实际生成，不额外smoke、不采状态/加载probe/拟合。

新[评分规则](../../prompts/behavior_relation_attachment_scoring_v1.json)固定五字段，共240未来评分槽，准备/采集阶段全部unknown/unreviewed，技术报告的行为主率null。TA−OA按六场景平均、unknown保留识别界，不按TQ正确筛场景，不新增bootstrap或显著性检验。所有36不足实质作答与12充分有据答另列；采用候选为零不遮蔽文外猜测。匿名输入/行为与协调映射分开，有历史暴露必须披露。

## 实际检查

新10项CPU unittest实际通过，8.115秒。检查完整48模拟收集和重复续跑不加载模型、不重采样、未评导出；四条smoke失败停止；未提交attempt/孤立tmp、缓存文本/token/元数据/EOS/时间损坏拒绝；正常提交5条后中断续跑无重复、保留历史failure；材料/世界/问题破坏、匿名渲染隔离和真实来源准备重放。模拟回答位于临时目录，不是本机3B推理；旧测试套件未重跑。

真实执行`sh scripts/run_relation_attachment_study.sh --stage prepare`及`PYTHONHASHSEED=241 sh scripts/run_relation_attachment_study.sh --stage verify`均exit0。完整2权重分片/模型元数据、13实现/9来源指纹通过；未实例化推理模型。48实际原chat提示均267tokens，总12816，无裁剪。6144为最大新增输出预算，不是实测输出。

另写`scripts/verify_relation_attachment_preparation.py`，不导入采集器，从固定P0及AST读取原自由回答指令、独立应用本地chat模板及分词，重建48提示/token/hash、条件与匿名材料、36/72世界、72配对/12主对、原16例一致性，实际exit0。该脚本重新核对五模型元数据文件，不重复全权重哈希；完整权重检查来自真实prepare/verify，不冒称独立脚本也做了。新run10文件和1162此前路径集合/字节核对通过，含原12拟合封存与共享预算。

新run为`runs/qwen2.5-3b-relation-attachment-v1`，只有10份冻结准备/审阅文件另锁，predictions/generation_attempts均不存在，实际GPU/前向/回答0。原“仅2场景16例/无入口”是上一阶段快照，新版本完整48已就绪由用户启动，不修改旧记录字节。

## 交付与下一步

[运行说明](../relation_attachment_study.md)提供启动/续跑、日志、异常停止和完成后核验。用户执行：

```sh
sh scripts/run_relation_attachment_study.sh
```

日志`runs/qwen2.5-3b-relation-attachment-v1/launch/collection.log`；建议预留5–20分钟含CPU/加载与生成，容量规划不是新GPU实测。按AGENTS“估算不能保证低于10分钟时按长期任务处理”由用户启动，助手本轮不运行。

采集完成后用`sh scripts/run_relation_attachment_study.sh --stage verify-results`，再显式离线行为评分，不能把技术完成当行为结论。原预算0/独立语义0/正式gate=false/标签null/380封存保持，无新统计结果或实验指标登记，不自动扩容/调参/patching，未提交推送。前两步背景恢复及差异审计的工作区改动均保留。

材料与检查副本：[48全文](2026-10-23-relation-attachment-preparation-inputs.md)/[JSON](2026-10-23-relation-attachment-preparation-inputs.json)、[世界](2026-10-23-relation-attachment-preparation-witnesses.json)、[72配对](2026-10-23-relation-attachment-preparation-pairs.csv)、[阅读清单](2026-10-23-relation-attachment-preparation-reading-inventory.json)、[1162旧路径](2026-10-23-relation-attachment-preparation-preserved.json)、[10准备文件](2026-10-23-relation-attachment-preparation-run-hashes.json)、[独立核验](2026-10-23-relation-attachment-preparation-verification.json)。

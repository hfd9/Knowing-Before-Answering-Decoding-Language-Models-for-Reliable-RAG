# 查询可判定性开发试验：用户 GPU 执行入口

2026-11-15，Asia/Shanghai。状态：`prepared_not_started`，当前72计划输入、0实际attempt、0回答、0评分。按用户持续推进的明确要求，在既有主线上另立探索性开发运行；不是正式确认，不修改原v1/E1-r1门禁，不访问380正文，不训练probe。

## 设计与已完成工作

[任务与评分合同](CONTRACT.md)固定“同一对可能世界、问题答案相同/不同”及单世界基础对照；[材料](material.jsonl)为当前助手可见、虚构开发材料，不是独立或未暴露确认集。6底题（数值、类别各3）×3问题（两个世界同为是、同为否、答案不同）×4条件（单甲、单乙、双来源、双候选）=72次独立会话。每个底题的两个具体世界不变；双条件为两套完整文本，不能将差异归因给单词。每族两种来源顺序按2:1排列而非完全平衡；底题少、任务形式简单，不证明自然RAG或整体泛化。单世界与双世界的措辞不完全相同，不把二者差异解释成冲突的单因素因果效应。

[独立文本解析核验](../../../scripts/query_determinacy_dev_audit.py)从实际输入解析值、比较阈值或集合成员，逐条检查72个参照、两世界条件、18组四条件和问题一致性；与[材料构造器](../../../scripts/query_determinacy_dev_material.py)实现分离，但两者均由同一知情助手开发，不是独立语义审核。存储顺序world_a/b与资料甲/乙在部分题反转，评分时须按实际文本值映射。[合同](CONTRACT.md)为评分来源，其 SHA-256 `843de1f30d2d688e7e801506b6e9383c28c40a779e1c1e17d80ac0c5226bd53e` 记录在本文，运行器本身不检查合同文件；合同如需修订应另存版本并披露。

## 冻结与检查

[清单](manifest.json) SHA-256 `7309be6174b484ccd9307a7f369d1cc67777b5a2643bebadba01b01b3cdf86a5`；材料 SHA-256 `e7ebfe398e24521d5c5a47e37731109246fd5191df8a9938dd759200c62e78b8`。固定随机种子19517；模型 Qwen2.5-3B-Instruct、原生聊天模板、独立user消息、greedy、最多384新token、BF16、SDPA；明确要求简短回答，与旧先导提示不同，不能把两批差异直接归于任务。72个真实渲染输入为78–115 tokens。CPU重建清单逐项相同，7个模型文件散列与既有快照一致，未加载权重或检查GPU。运行前会重新校验材料、依赖、模型文件及设备。

4项新CPU测试通过：真实材料与重建一致、篡改参照被拒、72条模拟生成含一次截断留痕且不重答、未提交attempt阻断及smoke失败阻断。复用的先导自动继续组件2项测试通过。当前只读 inspect 为0 attempts/0 records、valid_prefix；模拟不代表真实GPU成功。每条真实输出记attempt、token、文本与哈希。前4条是预定技术smoke且计入72，任何一条空或无EOS时保存后停止；后续空或无EOS保存凭据并继续，不自动重答或作为语义判断；结构性错误及未提交attempt停止。恢复前完整验证已存前缀；不要删除或手工修改运行目录。

## 用户执行

在项目所在机器执行：

```sh
cd '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG' && CUDA_VISIBLE_DEVICES=0 /large_disk/wf/miniconda3/envs/kba-rag/bin/python scripts/query_determinacy_dev_run.py collect
```

启动前确保GPU 0无其他计算任务。入口检查实时设备进程、单可见CUDA及bf16，但不能保证运行期间独占。预计建议预留20–45分钟：仅根据旧先导运行准备经验对更短的72条作保守规划，不是实测保证；模型加载、最长384 token、设备和故障会影响时间。运行中逐条打印进度；目录是本地 `runs/qwen2.5-3b-query-determinacy-development-v1/`，不会由Git自动备份。完成或报错请告知助手，助手先核验attempt、记录、输入/token和失败，再按知情评分合同分析；请勿删除run或重答。普通中断如有未提交attempt会阻断自动恢复，应先检查而非反复启动。

本轮无真实GPU、模型前向、回答、评分或拟合。原v1/E1-r1 gate=false、正式独立批准0、正式标签null、原拟合预算0、380正文封存；开发探索不冒称确认。

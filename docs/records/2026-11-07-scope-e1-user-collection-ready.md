# 2026-11-07：E1用户执行版完成审查并准备运行命令

时间与时区：2026-11-07，Asia/Shanghai。状态：用户执行版已完成条件性放行审查，尚未开始真实采集；操作者：助手完成CPU准备，GPU由用户运行。

## 用户要求与决定

用户明确要求提供命令，由用户运行后助手继续后续任务。按照既有“GPU工作由用户运行”约定，完成独立的[E1用户执行协议](../explanation_scope_e1_user_collection_20261107.md)、[代码门禁审查](../explanation_scope_e1_user_collection_gate_review_20261107.md)、[固定计划](../review/2026-11-07-explanation-scope-e1/user-collection-plan-v1.json)和[单版本release](../review/2026-11-07-explanation-scope-e1/user-collection-release-v1.json)。用户直接请求运行构成本次单版本执行依据；助手的研究和执行决定有历史暴露，不能称独立审评或人工金标准。原v1及原E1-r1门禁仍关闭。

## 运行约束与检查

新[用户执行器](../../scripts/explanation_scope_e1_user_collection.py)仅在单独计划、协议、用户执行补充、源码、测试证据和审查哈希全部一致时接受`collect`；不更改旧E1代码或用命令行开关绕过旧门禁。固定独立目录`runs/qwen2.5-3b-explanation-scope-e1-user-v1`；用户执行前重新核对GPU 0的UUID、七个模型文件SHA、计算进程、CUDA与bf16，GPU忙/文件不符时不创建新run。用户此前报告RTX3090且当时空闲是时点证据；首次真实模型/Transformers/CUDA兼容性需在正式命令内检验，无法由本轮CPU测试证明。

严格48条及原固定顺序，前四S/I0/IU/CT是计入总数的smoke；每槽一次attempt，全程空或截断保存后停止，异常/未提交attempt保留且不重答。新执行器提供CPU `inspect`/`package`，助手在用户报告结束后先验证保存记录和来源，再处理评审；公开材料可全文匹配条件，随机ID不能认证盲化。

真实tokenizer及临时synthetic CPU假模型测试8项17.453秒exit 0，覆盖release缺失/篡改阻断、旧门禁仍关闭、GPU忙不建run、UUID检查、48记录合成、第五条空输出停止及重启不触GPU/模型、完成与部分缓存转包、评分接收兼容；见[测试证据](../review/2026-11-07-explanation-scope-e1/user-collection-test-evidence-v1.json)。release创建前实际调用用户版`collect()`被拒绝且未创建run；审查完成后仅调用CPU验证，release与固定计划一致、旧E1仍拒绝、用户run目录不存在。用户版正式研究门禁有条件放行，但GPU就绪必须在用户启动时实时检查，不能把旧设备快照说成当前GPU已预留。

## 需用户执行的命令

```sh
cd '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG'
CUDA_VISIBLE_DEVICES=0 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/explanation_scope_e1_user_collection.py --stage collect
```

这是唯一固定48槽的正式采集入口，不是额外GPU试验。用户执行后告知助手；如失败、空/截断或中断，不删除目录、不手动补答或重复运行，先交助手检查。无GPU前向在助手本轮进行；48真实回答仍0、独立批准0、拟合预算0、正式标签null、380题封存。release、源码、协议及计划变更均导致绑定失效；须重新审查，不能只改标志。按长期约定记录后提交推送，实际提交与远端以Git和回复为准。

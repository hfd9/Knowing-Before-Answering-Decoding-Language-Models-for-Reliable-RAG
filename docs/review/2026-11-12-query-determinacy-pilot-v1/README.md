# 查询可判定性探索先导：材料核验与用户运行入口

2026-11-12，Asia/Shanghai。状态：`prepared_not_started`；144 条均未生成或评分。用户提供的解压材料位于 `docs/查询可判定性_探索先导包/`，是已暴露的虚构开发集，不涉及封存题；原材料在当前工作区保留、未纳入本次提交。清单和哈希见[冻结清单](manifest.json)。

## 材料检查

[只读复算脚本](../../../scripts/query_determinacy_material_audit.py)解析实际题面数值、单位、大小关系及代码规则表，独立计算甲乙分支及参考答案，逐条核对 144 行。12 底题、每题 3 问，共 36 问：是、否、无法唯一确定各 12；数值比较与类别规则各 18 问。36 组双来源对的完整提示逐字比较后，每组均恰好把两处“登记值”改为“候选值”；72 条单来源均按同一来源、值、规则与问题重建匹配。每个底题除问题外材料相同；每任务族甲乙/乙甲顺序各 3 底题，分歧问题中甲分支是/否各 3。以上是同项目知情规则复算，不是独立盲评。

`README.md` SHA-256 `5194a3c44b7ee8b12c8d3366fab8953958e74f48c4e09b17b9699f39302b5563`；`prompts.jsonl` `8eee52a6b7d6dfc43e82d34877db727bc7b1824bdfdcba94eb4ad0e48a5848f1`；`key.csv` `088bf3a2cbbb880840cb287b3c3c5470c8873d026e21c3baae5aef393067b95e`。未收到原 ZIP，故只绑定现有三个文件，不推断原 ZIP 字节。

## 固定执行设置

[新运行器](../../../scripts/query_determinacy_pilot.py)使用本地 Qwen2.5-3B-Instruct、原生 chat 模板、greedy、1 beam、BF16、SDPA、最多 128 新 token；不提取 probe 或拟合。每个独立会话只将材料包的 `prompt` 放入 user 消息，不拼接旧 E1 的额外 system 指令或评分答案。Qwen 模板自动添加 `You are Qwen, created by Alibaba Cloud. You are a helpful assistant.` 作为默认 system 消息；该包装及实际 prompt/token 哈希纳入清单，对全部条件相同。

固定种子 42 排序；首四条 smoke 覆盖两题型、双/单来源和可判定/分歧，计入 144 条。每条生成前写入 attempt；保存 token、文本和绑定信息后重验完整前缀。空输出、非 EOS 截断、未提交 attempt、材料/实现/模型文件指纹变化、异常文件或其他错误均停止并保留现场，不自动重答；有效前缀方可恢复。缓存一致性不独立认证 GPU 独占或输出全部来源。

真实本地 tokenizer 对 144 条完整渲染的输入长度为 85–165 tokens，均满足 32768 上下文及 128 输出余量。本地 7 个模型文件 SHA-256 均匹配既存快照；本轮没有加载权重或检查 GPU。Python 3.11.15、torch 2.5.1+cu121、transformers 4.56.2。9 项 CPU 测试通过，含真实材料只读核验及参考篡改拒绝、合成单条与 144 条生成/写入/重放、未完成 attempt、截断与输出篡改。模拟生成不证明真实 GPU 可运行。

清单 SHA-256 `9c815e26d0038617cb4eeac4faf3974248a38ab6b83c0b66a84fbc1decad125e`，与运行目录副本一致，再次从材料、tokenizer及模型文件重建的清单逐字节相同。只读 inspect：0 attempts、0 records、144 总数、有效空前缀。运行产物是忽略的本地目录，不随 Git 备份；材料和运行器必须保持不变。

## 用户执行

在该工作区所在机器执行（确保 GPU 0 没有其他任务）：

```sh
cd '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG' && CUDA_VISIBLE_DEVICES=0 /large_disk/wf/miniconda3/envs/kba-rag/bin/python scripts/query_determinacy_pilot.py collect
```

入口先核对指纹，再通过 `nvidia-smi` 检查设备上无计算进程，检查单可见 CUDA 设备与 BF16；检查不构成独占预约。预计请预留 30–60 分钟，实际取决于设备负载和输出长度；历史 E1 的 48 条生成累计约 6.1 分钟，简单乘 3 为约 18.4 分钟，仅作粗略参照，不含加载且不能保证新任务耗时。每条输出一行进度；前四条成功后自动继续。终止、报错、空输出或截断时保留目录，不自行删除或重答，告知助手输出；完成后也告知助手，先核验 144 条再进行知情语义评分和配对分析。

可用下列只读命令查看当前缓存：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python scripts/query_determinacy_pilot.py inspect
```

该先导由用户明确授权，不改变原 v1/E1-r1 门禁、正式独立批准 0、正式标签 null、原拟合预算 0 或 380 正文封存。它不测检索系统，不能据此证明隐藏机制或总体性能。

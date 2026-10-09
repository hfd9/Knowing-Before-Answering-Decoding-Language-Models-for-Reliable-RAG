# 提示词三分类基线

本轮在已经完成的 Qwen2.5-3B 隐藏状态路由器实验上补充直接三分类提示词对照。
使用相同模型、相同 300 条测试实例、完整五篇文档及原有顺序，不重新抽样。
提示词不读取真实标签或 gold_answer；真实标签只用于评估。

## 2026-10-09 实际运行与补充分析

用户已完成 9 条冒烟验证及 300 条正式测试推理。模型普遍先输出类别，再追加解释，
原完整输出解析器将全部 300 条记为 invalid。因此原 comparison.md 的 0% 反映格式不符合要求，
不能直接解释为分类能力为零。

原始 predictions.json 和原评估文件保留，新增独立 CPU 补充分析入口：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python scripts/analyze_prompt_baseline.py
```

只接受首个非空行中的单一类别词；后续解释不影响类别。
同一行的 answer conflict 等多标签仍为 invalid，不按真实标签或解释内容推断类别。
这是运行后变更解析口径的补充分析，报告明确记录 post hoc；没有重跑 GPU 或改动原始输出。

最新可读报告在 runs/qwen2.5-3b-prompt-baseline/first_line_analysis/comparison.md，
配对结果、原输出格式遵从率及全部错误位于同目录的 JSON 文件。

| 方法 | Accuracy | Macro-F1 | FAR | 无法解析 |
| --- | ---: | ---: | ---: | ---: |
| 隐藏状态路由器 | 80.67% | 80.54% | 10.00% | 0 |
| 提示词基线，首行解析 | 50.00% | 39.93% | 31.50% | 1 |

原完整输出格式遵从率为 0%，首行解析覆盖率为 99.67%。
100 条 conflict 中提示词基线仅 1 条正确，57 条预测 answer、42 条预测 refuse；
路由器 conflict 召回率为 87%。当前提示词基线是纯文本输入、8-token 输出预算设置，
不能代表更强的 chat-template 或其他提示词基线。
后续应在验证集检查指令模型的 chat-template 输入与输出约束，再明确冻结评估设置。
测试集结果已经查看，后续任何调整需保留这一实验历史。

## 运行

在项目根目录执行，入口自动使用 kba-rag Python 和 configs/local.env，无需手动激活：

```sh
cd '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG'
sh scripts/run_prompt_baseline.sh
```

默认完成长度检查、逐条推理、指标计算和路由器对照。CPU 检查可以先单独执行：

```sh
sh scripts/run_prompt_baseline.sh --stage check
```

该检查验证数据与模型指纹，使用本地 tokenizer 检查全部输入长度，不加载模型权重、不执行 GPU 推理。
首次 GPU 验证可先跑 3 个问题 / 9 条实例，使用独立目录：

```sh
sh scripts/run_prompt_baseline.sh --limit_questions 3 --run_dir runs/qwen2.5-3b-prompt-smoke
```

冒烟指标只检查流程，不能代替正式 300 条结果。正式实验不加 limit_questions。
运行中逐条打印进度，首次加载模型及长输入可能需要等待。

后台运行并留存日志，可使用：

```sh
mkdir -p runs/qwen2.5-3b-prompt-baseline
nohup sh scripts/run_prompt_baseline.sh > runs/qwen2.5-3b-prompt-baseline/run.log 2>&1 &
tail -f runs/qwen2.5-3b-prompt-baseline/run.log
```

每完成一条，predictions.json 会原子保存全部已完成记录。中断后使用相同命令续跑，
完成的实例会跳过；未完成的当前实例重新生成。目录有进程锁，避免同时写入。
变更模型、指令、脚本、生成设置或样本范围，需要使用新的 run_dir。

仅重做分析，无需 GPU：

```sh
sh scripts/run_prompt_baseline.sh --stage analyze
```

如要在验证集检查其他设置，必须使用独立目录，例如：

```sh
sh scripts/run_prompt_baseline.sh --split val --run_dir runs/qwen2.5-3b-prompt-val
```

当前指令预先固定，没有依据测试结果调优。后续指令或参数选择应只使用验证集。

## 设置与指标

- 模型与路由器相同：本地 Qwen2.5-3B-Instruct，BF16、SDPA、batch size 1。
- 保留 P0 的文档格式与问题位置，改用明确三分类指令及 Label: 后缀，无 chat wrapper。
- 输出 answer、refuse 或 conflict；贪心解码、单 beam，最多 8 个新 token。
- 不截断文档；输入长度加输出预算超过上下文窗口时停止。
- logits_to_keep=1 仅计算生成所需的最后一个位置 logits，避免长输入的全位置词表 logits 分配。
- 输出只接受单个类别词（大小写、首尾空白与末尾句号/感叹号可容忍），解释文字或多标签计为 invalid。
- Accuracy 使用全部实例作为分母；Macro-F1 在三类上计算，invalid 计入相应真实类别的假负例。
- FAR 与路由器同定义：真实 refuse/conflict 中明确预测为 answer 的比例。
  invalid 不计作 answer，需同时报告解析覆盖率及不应回答实例中的 invalid 数量。
- 对照按 ID 核对，输出两者都正确、仅基线正确、仅路由器正确、两者都错误四类。
- 准确率差提供按原始问题配对的 10,000 次 bootstrap 区间，保留每个问题的三个实例。
  区间基于固定模型，不包含训练随机性。

这是直接标签预测基线，尚未评价实际生成答案，也不等同于原论文全部生成基线。
提示词任务与隐藏状态提取的原始 P0 回答任务不同，应明确记录这一差异。
运行耗时统计是逐实例分词与生成时间之和，不包括模型加载、结果落盘和分析。
3090 上长输入生成的峰值显存与先前隐藏状态提取可能不同；失败会保留已完成记录。

## 结果

默认目录：runs/qwen2.5-3b-prompt-baseline。

| 文件 | 内容 |
| --- | --- |
| preflight.json | 输入长度、类别数量和已有进度 |
| predictions.json | 实验指纹、原始输出、解析类别、长度、逐条耗时及峰值显存 |
| metrics.json | 基线准确率、Macro-F1、FAR、解析覆盖率及 3×4 混淆矩阵 |
| comparison.json | 与相同测试实例上的路由器配对比较、准确率差及区间 |
| comparison.md | 可直接阅读的对照表 |
| errors.json | 任一方法出错的实例、问题、预测及错误类别；val 仅列基线错误 |

实际测试实例仍位于 runs/qwen2.5-3b-small/data/instances_test.jsonl；没有复制或修改原始数据。
完整证据可根据 errors.json 的 ID 回查该 JSONL。
验证集没有保存的路由器逐实例预测，因此 val 仅输出基线分析。

## 准备工作验证

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -m unittest discover -s tests -v
```

测试覆盖完整证据与标签隔离、严格解析、invalid 指标分母、续跑完整性、模拟中断后继续生成、配对分析，
以及小型随机 Qwen2 CPU 模型的生成接口。GPU 实验由用户启动后验证。

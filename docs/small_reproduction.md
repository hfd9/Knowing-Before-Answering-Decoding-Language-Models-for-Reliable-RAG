# 小规模隐藏状态路由器复现

环境：kba-rag；模型：本地 Qwen2.5-3B-Instruct；提示词：P0。
大模型参数冻结，训练各层的线性三分类探针，在验证集选层并做 sigmoid 校准，最后评估测试集。

## 开始运行

在项目根目录运行。已经激活环境也可以使用下面的 sh 入口：

```sh
cd '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG'
sh scripts/run_small_repro.sh
```

该命令自动使用专用 Conda Python、本地模型路径、GPU 0 和离线加载。
从其他目录调用时使用入口的绝对路径。

默认按问题抽样，随机种子 42，并保留同一问题的三个证据配置：

| 集合 | 问题数 | 实例数 | 每类实例数 |
| --- | ---: | ---: | ---: |
| train | 200 | 600 | 200 |
| val | 95 | 285 | 95 |
| test | 100 | 300 | 100 |
| 合计 | 395 | 1,185 | 395 |

输入来自仓库的 dataset/instances.zip，保持原始 train/val/test 划分。
抽样数据已准备在 runs/qwen2.5-3b-small/data，无需手动解压。

## 分阶段运行与继续

```sh
sh scripts/run_small_repro.sh --stage prepare
sh scripts/run_small_repro.sh --stage extract
sh scripts/run_small_repro.sh --stage probe
sh scripts/run_small_repro.sh --stage router
```

默认的 all 会依次执行上述阶段。提取完成的 split 会验证缓存后跳过；
某个 split 提取中断时，重新运行会从该 split 开头开始。
失败样本会报告实例 ID 和 token 数并中止，不会用全零行代替。
抽样参数改变时使用新的 --run_dir，避免覆盖或混用不同实验。

## 结果位置

默认输出目录是 runs/qwen2.5-3b-small：

- data/manifest.json：数据来源摘要、抽样设置、样本 ID、类别数量和文件哈希。
- activations/H_P0_{train,val,test}.npy：各层最后一个提示词 token 的隐藏状态。
- activations/meta_P0_{train,val,test}.json：模型和提示词指纹、输入长度、耗时和显存记录。
- results/layer_probe_hidden.json：逐层验证集准确率与 Macro-F1。
- results/best_hidden_probe.pkl：根据验证集准确率选择的线性探针。
- results/router_hidden_dev.pkl：路由器、标准化器和所选层。
- results/router_metrics.json：测试集 Accuracy、Macro-F1、FAR、混淆矩阵。
- results/router_test_predictions.json：逐实例的真实类别、预测类别与三类概率。

混淆矩阵的行是真实类别、列是预测类别，顺序为 answer、refuse、conflict。
FAR 的分母是所有真实 refuse/conflict 实例，分子是其中预测为 answer 的实例。
测试标签不参与选层、训练和概率校准。

## 验证与资源设置

用于检查全流程的 27 条真实实例：

```sh
sh scripts/run_small_repro.sh --run_dir runs/qwen2.5-3b-smoke \
  --train_questions 3 --val_questions 3 --test_questions 3
```

这个规模只验证运行衔接，不能据此判断论文结论或报告可靠的准确率。

```sh
python -m unittest discover -s tests -v
```

检查覆盖完整证据保留、按问题保留三类实例，以及拒绝标签错序和模型不匹配的缓存。

## 实验设置与复现范围

原仓库未发布 prompts.py。本地版本按发布的 P0--P5 JSON 重建纯文本提示，
保留完整文档、原有文档顺序和文档编号，不增加 chat wrapper。
因此应记录 render_policy，而不能宣称提示词渲染细节与作者内部版本完全一致。

隐藏状态遵循原代码的索引：H[i,l] = hidden_states[l+1][0,-1,:]。
提取使用 BF16 模型、FP16 特征存储、SDPA，不返回完整注意力矩阵。
直接调用 decoder 避免分配每个输入 token 的全词表 logits，隐藏状态定义相同。
输入超过模型上下文长度时中止，保留三分类标签所依据的完整证据。

这一轮完成隐藏状态路由器实验。MLP/注意力特征对照、生成基线、
因果替换实验和全量论文模型比较可在主流程验证后扩展。
Qwen2.5 和仓库发布数据用于方法流程复现；严格对齐论文数值还需确认论文模型及数据版本。

# 四条件分类与自由回答实验运行

所有 sh 入口自动使用 kba-rag、本地 Qwen2.5-3B-Instruct、configs/local.env 和 GPU 0。
从任何目录调用入口绝对路径均可；下面命令在项目根目录执行，无需手动激活 Conda。
详细固定协议见 [evidence_behavior_plan.md](evidence_behavior_plan.md)。

```sh
cd '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG'
```

## 先跑分类对照

9 条验证实例和 9 条测试实例的四条件 GPU 冒烟验证：

```sh
sh scripts/run_classification_grid.sh --limit_questions 3 --run_dir runs/qwen2.5-3b-classification-grid-smoke
```

成功后跑正式分类对照，默认先 val 后 test：

```sh
sh scripts/run_classification_grid.sh
```

正式新增 2,040 次生成：val 的四条件共 1,140 条；test 的三种新条件共 900 条。
test/plain8 复用此前 300 条原始输出，仅做验证和新报告，不重新生成。
默认每个条件分别保存，不覆盖历史实验。
首次模型加载和长输入可能需要等待，之后逐实例打印 condition/split/进度/类别。

只做 CPU 检查与审计：

```sh
sh scripts/run_classification_grid.sh --stage check
```

默认输出目录：runs/qwen2.5-3b-classification-grid。

| 文件 | 用途 |
| --- | --- |
| protocol.json | 推理前固定的指令、解析口径、条件、样本与代码/模型指纹 |
| preflight.json | 两种格式的输入长度和输出预算检查 |
| audit.json | 数据泄漏、特征完整性、原路由器选择依据和保留确认集 ID |
| plain8/val 等目录下的 predictions.json | 每种条件每个集合的原始输出及续跑记录 |
| reports/test.md | 五种方法指标表、各类 P/R/F1 和全部混淆矩阵 |
| reports/test.json | 配对 bootstrap 差值与完整结构化结果 |
| reports/test_per_class.csv | 分类型指标表 |
| reports/test_errors.json | 方法间分歧与错误实例 |
| reports/val.* | 对应验证集报告；原路由器 val 是校准内评估 |

仅重做报告，无需 GPU：

```sh
sh scripts/run_classification_grid.sh --stage analyze
```

阶段支持 all/check/audit/infer/analyze。可用 --splits val 或 --conditions chat8 chat64 只运行特定部分；
完整四条件报告使用默认条件。切勿变更原始数据、指令或代码后继续写同一目录。

## 然后跑自由回答

先完成分类对照并核对结果，再运行以下命令。
每种输入格式都会重新训练对应自由回答提示的探针，旧 L24 探针不直接迁移。

全流程 GPU 冒烟：每个集合 3 底题/9 实例，plain 和 chat 两种格式：

```sh
sh scripts/run_free_answer_study.sh --limit_questions 3 --run_dir runs/qwen2.5-3b-free-answer-smoke
```

正式实验：

```sh
sh scripts/run_free_answer_study.sh
```

两个格式各提取 train 600/val 285 状态、扫描所有层并校准，随后各生成 test 300 条回答，预算 128 tokens。
生成时在首次 prefill 的首个输出 logits 前做出探针预测，探针结果不会改变生成过程。
默认共生成 600 条自由回答；训练/验证阶段只有前向提取。

分阶段入口：

```sh
sh scripts/run_free_answer_study.sh --stage check
sh scripts/run_free_answer_study.sh --stage extract
sh scripts/run_free_answer_study.sh --stage probe
sh scripts/run_free_answer_study.sh --stage generate
sh scripts/run_free_answer_study.sh --stage analyze
```

默认输出目录：runs/qwen2.5-3b-free-answer-study。

| 文件 | 用途 |
| --- | --- |
| protocol.json、preflight.json | 固定协议与所有集合长度检查 |
| plain/train/states.json 等 | 逐实例状态及特征哈希的续跑清单 |
| plain/train/features/*.npy 等 | 同模板、生成前各层状态 |
| plain/probe/probe.json、probe.pkl | 逐层验证结果、所选层与校准探针；chat 独立保存 |
| plain/test/predictions.json 等 | 原始回答、生成前探针类别及概率、特征和长度记录 |
| review/blind_review.html | 离线盲审页面，不联网，不显示真实类别、探针预测和格式条件 |
| review/annotations_template.csv | 可手工编辑的空标注模板，带本批次哈希 |
| reports/behavior.md、behavior.json | 行为计数与比例；未审核时明确显示待审核及上下界 |
| reports/joined_records.json | 对齐的真实类别、探针预测、回答和行为标注 |

## 审核行为后再计算最终比例

在浏览器打开本地 review/blind_review.html，按问题、证据与原始回答进行标注。
可导出进度 JSON 并在页面导入恢复；页面也尝试用浏览器本地存储保留进度。
点击“导出 annotations.csv”，将文件放到：

```text
runs/qwen2.5-3b-free-answer-study/annotations.csv
```

也可以复制 review/annotations_template.csv 为上述 annotations.csv 后编辑。
不要修改 item_id 或 review_manifest_sha256；每个行为字段使用 yes/no/unknown，已做判断须填 reviewer。
不要把其他批次的标注文件用于本批输出。

然后执行：

```sh
sh scripts/run_free_answer_study.sh --stage analyze
```

也可用 --annotations 指定标注文件的绝对路径。
空输出、截断或不确定项应保留 unknown；报告用完整分母给出上下界，不能把未知项当拒答。
生成结束后可让助手检查输出并协助标注，再计算最终行为结果。

## 日志与续跑

两阶段均逐实例原子保存，并有目录锁。中断后重新执行相同命令，会校验并跳过已完成实例。
失败会报告实例并保存 last_failure.json；不会用零状态或默认拒答代替失败。
CLI 支持 --formats，但完整自由回答对照使用默认两种格式；需要只研究单一格式时使用独立目录，避免混用盲审批次。

分类后台日志示例：

```sh
mkdir -p runs/qwen2.5-3b-classification-grid
nohup sh scripts/run_classification_grid.sh > runs/qwen2.5-3b-classification-grid/run.log 2>&1 &
tail -f runs/qwen2.5-3b-classification-grid/run.log
```

两个完整实验不要同时占用同一张 GPU；先完成分类，再执行自由回答。
本轮入口不生成保留确认集预测，不实施干预，不自动提交或推送 Git 更新。

## 代码验证

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -m unittest discover -s tests -v
```

测试覆盖原提示词复用、原生 chat 分词、完整证据和标签隔离、分类型与 invalid 指标、配对底题 bootstrap、
生成前状态与 HF 状态一致、探针回调在 logits 前执行、缓存损坏、四条件报告和盲审批次/未知分母。

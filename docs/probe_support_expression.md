# 支持事实表达、冗余否定与同步答案值诊断

承接[文档三因素完成核验](records/2026-10-20-probe-document-factors-verified.md)：此前尾句、背景集合和一个整体循环顺序均未翻转十个底题的读出。本轮进一步检查支持事实本体的表达，而不继续扩大背景/顺序网格。冻结Qwen2.5-3B-Instruct、chat自由回答指令、L28 scaler/router，只做decoder prefill，不生成答案、不训练或调阈值。

2026-10-20已完成[正式50+smoke12完整核验与九组分析](records/2026-10-20-probe-support-expression-verified.md)：两次只读verify exit0、各30实现/16来源匹配、两桥接误差0、12跨运行同输入数组/概率完全一致。正式末条12:38:12；独立60配对与报告一致，全部九组0类别翻转，val_81始终answer、另九题始终conflict。增加冗余否定两表达各6/6概率上升，均值+7.38/+8.84pp；整个目标包换核心均值−6.72/−11.06pp，仍无类别翻转。不能据此认定否定或长度根因，没有新行为率。当前无需重跑GPU，下方启动命令保留为复现/续跑说明。

准备时新增9项CPU55.940秒、最终全120项167.379秒通过，50/12真实tokenizer预检查、两目录prepared_only核验及独立重建/80编辑检查通过。459–2952tokens。此前prepared_not_started/GPU0及4–12分钟估时均为准备时历史快照。

## 固定材料与三项问题

保持同十个已暴露val底题的澄清问题、三篇完整S背景、原平衡槽位和重复文档。替换两个目标段，并将同一条件下的答案写入两段，避免只改一段制造证据矛盾。

| 组别 | 范围 | 输入数 | 作用 |
| --- | --- | ---: | --- |
| B旧端点 | 十题 | 10 | 精确复用上一轮C/S/0输入和状态，作为来源与目标段整体变化的参照 |
| D0/P0 | 十题×两种表达 | 20 | 直接陈述／同义改写，保留作者答案、必要范围与排他关系 |
| D1/P1 | 六题×两种表达 | 12 | 在对应D0/P0末尾逐字加一条冗余否定；原正面或排他前提完整保留 |
| DX/PX | 四题×两种表达 | 8 | 模板不变，仅将两目标中的人名或日期同步换为预定替代值 |

正式50输入=40新前向+10精确缓存复用。六个否定题固定为val_14、val_3、val_31、val_28、val_17、val_13；四个值替换题固定为val_81、val_35、val_31、val_86。这些子集在新GPU前固定，分别分析，不拿四题分布直接与十题比较。

四对值为Christian Wulff→Joachim Gauck、12 April 1993→23 September 1996、Elton John→Andrew Lloyd Webber、Selena Gomez→Cristiano Ronaldo。它们来自此前作者充分／冲突构造的两个值，两段同步换成替代值后仍按作者设定一致。**这些是给定材料中的反事实值，不是对真实历史的核验，也不把某值称为更真实或更熟悉。**

不对机场、动物等类别题直接换类别：例如固定背景已明确Tucson为公共机场，若两目标改成私人机场，会同时引入与背景的真实不一致。其他类别题同样保留其原类别，不通过背景清洗扩大值对照。

正面核心保留sole/only等必要排他或单一范围，特别是山／高原可能兼容，不能为删除not而丢失问题所需的明确分类。这里positive指“没有额外冗余否定后缀”，并不表示没有排他措辞。新增否定是对既有排他前提的重复陈述，仍会增加长度。

D/P之间保持新核心的问答命题，改变句法及措辞；DX/D0与PX/P0只替换既定值字符串。B→D0/P0改变整个目标段，并可能删去民航军用等附带事实、明确对应实体排他关系或改变词汇重复结构，**属于目标段整体变化，不能称纯措辞效应**。所有编辑、原始偏移、保留核心引文、来源/语义理由和暴露声明均封存。

## 固定的九组对照

方向均为左减右；完整十题／六题／四题分母保留，不按结果筛选。

| 对照 | 配对数 | 解释 |
| --- | ---: | --- |
| P0−D0 | 10 | 作者答案、无额外否定时的表达变化 |
| P1−D1 | 6 | 作者答案、增加否定后的表达变化 |
| PX−DX | 4 | 替代答案下的表达变化 |
| D1−D0 | 6 | 直接表达下增加冗余否定 |
| P1−P0 | 6 | 改写表达下增加冗余否定 |
| DX−D0 | 4 | 直接表达下同步改值 |
| PX−P0 | 4 | 改写表达下同步改值 |
| D0−B | 10 | 直接核心与旧完整目标段包的差异 |
| P0−B | 10 | 改写核心与旧完整目标段包的差异 |

共60配对行，仍只有十个重复使用的底题，不作60个独立样本。报告类别、三概率及token差；不选“最佳”条件，不报告新accuracy、回答／拒答／选边率或语义置信度校准结果。

另仅对固定train600/200底题，按发布构造类别统计人名／日期／类别值及not/no/sole/only等词的字面出现行数和文档槽数。该CPU描述不建立命题蕴含、预训练记忆、真假、分布外检测或根因；不使用当前测试或380保留确认题，不以词频调参。

## 用户启动与技术门槛

准备检查和耗时估计见[准备记录](records/2026-10-20-probe-support-expression-preparation.md)。按既有约定由用户启动GPU：

```sh
sh scripts/run_probe_support_expression_review.sh
```

先固定val_31和val_35的全部条件，共12条smoke，覆盖音乐唯一署名、冗余否定、日期与答案替换分支；选择不依赖新探针输出。包含两个旧B端点重新计算，沿用逐层相对L2最大≤0.02、概率最大绝对差≤0.01。通过状态形状/有限/非零、提示/token、冻结来源等技术检查后，才自动开始正式50条。门槛不看语义准确率或期望输出。

整个入口52次新前向（12smoke+40正式），0条新生成；两个阶段分别加载模型。GPU活动保护在模型加载前运行，不停止其他进程。逐行原子保存、缓存严格校验和锁保护齐全，中断后用同一命令续跑；若smoke失败先诊断，不改旧协议或指纹绕过检查。

正式目录runs/qwen2.5-3b-probe-support-expression-v1，smoke目录runs/qwen2.5-3b-probe-support-expression-smoke-v1。入口日志在正式目录launch/smoke.log与launch/full.log；last_failure.json记录失败实例。

## CPU准备和完成后核验

```sh
sh scripts/run_probe_support_expression.sh --stage prepare
sh scripts/run_probe_support_expression.sh --stage prepare --smoke --run_dir runs/qwen2.5-3b-probe-support-expression-smoke-v1
sh scripts/run_probe_support_expression.sh --stage verify --prepared_only
sh scripts/run_probe_support_expression.sh --stage verify --prepared_only --smoke --run_dir runs/qwen2.5-3b-probe-support-expression-smoke-v1
```

准备仅加载模型配置、真实tokenizer和旧探针／源状态，模型权重不加载GPU。完成后执行只读核验：

```sh
sh scripts/run_probe_support_expression.sh --stage verify --smoke --run_dir runs/qwen2.5-3b-probe-support-expression-smoke-v1
sh scripts/run_probe_support_expression.sh --stage verify
```

verify不写锁、缓存、来源或报告；核验协议/材料/封存、全部提示/token、状态/哈希、来源复用、三概率与类别、九组对照、train字面计数和smoke技术门槛。设置有变更时使用新的protocol/run_dir。

产物：protocol.json、preflight.json、materials/inputs.json、target_edits.json、semantic_review.json、review_seal.json；reports/cached_endpoints.json、train_lexical_counts.json；GPU完成后才有states.json、features/、reports/diagnostic.json、smoke_gate.json（smoke）。runs被Git忽略，持久记录只保存必要的轻量材料、指标与校验值。

所有材料与旧结果有当前助手暴露，旧probe的选层/校准也使用这些题所在val；全文语义复核属于作者检查，不是独立金标准或确认。措辞／否定仍改变长度，人名／日期仍改变tokenization及内容；不会因观察到翻转就自动归因某词、模型自知或内部因果使用。本轮不做patching。

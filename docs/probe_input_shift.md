# 冻结探针对输入变化的敏感性诊断

本轮承接[40条行为复核](records/2026-10-20-controlled-evidence-pilot-behavior.md)。首要问题是为什么10条作者充分S材料中有9条被原chat L28探针判冲突，而实际回答全部有据正确。

**2026-10-20当前状态：正式52和smoke6已由用户完成，两套完整只读verify及独立计数/58配对通过，无需重跑GPU。** 末条11:47:24，两数值桥接误差0、六组smoke/full同输入状态与概率完全相同。结果：问题与文档包均影响读出，文档包对应平均变化更大；六题删除重复否定各自降低conflict概率，但两问题条件下均0/6类别改变。根因仍未分离，不新增accuracy或行为指标。详见[完成核验](records/2026-10-20-probe-input-shift-verified.md)、[JSON](records/2026-10-20-probe-input-shift-verified.json)及[52单元CSV](records/2026-10-20-probe-input-shift-cells.csv)；下述准备和启动说明为历史/复用参考。

2026-10-20准备完成：全102项CPU测试82.850秒通过，52正式/6smoke真实tokenizer检查及只读准备重放通过，各22实现/9源哈希，最大输入4137/32768。两目录prepared_not_started、GPU0；容量规划4–11分钟，建议预留10–20，非实测。详见[准备记录](records/2026-10-20-probe-input-shift-preparation.md)和[JSON](records/2026-10-20-probe-input-shift-preparation.json)。

已有CPU端点复算显示：同样10个底题在**原发布answer配置的完整文档与原问题**下，探针输出9 answer、1 refuse、0 conflict；在上轮作者S材料与澄清问题下输出1 answer、0 refuse、9 conflict。这里只描述读出分布，不把发布answer标签认证为真实语义充分，也不据两个同时改变多因素的端点判定根因。

## 固定对照及限制

使用完全冻结的Qwen2.5-3B-Instruct、原chat自由回答指令及chat L28探针，不训练、校准、选层或调阈值。新阶段只对提示做decoder前向，保存末位置36×2048 FP16状态；不调用语言模型生成头、不生成答案、不做隐藏状态替换，也不新增行为评分。

仍固定上轮10个已暴露验证开发底题，不使用test或保留380底题。O/A表示原问题/上轮澄清问题；文档O/P/N分别是原发布answer五文档、上轮S五文档、只删除两目标中指定重复否定片段的五文档。

| 单元 | 问题 | 文档 | 个数 | 状态来源 |
| --- | --- | --- | ---: | --- |
| OO | 原问题 | 原完整五文档 | 10 | 旧val缓存，逐提示与特征校验后复用 |
| AO | 澄清问题 | 原完整五文档 | 10 | 新前向 |
| OP | 原问题 | 上轮S五文档 | 10 | 新前向 |
| AP | 澄清问题 | 上轮S五文档 | 10 | 上轮S缓存，逐提示与特征校验后复用 |
| ON | 原问题 | S删除指定重复否定片段 | 6 | 新前向 |
| AN | 澄清问题 | S删除指定重复否定片段 | 6 | 新前向 |

共52单元，复用20，新前向32；另smoke将固定val_31全部6单元重算，因此整个入口预计38次新前向。6个N底题依据存在预先列明的片段选定，固定为犬种val_14、机场val_3、作曲者val_31、刊物val_28、地貌val_17、小说val_13；不从未来新输出选案例。

例如保留“Boykin Spaniel is described as a breed of dog”，只删除“, not a breed of cat”；作曲者仍保留“sole composer of all music”，只删除重复的“there are no other music composers”。全部12处Unicode删除偏移、保留正面事实的引文及作者解释写入新材料。两个目标同步删除，其他三篇全文、槽位、顺序和问题保持对应单元不变。N不等于去掉所有否定词，例如小说原版本范围中的“not stage adaptations”保留。

比较问题变化时固定文档；比较N与P时固定问题。O→P改变目标内容、干扰来源、顺序及部分反事实答案，**不是纯长度或简化对照**。原问题→澄清问题有时改变范围，也不能称纯措辞同义替换。删除N片段会改变长度，且“冗余”只相对于作者设定的分类轴/版本范围；不能宣称所有开放世界含义完全不变。两个已知端点已被查看，本轮假设是事后提出、随后为新单元固定，非全新独立确认。

## 用户启动、技术门槛与续跑

代码、CPU检查和冻结目录准备完成后，项目根目录执行：

```sh
sh scripts/run_probe_input_shift_review.sh
```

入口先做固定val_31的6次smoke，再自动跑正式52单元（其中20个复制已核验缓存）。不按语义准确率或类别决定是否通过。smoke中OO和AP是已知端点重算，用来检查当前纯前向提取和旧抽取/生成前状态的一致性：逐层相对L2最大值≤0.02，探针概率绝对差最大值≤0.01；其余检查非空状态、正确形状/FP16、无NaN/Inf/零层向量。任一失败立即退出，正式不启动，终端打印日志末尾。不能放宽门槛后续写原目录。

GPU加载前检查活动计算进程，忙则退出，不停止其他进程。逐单元原子保存，目录锁保护；原样重跑命令会校验已有状态后续跑。代码、指令、材料、模型或探针变化须新run_dir/protocol，不能改指纹绕过。正式运行还会重新读取smoke缓存并复算gate，而非仅检查gate文件存在。

默认正式runs/qwen2.5-3b-probe-input-shift-v1，smoke为runs/qwen2.5-3b-probe-input-shift-smoke-v1。日志在正式launch/smoke.log、launch/full.log。时长是preflight.json里基于十条旧原文prefill的elapsed/input-token最大比值、38次输入量、2倍/10倍余量及3/8分钟加载IO得到的容量规划；注意attention并非线性耗时，不是本轮GPU实测或完成保证。不能保证低于10分钟，按约定交用户运行。

## CPU准备与只读核验

```sh
sh scripts/run_probe_input_shift.sh --stage prepare
sh scripts/run_probe_input_shift.sh --stage prepare --smoke --run_dir runs/qwen2.5-3b-probe-input-shift-smoke-v1
sh scripts/run_probe_input_shift.sh --stage verify --prepared_only
sh scripts/run_probe_input_shift.sh --stage verify --prepared_only --smoke --run_dir runs/qwen2.5-3b-probe-input-shift-smoke-v1
```

以上不加载3B、不占GPU。prepare写新冻结材料/协议/真实tokenizer长度、已缓存端点CPU复算；verify默认只读，不写锁/报告。完成GPU后执行：

```sh
sh scripts/run_probe_input_shift.sh --stage verify --smoke --run_dir runs/qwen2.5-3b-probe-input-shift-smoke-v1
sh scripts/run_probe_input_shift.sh --stage verify
```

| 文件 | 含义 |
| --- | --- |
| protocol.json | 完整固定设计、实现/源缓存/模型指纹、暴露与解释边界 |
| materials/inputs.json、edits.json | 52/6输入与12处删除/保留事实引文，不设置语义gold |
| preflight.json | 逐条真实输入token、上下文检查、规划耗时 |
| reports/cached_endpoints.json | 旧缓存CPU读出，不是新GPU结果 |
| states.json、features/ | 新/复用状态的来源、逐提示哈希、概率、数组及哈希 |
| progress.json、last_failure.json | 0输出准备、运行进度及失败实例 |
| reports/diagnostic.json、smoke_gate.json | 七组配对方向、分单元类别分布/概率差/长度差；smoke技术校验 |

## 结果如何解释

问题效应分别在O/P/N文档上比较，文档bundle效应分别在O/A问题上比较，N删除效应只在固定六底题内配对。报告每题变化及完整分母，不将六题当十题、不报告新分类准确率、不根据结果挑层或新候选。

如果删掉重复否定片段后冲突读出下降，可认为这批输入的读出对该编辑敏感；长度变化等替代解释仍在。如果问题切换影响明显，仍需区分范围和措辞。如果只有O→P大幅改变而更小对照无法解释，根因仍未定位，不能自动归因文本变短或断言模型“知道却故意忽略”。本轮不消耗确认集、不自动patching，也不把开发诊断变成旧基线达标结果。

smoke的两个端点桥接误差会另存；小幅概率差需要结合实测数值误差评估，不能仅以差值正负判定稳定效果。

# 固定问题与回答事实的文档因素诊断

本轮承接[输入变化诊断](records/2026-10-20-probe-input-shift-verified.md)。此前原文档换作者S文档带来较大的探针冲突概率变化，但目标事实、干扰、顺序和长度混在一起。本轮固定同十个澄清问题及其作者S回答事实，只改变三个明确因素。材料仍为有历史暴露的验证开发样本，不是独立金标准或确认实验。

2026-10-20准备完成：全111项CPU测试110.241秒通过，正式80/smoke16真实tokenizer及准备只读verify通过，26实现/12源哈希匹配，输入482–3112/32768。两目录prepared_not_started、新GPU0；规划5–14分钟，建议预留10–20，非实测保证。详见[准备记录](records/2026-10-20-probe-document-factors-preparation.md)与[JSON](records/2026-10-20-probe-document-factors-preparation.json)。

## 三因素、八组合

| 因素 | 原条件 | 变更条件 | 保持不变的部分 |
| --- | --- | --- | --- |
| 目标段T | F：上轮完整目标A/B | C：仅删除指定结尾背景句 | 正面回答事实、否定/唯一性及时间/版本范围原文保留 |
| 背景B | S：原refuse五文档排序最短三篇 | L：同一排序最长三篇 | 两目标、问题、装配槽位规则；背景均整篇保留 |
| 顺序R | 0：上轮平衡目标槽位/原序 | 1：整个五文档列表左循环一位 | 问题和五篇文档的精确多重集，重复文档也保留 |

10底题×2×2×2=80单元。F/S/0十个输入与既有AP端点完全相同，经完整提示/token/状态哈希核验复用；其余70新前向。每个因素在另外两个因素的四种固定设置下分别比较，**12组预设对照，每组10底题，共120个配对行；不当成120个独立底题**。

T只测试指定背景尾句的删除，不代表已经比较自然与合成支持文本的全部措辞。全文/删减两条件都保留“not a cat”等既有明确分类与排他语句，区别于上一轮删除重复否定的诊断。共19个目标尾句删除：Instagram目标B的机构账号说明涉及范围，因此保留不删。所有删除偏移与保留回答事实引文保存，不自动删句或改写事实。

B使用单一升序(字符数,原槽位)排名，S取前三、L取后三；集合内部按原槽位排列。这样20个替代来源槽位经全文复核。部分有姓名或主题重叠，例如English White Terrier祖先信息、Serena/Shirley Williams；当前作者未发现与固定回答事实矛盾的内容，但不声称全都完全无关或获得独立语义认证。重复Jeopardy段落按来源原样保留。B同时改变内容、长度与重复结构，不把它解释成纯长度或纯干扰身份效应。

R同时改变绝对位置和线性阅读顺序，不声称只移动目标而其他位置不变。完整文档多重集逐单元比较，保证没有裁剪、丢失或意外去重。

## 运行与技术门槛

使用冻结Qwen2.5-3B-Instruct、BF16/SDPA、原chat自由回答指令与L28探针；只对提示做decoder前向、use_cache=False，保存36×2048 FP16末位置状态，不调用生成头，不训练/校准/选层/调阈值，不生成新答案或行为评分。

CPU准备与预检查完成后，在根目录运行：

```sh
sh scripts/run_probe_document_factors_review.sh
```

先固定val_94和val_35两个底题全部8组合，共16次smoke。它们在推理前的真实tokenizer检查中覆盖最长3112与最短482token单元，选择不依赖新探针结果。两个F/S/0已有端点重新计算：逐层相对L2最大≤0.02、概率最大绝对误差≤0.01，其余检查形状/FP16/有限/非零，不看语义准确率。

技术通过后自动执行正式80单元，其中70新前向、10源缓存复制；整个入口86次新前向、0条新生成。加载前GPU忙保护，失败即退出并打印日志末尾，不停止其他进程。逐行原子保存与锁保护，中断后原样重跑并严格校验缓存；smoke技术失败则先检查原因，不在原目录改指纹或放宽门槛。

正式目录runs/qwen2.5-3b-probe-document-factors-v1；smoke为runs/qwen2.5-3b-probe-document-factors-smoke-v1。日志为正式目录launch/smoke.log、launch/full.log。实际容量规划以preflight.json为准，基于上一轮31条不含模型加载的前向耗时、2倍/10倍余量并另加3/8分钟加载IO；attention并非线性，因此是估计而非本轮GPU实测。不能保证低于10分钟时按约定由用户启动。

## CPU准备与只读重放

```sh
sh scripts/run_probe_document_factors.sh --stage prepare
sh scripts/run_probe_document_factors.sh --stage prepare --smoke --run_dir runs/qwen2.5-3b-probe-document-factors-smoke-v1
sh scripts/run_probe_document_factors.sh --stage verify --prepared_only
sh scripts/run_probe_document_factors.sh --stage verify --prepared_only --smoke --run_dir runs/qwen2.5-3b-probe-document-factors-smoke-v1
```

准备只读取模型配置/tokenizer/旧探针和缓存，不加载3B模型或占GPU。verify只读，不改锁、源输入或报告。新GPU完成后助手执行：

```sh
sh scripts/run_probe_document_factors.sh --stage verify --smoke --run_dir runs/qwen2.5-3b-probe-document-factors-smoke-v1
sh scripts/run_probe_document_factors.sh --stage verify
```

| 产物 | 内容 |
| --- | --- |
| protocol.json、preflight.json | 固定因素、暴露/限制、模型/实现/来源指纹、逐输入长度与估时 |
| materials/inputs.json | 80/16个完整五文档输入及来源、槽位、复用端点 |
| materials/target_edits.json | 19个精确尾句删除、保留事实引文和偏移 |
| materials/background_review.json、review_seal.json | 20新增来源槽位的全文复核理由、来源哈希及非独立性披露 |
| states.json、features/ | 逐行身份/来源、完整提示哈希、状态和读出概率 |
| progress.json、last_failure.json | 准备/运行进度与失败实例 |
| smoke_gate.json、reports/diagnostic.json | 两数值桥接；8组合分布与12组/120行预设配对 |

## 分析边界

每次一因素比较均固定其他因素并保留十底题完整分母；不按新结果筛题或选择最佳设置。报告所有类别/概率/token变化，不计算新accuracy或行为率。已知F/S/0端点与前几轮结果先被查看，本轮为随后预先固定的新开发对照；不是独立泛化实验。

如果背景尾句删除、背景集合或循环顺序明显影响读出，结论限于这项明确编辑在固定模型/材料上的敏感性。仍需保留长度、背景额外兼容信息、文档重复和位置/顺序等解释边界；不能由此证明模型语义自知或隐藏状态因果使用。本轮不使用380确认题、patching或新行为输出。

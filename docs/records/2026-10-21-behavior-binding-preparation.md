# 2026-10-21：12场景四格行为绑定材料与CPU采集准备

记录日期与时区：2026-10-21，Asia/Shanghai。
状态：prepared_not_started_cpu_verified。操作者：助手；长期GPU启动者：用户。

用户要求继续下个阶段。本轮承接[行为草案](../behavior_binding_followup_design.md)，完成48条固定虚构材料、作者全文复核、评分规则、独立新执行器与用户启动入口、CPU测试、真实tokenizer/模型指纹及独立重建。没有启动GPU，没有任何实际回答，不把CPU准备称为实验完成。

## 固定研究设置

模型为冻结本地Qwen2.5-3B-Instruct，原chat自由回答指令、greedy128；主结果直接观察实体属性绑定，不加载或训练probe、不保存隐藏状态。新run为runs/qwen2.5-3b-behavior-binding-v1，CLI不允许换run目录重复采集。

12组虚构Unit/access-code记录，每组S-v1、S-v2、I-v1、I-v2，共48。seed42先分配24单位名与36代码，三代码排序角色的六种排列各两次；目标先于/后于干扰各6场景，五槽位置各2或3次。S→I只改目标槽，v1→v2只改干扰槽。24条I各有两套不同目标赋值且保留原文事实，共48见证，不进入提示。

当前助手读完48问题与240文档槽、73个不同全文，按12场景手写作者检查说明，封存在prompts/behavior_binding_author_review_v1.json。识别U-132/U-130等名称相似、五位置近似平衡、单一句型与长度差限制，未按难度或tokenizer挑选替换。独立语义标签0，原正式门禁不变；作者检查不代表真实文档语义审核通过。

## 实现、检查与真实状态

- 新scripts/behavior_binding_study.py复用既有renderer/冻结模型加载/GPU空闲保护，独立处理固定材料、上下文/指纹、48顺序、原始token与EOS缓存、原子attempt和完成导出。前4条smoke计入48，通过后余44；未提交attempt和失败smoke禁止自动重答。既有实验实现未改。
- prompts/behavior_binding_materials_v1.json固定生成规则和smoke顺序；behavior_binding_scoring_v1.json固定五字段及目标对齐、采用/提及/撤回差别。全48结束才导出匿名回答和空白行为表，技术汇总不计算行为率。
- 新10CPU测试全部通过，unittest2.870秒。覆盖材料单槽编辑/泄漏/世界见证、角色顺序、完整48模拟收集与只读重放、无重复模型加载的完成续跑、smoke失败止于4、未提交attempt阻止模型重载、七类缓存篡改、未完成拒绝导出、冻结产物拒绝改写与真实依赖文件准备回归。旧套件未重跑；模拟均临时CPU产物。
- 首次真实prepare在实施指纹清单时引用了不存在的classification_prompt_validation.py，在写入任何冻结材料/协议前exit1，实际目录仅.run.lock。核对依赖后改为实际classification_prompt_search.py，并增加完整prepare回归。修复发生于第一次成功冻结前，无原协议重写、GPU或回答，也不涉及拟合预算。
- 实际`sh scripts/run_behavior_binding_study.sh --stage prepare`与`PYTHONHASHSEED=179 sh scripts/run_behavior_binding_study.sh --stage verify`均exit0。48真实提示S249/I238tokens，总11,688；输出预算6,144。所有提示与token哈希一致，无协调元数据/目标漏值，无裁剪；模型metadata与2完整权重分片SHA匹配。协议12实现/5来源均匹配。
- 另写CPU代码从48保存文本逐句解析实体属性，重建24个S/I单槽对照、24个干扰单槽对照、48兼容世界，独立调用tokenizer重放48提示/长度/token哈希及角色/位置平衡，均通过。该核验是实现复算，不是独立语义评分。
- [926既有路径保存清单](2026-10-21-behavior-binding-preparation-preserved.json)全部匹配，覆盖901旧路径、拟合seal、上一轮综合结论及23条审计封存；原run495文件与一次拟合模型不变，预算剩余0，原正式标签仍全null。

## 产物与用户入口

实际新run有5冻结准备文件、4输入审阅/映射产物和锁文件；无predictions、generation_attempts、completion、模型前向、probe加载或行为评分。输入审阅包48条、输入评分模板48行全unreviewed，独立评分仍0，不自动批准。

交付[运行说明](../behavior_binding_study.md)、[48输入/token明细](2026-10-21-behavior-binding-preparation-inputs.csv)、[CPU核验JSON](2026-10-21-behavior-binding-preparation.json)及新run内input_review/inputs.html。旧草案和已封存材料不回写，当前执行状态以本记录为准。

用户启动/正常中断续跑：

```sh
sh scripts/run_behavior_binding_study.sh
```

日志runs/qwen2.5-3b-behavior-binding-v1/launch/collection.log。规划预留5–20分钟，包含CPU检查/模型加载/生成，并非新GPU实测；不能保证10分钟内，沿用用户启动分工。未提交attempt或失败smoke需检查，保留marker不重答。

完成后只读verify-results，再逐条评分和12场景配对，完整I24/S24分母不按S成功过滤。本轮准备已完成，实际GPU待用户启动；没有新行为率、语义Acc/F1或实验结果登记。原独立语义0/正式门禁false/拟合预算0/380封存保持，不自动运行、扩网格、调参或patching，未提交推送。

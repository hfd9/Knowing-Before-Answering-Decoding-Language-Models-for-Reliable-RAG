# 2026-11-11：新受控probe探索材料与用户GPU入口

记录时间与时区：2026-11-11，Asia/Shanghai。状态：CPU准备完成、用户GPU待运行；操作者：助手完成材料/知情审核/CPU准备，GPU由用户执行。

用户要求直接开始[先前计划](../review/2026-11-11-new-controlled-exploration-plan-v1/README.md)。已制作[6个作者原创虚构场景](../../prompts/new_controlled_probe_20261111_v1.json)及[36条五文档输入、36条知情参照及封存](../review/2026-11-11-new-controlled-exploration-v1/README.md)。作者以六条场景论证生成逐项记录，再阅读全部36输入；同一助手已知历史，不是独立金标准。S/I/C中S→I槽1变化、S→C槽2变化，各版其余槽不变。六个场景的对象和属性不同，但均为类似的单值结构，不能泛化至自然RAG。

[独立材料验证](../../scripts/verify_new_controlled_probe_materials_20261111.py)检查6底题36输入180槽、引用、状态槽变化及真实token；新输入总7996 tokens、214–239 tokens。允许范围内新问题精确/Jaccard≥0.8及文档精确与旧材料均0；60个去重新文档55个短于16词，未做文档近似，380正文/全部历史/预训练未覆盖。仅支持限定规则下无命中，不证明无碰撞。技术检查不认证语义。

编写[用户执行器](../../scripts/new_controlled_probe_20261111.py)及独立[预检](../../scripts/verify_new_controlled_probe_preflight_20261111.py)，固定旧P0及L28 probe、6×3×2输入和1旧桥接，共37新prefill、0答案/拟合；运行目录 `runs/qwen2.5-3b-new-controlled-probe-20261111-v1/` prepared_not_started，0条attempt/记录/特征。独立预检重建37完整提示和token哈希、57依赖；本轮CPU对7模型文件SHA均匹配。材料生成重放、独立材料/旧白名单筛查、预检、8项临时合成事务/边界测试、prepare幂等和缺operator拒绝均通过，详见[预检](../review/2026-11-11-new-controlled-exploration-v1/preflight-audit.json)。合成报告测试不等于真实GPU兼容性；启动时用户设备状态、真实运行来源、设备独占及断电持久性尚未认证。

用户运行命令及失败处置见[运行说明](../review/2026-11-11-new-controlled-exploration-v1/README.md)。估算5–16分钟、建议预留10–25分钟，为基于旧计时的规划而非实测；37条中第一条旧桥接须先通过。用户完成或报错后助手先检查现场，再作分析，不自行删除或重跑未提交attempt。

原v1/E1-r1门禁false、正式独立批准0、正式标签null、原拟合预算0、380正文封存；用户执行的新探索路径不更改旧门禁，无新GPU/模型前向、拟合、答案生成或patching。工作区在本轮开始已有暂存的背景恢复及交接四处修改，本次不覆盖或代提交；本记录、准备材料、代码及新测试单独提交，实际Git状态以回复为准。

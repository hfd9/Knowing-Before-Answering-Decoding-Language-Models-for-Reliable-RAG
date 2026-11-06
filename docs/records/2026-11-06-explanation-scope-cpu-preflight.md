# 2026-11-06：解释行为材料有限模型检查与CPU执行预案

用户要求“直接开始下一步工作”。本轮由助手继续，不要求用户逐条审查；遵守此前不把已暴露助手判断写成独立批准的边界。开始工作区干净，父提交e0ffeba5f0c90cf0086eb4c982e8619cf6c2e295。

针对实际v2 48条输入，新增[有限模型检查](../review/2026-11-06-explanation-scope-cpu-preflight-v1/finite-model-audit.json)及[CPU预案](../review/2026-11-06-explanation-scope-cpu-preflight-v1/README.md)：每题4值有限域穷举256个世界。将全部报告作为约束时，S/I0每题4个世界，IU/CT零；对IU/CT分别移除一条冲突记录后，各修复16个世界。I0及IU每个修复下目标可取四值，CT每个修复下目标为余下记录值。若记录可以全部出错，S真实目标在有限域仍可取四值；单记录只构成记录相对支持，不能认证真实值。检查依赖约定的语义模型，不是独立自然语言审核、世界真值或穷尽证明。

固定一份未授权采集的48条候选顺序：首场景S/I0/IU/CT为计入总数的四条技术smoke，其余按预定前缀和ID的SHA排序；计划绑定v2材料、原草案/评分契约及旧协议快照哈希。明确未提交attempt、孤立/乱序、smoke失败或失败标记停止与保留规则，不能按语义结果筛选。旧关系附着协议在被忽略的runs目录，本轮加入逐字节Git快照，保留引用调整前计划及有限模型报告；实际核对两计划仅协议引用位置和对应说明不同，模型结果仅计划哈希不同。旧协议中的旧采集许可不授权本研究。

新增只处理synthetic声明的[账本模拟器](../../scripts/explanation_scope_ledger_simulator.py)及[七项实际CLI合成演练](../review/2026-11-06-explanation-scope-cpu-preflight-v1/synthetic-examples.json)：未提交attempt、缺smoke、smoke失败、失败标记均阻止继续，篡改收据实际退出非0；合成前缀即使无阻塞，collection_permitted与gpu_launch_ready仍false。11项账本测试0.016秒和2项有限模型测试0.210秒通过。合成模拟没有实际磁盘原子写入、进程锁、真实token解码、模型或GPU，不能作为已实现采集器的验证。

实际v2生成器只读verify、原CLI核验和现有空评分模板verify均exit0；CLI核验报告72来源、12拟合封存、四接收快照保持，空模板的真实已审/技术完成仍0、主点及界null。旧参考协议列出的13项本地实现文件哈希匹配；仅检查代码，不是当前权重完整性认证。runs中按名称glob `*explanation*` 未发现目录，范围仅此名称；本轮没有创建任何实际run、attempt或回答，没有加载模型权重、前向、拟合、patching或访问380题。

当前仍无独立语义批准、真实采集器和GPU入口；正式gate/GPU=false、预算0、标签null、380封存。下一步助手可继续在这些边界内完善真实执行器的可审计锁、原子写入及缓存核验，或处理材料记录语义；不得把合成状态当实际回答或自动放行。[机器记录](2026-11-06-explanation-scope-cpu-preflight.json)保存本轮哈希与检查范围；按长期授权提交推送，实际结果以Git和回复为准。

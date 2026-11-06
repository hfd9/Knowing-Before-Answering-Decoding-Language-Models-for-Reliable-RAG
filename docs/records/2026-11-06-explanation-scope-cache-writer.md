# 2026-11-06：接续候选缓存合成写入与生成输入准备

用户要求直接开始上轮提出的任务。本轮从父提交 `32971225d56bac1ed69724e189a14fbc17f1d365` 及其后保留的两处在途改动接续，审查并完善[临时合成写入器](../../scripts/explanation_scope_cache_writer_fixture.py)、[只读检查器](../../scripts/explanation_scope_disk_cache.py)与[运行时](../../scripts/explanation_scope_runtime.py)。说明见[候选格式与边界](../explanation_scope_cache_writer_fixture.md)。

写入器现在生成候选磁盘格式的合成manifest、attempt、token记录和smoke，可由只读检查器重验并接入空评分包。审查发现原在途实现的清单没有标注synthetic，现增加持久化 `synthetic_fixture_only: true`，检查器读取并报告；无合成声明的清单也不证明输出由模型生成。锁文件要求普通文件，持锁期间验证路径inode未改变；任一文件事务异常令当前持锁会话停止操作。只允许同进程同一持锁会话提交自己创建的attempt，旧未提交标记阻止重答，正常提交前缀经另一进程检查后可继续。全部测试仍限系统临时目录的合成token；锁不是对非合作恶意进程的安全保证，目录同步不能证明断电持久性。

运行时新增长期供未来执行代码调用的 `generation_input`：重新渲染实际48条材料，核对问题/文档、prompt与token哈希和长度；材料变化则拒绝。它不加载模型或生成，未来采集器仍需保证实际送入模型的token及attention mask正确。

实际验证：真实tokenizer/临时文件套件36项、77.388秒exit0，覆盖48条合成记录和空评分连接、跨进程重读后提交并在新attempt处退出、未提交不能重答、锁替换/非普通文件、替换故障和替换后模拟错误、48实际生成输入及改动拒绝；原事务套件20项4.611秒exit0。完整套件之后收紧合成标记为严格布尔值，针对这一最终修改及完整合成缓存连接的2项定向测试18.763秒exit0，未再次重跑完整套件。另有不导入运行时模块的48条chat组装核验exit0（仍共享P0 builder、tokenizer及指令），CLI只读核验exit0、72来源/12拟合封存/4接收快照保持，默认run只读查询 `not_created`，`git diff --check` 通过。中途34项测试在后续增加2项前通过。

没有真实模型权重加载、GPU前向、真实回答、语义评分或新拟合。当前实际生产采集器、非synthetic运行目录写入/恢复、真实生成及其故障注入仍未实现或验证；门禁仍关闭，不能将合成事务或历史GPU快照称为GPU就绪。正式独立批准0/formal_gate=false/gpu_launch_ready=false、拟合预算0、正式标签null、380封存保持。下一步继续真实执行路径的技术准备，保留该门禁及实际输出来源边界。本记录及相关变更按长期约定提交推送，结果以Git及本轮回复为准。

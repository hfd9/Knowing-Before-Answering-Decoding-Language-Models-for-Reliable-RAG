# 2026-11-06：受门禁约束的生产写入、恢复与调用连接

用户要求直接完成生产写入恢复、故障测试和模型执行连接三项工作。从干净工作区父提交 `40d675ff37dca820a3c43807d562aac8b0342d43` 出发，新增[生产路径](../../scripts/explanation_scope_production.py)，复用[事务内核](../../scripts/explanation_scope_cache_writer_fixture.py)，并记录[设计与限制](../explanation_scope_guarded_production.md)。没有修改冻结计划或放开门禁。

代码实现固定run路径初始化/重读、共享锁事务内核、输入/计划/记录绑定、attempt与原子提交、已提交前缀恢复、未提交阻断及技术smoke；已存在但不完整的目录不自动重建。调用连接包括48输入与13历史实现快照复核、七文件及两权重分片SHA-256、计算进程和单CUDA/bf16设备检查、实际模型加载与greedy生成代码、输入输出/上下文/EOS核验及每条记录保存。GPU进程查询放在CUDA初始化前，避免把自己的新上下文误认为已有任务。设备检查是时间点快照，权重核验与实际加载之间存在变化窗口，代码不认证不可篡改的输出来源或设备独占。

当前 `collect`、生产目录创建、生产写入器构造以及共享事务内核的非合成入口均先调用现有关闭门禁；计划加载器本身也要求guard保持false。当前实现无法通过启动参数启用，未来需要有新的正式协议并审查修改门禁，不以测试通过自动放行。

实际测试：最终生产路径13项31.493秒exit0，模拟放行条件并用临时目录、合成标记、CPU固定token桩及模拟设备/模型，覆盖48条完整流程、跨进程attempt后退出、锁竞争、替换故障、损坏、输出异常阻断重答、smoke失败及重启不加载模型、目录部分初始化阻断、输入与七模拟权重文件篡改、设备及默认关闭门禁；此前11项完整测试及设备2项/直接门禁1项定向测试也通过。共享事务改造后的真实tokenizer运行时36项77.810秒及生成桩8项10.946秒exit0，原事务20项4.688秒通过。

真实七个模型文件完整流式SHA重核均匹配，结果保存在[模型指纹](../review/2026-11-06-explanation-scope-guarded-production-v1/model-fingerprints.json)；[48输入重建](../review/2026-11-06-explanation-scope-guarded-production-v1/independent-input-verification.json)和[72来源/12拟合封存/4快照](../review/2026-11-06-explanation-scope-guarded-production-v1/protected-sources-verification.json)只读核验通过。输入重建仍共享P0 builder、tokenizer及历史指令；默认真实run目录不存在。

真实模型权重仅流式读取作哈希，未加载、未执行前向，没有GPU设备实时测试、真实回答、新评分或拟合。测试中显式模拟绕过关闭门禁**仅限本进程的临时目录合成演练**；不能证明实际CUDA/Transformers兼容性、真实输出来源、断电持久性或GPU就绪。独立批准0/formal_gate=false/gpu_launch_ready=false/拟合预算0/正式标签null/380题封存保持。按长期约定正常提交推送，实际结果以Git与本轮回复为准。

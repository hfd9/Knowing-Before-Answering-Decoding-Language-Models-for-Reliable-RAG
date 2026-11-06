# 2026-11-06：真实调用路径的CPU合成连接准备

用户要求继续下一步。从干净工作区父提交 `08d4ecee4e0d5fb91f8fb8f2bb45c9a12e400bc8` 接续，对照历史 [generate](../../scripts/behavior_binding_study.py) 与固定执行草案，实现[CPU合成调用演练](../../scripts/explanation_scope_generation_fixture.py)，详见[说明](../explanation_scope_generation_fixture.md)。

代码在创建attempt前重验绑定计划、generation_config文件哈希、greedy/128参数与真实tokenizer生成输入，构造单行CPU输入token、全1 attention mask与明确的 `GenerationConfig`。固定token桩调用后检查输出张量形状、输入前缀和输入是否被修改，再经原运行时检查EOS、截断、解码及哈希，最后写入既有synthetic事务。调用失败或输出无效时保留未提交attempt、不自动重答；技术smoke失败阻止第五条，成功后可继续。仅允许临时合成写入器及本地固定token桩，正式函数仍由既有门禁拒绝；这些限定不认证数据来源。

实际真实tokenizer/CPU测试8项10.983秒exit0，覆盖参数、输入和mask、只读缓存连接、异常无重答、坏形状/错误前缀/输入被修改、输出上限/EOS后token、smoke成功与失败、计划或配置指纹变化、任意对象和正式门禁拒绝。不导入运行时的48条输入重建exit0，仍共享P0 builder、tokenizer与指令；旧CLI只读核验72来源、12拟合封存及4接收快照通过。首次5项测试在加入后续3项之前通过，最终以8项为准；本轮新增代码不改变上轮36项运行时测试范围，未重新跑该套件。

本轮没有真实模型加载、模型前向或GPU任务。固定token桩不是Transformers的实际生成，不能验证真实设备/权重、模型API兼容性、输出来源、生产写入恢复或断电持久性；真实生产采集器及非synthetic run仍未实现或验证。正式独立批准0、formal_gate=false、gpu_launch_ready=false、拟合预算0、正式标签null、380题封存保持，无新真实回答/评分/拟合。按长期约定提交推送，实际哈希以Git和本轮回复为准。

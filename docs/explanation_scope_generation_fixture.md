# 解释行为：CPU合成生成调用演练

日期：2026-11-06。状态：以真实tokenizer、CPU PyTorch张量和固定token拼接桩演练单条调用、缓存事务及故障；没有加载模型权重、运行语言模型前向或实现正式采集。

[演练代码](../scripts/explanation_scope_generation_fixture.py)仅接受既有临时目录 `FixtureCacheWriter` 与本文件定义的 `SyntheticModel`；后者只是把事先给定的token拼到输入之后，不进行模型计算。它重新读取并验证绑定计划与生成配置哈希，检查草案中的greedy/128上限，重建并核对输入，建立单条CPU `input_ids` 和全1 `attention_mask`，构造与历史调用形状一致的 `GenerationConfig`（不采样、单beam、使用cache、指定EOS/BOS/pad）和 `logits_to_keep=1`。输出必须是单行整数CPU张量，且保留输入前缀；输入张量或mask若被修改则停止。生成token再由既有运行时检查EOS、提前停止、长度、解码和哈希，之后才提交文件事务。

初始化和输入/配置验证均发生在attempt之前；创建attempt后若调用、输出或提交失败，则保留未提交attempt并禁止自动重答。前四条失败smoke会阻止第五次调用，通过后才可继续。测试包含有EOS、128 token截断、EOS后继续、错误输出形状/前缀、输入被修改、模型桩异常和配置变更。合成标记和类型限制只用于限定这个测试工具，不认证任意数据的真实来源，也不是恶意代码安全边界。

该桩不会实际执行Transformers模型的 `generate`、CUDA同步或真实生产写入，因而不能验证GPU张量位置、真实生成行为、模型与版本兼容性、权重/设备运行时核验、实际模型来源或非合成run的持久化恢复。`production_generate` 只调用既有关闭门禁，没有生产实现。未来实现真实调用前，仍须实现受约束的生产写入/恢复与正式执行协议，并在门禁条件具备时重新测试完整真实路径。当前无真实回答、语义评分或独立批准；formal_gate=false、gpu_launch_ready=false、拟合预算0、正式标签null及380题封存保持。

# 2026-11-06：真实tokenizer、评分连接与设备只读核查

用户要求直接完成上轮提出的两项后续工作。本轮在formal_gate=false及无新GPU采集的既有边界内，实现真实输入/输出校验和评分接口、实际核对权重/环境/GPU，并用真实tokenizer加合成数据测试事务；用户无需人工逐项审核。开始工作区干净，父提交42e2ede558936bff73aec4aecbc49cf08ede3f51。

新增[运行时](../../scripts/explanation_scope_runtime.py)：原P0/free-answer chat renderer和真实本地tokenizer重建48条输入，绑定问题/文档、prompt、token IDs及顺序SHA；输出端检查token范围、实际decode、文本SHA、EOS、128上限、时间和缓存/attempt前缀。完成48条技术记录后可构造匿名问答包、独立协调映射与绑定原契约的空评分模板，语义评分保持未审，空/截断保留技术状态。此代码不读取真实模型生成结果、不证明输出由模型产生，当前采集guard恒为false。

新增[synthetic临时文件集成](../../scripts/explanation_scope_verified_fixture_journal.py)，与原事务原型一起把实际tokenizer生成的合成token、解码文本及输入/输出哈希一次原子保存，重开时复核。新增[磁盘缓存只读检查器](../../scripts/explanation_scope_disk_cache.py)，绑定输入指纹及计划，持共享锁检查候选缓存格式，未知或未提交文件、写锁和损坏停止，不创建或修复文件；实际默认目录只读查询为not_created。实际26项测试58.148秒exit0，涵盖48合成记录连接评分模板（其中一条合成截断，技术完成47、新输出的实际语义评分0）、进程重读已提交前缀、子进程写attempt后直接退出且禁止重答、替换失败、token哈希篡改、不同EOS解码同一文本、EOS/早停/空文本、磁盘读取与锁竞争及门禁false。全部回答都是合成fixture，没有真实采集。首次较早测试因逐token重复查询词表大小过慢而主动中断exit130；缓存词表长度后最终26项通过，不将中断称为测试成功。

[输入预检](../review/2026-11-06-explanation-scope-runtime-preflight-v1/input-fingerprints.json)实际使用CUDA_VISIBLE_DEVICES空值运行，48项均287 tokens、总13776，EOS为151645/151643、词表151665；13项历史代码指纹匹配。最终代码重跑预检exit0且与保存JSON字节一致。另一个不导入运行时模块的脚本重新组装48条chat输入与哈希，实际exit0；它仍共享P0模板/tokenizer和历史指令，不认证语义。

实际三次完整流式模型文件SHA检查，首次结果输出在终端，后两次的最终[记录](../review/2026-11-06-explanation-scope-runtime-preflight-v1/model-fingerprints.json)及初始快照均保存：7文件含两个完整权重分片全部与旧协议匹配，无权重加载或推理。Python 3.11.15、torch 2.5.1+cu121、transformers 4.56.2等版本在输入预检保存。沙箱内nvidia-smi exit9且PyTorch报NVML不可用；沙箱外只读GPU快照在08:12:08–08:12:12 UTC显示RTX 3090、24576 MiB总/12 MiB已用/1%利用率、计算进程列表空。稍后沙箱外PyTorch识别CUDA 12.1、GPU能力8.6及bf16支持；这些是当时快照，设备检查可能初始化CUDA驱动，但没有模型加载或前向。

既有事务原型20项4.714秒、账本11项0.017秒复验通过；前三轮记录的17+12+8项哈希（35个不同路径）一致，原CLI只读核验exit0、72来源/12拟合封存/4接收快照保持。没有新真实模型输出、语义标签、拟合、正式GPU启动或380访问。真实生产采集器及非synthetic run写入/恢复、实际输出评分尚未实现，不能称两项已达到GPU运行就绪；实际独立批准0/formal_gate=false/gpu_launch_ready=false/拟合预算0/正式标签null/380封存保持。详见[运行时说明](../review/2026-11-06-explanation-scope-runtime-preflight-v1/README.md)和[机器检查](2026-11-06-explanation-scope-runtime-preflight.json)。按长期约定正常提交推送，实际结果以Git和当轮回复为准。

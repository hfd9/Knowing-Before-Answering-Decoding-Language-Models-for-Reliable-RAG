# 解释行为运行时：真实tokenizer核验与设备检查

日期：2026-11-06，Asia/Shanghai。状态：**真实tokenizer的输入/输出校验及评分连接已实现，并以合成token、临时文件完成测试；权重及设备完成一次只读检查**。没有真实模型回答、真实采集run或可启动的GPU采集器，正式独立批准0、formal_gate=false、gpu_launch_ready=false。

## 输入、输出和评分连接

[运行时](../../../scripts/explanation_scope_runtime.py)使用已绑定的48条材料、固定顺序、历史free-answer指令和本地Qwen tokenizer，计算每条问题及五文档的规范化输入哈希、完整chat prompt哈希、输入token ID哈希和长度；[实际结果](input-fingerprints.json)保存48条指纹。只把问题和文档交给renderer，条件、协调见证和替代目标值不进入prompt。48条均287 tokens，总13776；本地EOS为151645和151643，词表大小151665。

输出记录检查会重新渲染输入，核对ID及顺序、输入/prompt/token哈希、生成token范围及token序列SHA、EOS不得出现在末位之前、非EOS提前停止、128-token上限、token实际解码文本及其SHA、时长和带时区完成时间。两个不同EOS可能解码为相同空文本，故同时保留token序列哈希；哈希仅检查一致性，不认证来源。空输出、未提交attempt、孤立记录、异常临时文件、失败标记、无smoke收据或smoke失败均不能被当作正常完成。函数检查提供的token和记录是否一致，**不证明这些token确实由模型生成**。

完成48条且技术smoke通过后，`review_artifacts`可建立匿名完整问题/文档/回答包、单独的协调映射和与原评分契约兼容的空端点模板，并给三者生成规范JSON哈希。协调映射与模板暴露条件，必须与匿名包分开；所有语义评分仍为空，无法通过该连接自动创建独立批准。截断或空输出保留为相应技术状态，不计为正确拒答。

[集成原型](../../../scripts/explanation_scope_verified_fixture_journal.py)把上述真实tokenizer验证接到既有**临时目录、synthetic专用**事务原型，单次原子替换同时保存文件状态和token绑定记录。它不是生产采集器。实际测试用本地tokenizer编码虚构短语构造输出，验证48条合成记录及评分模板、进程退出后的未提交标记、另一进程读取已提交前缀、token哈希篡改和原子替换失败。synthetic标记和token一致性不能认证真实输出来源。

[磁盘缓存只读检查器](../../../scripts/explanation_scope_disk_cache.py)定义待实现采集器可使用的候选缓存格式；读取已有缓存时获取共享锁，核对材料指纹、attempt顺序、实际token解码和smoke，发现写锁、未知文件、pending文件、损坏或未提交attempt即停止，绝不创建或修复文件。[本次实际只读查询](cache-observation.json)显示预定run目录不存在。此检查器没有写入端，也不能证明缓存内容来自模型；当前仅用临时目录的合成数据测试。

## 环境、设备与独立重建

- [完整模型文件哈希](model-fingerprints.json)：config、索引、tokenizer、生成配置与两个权重分片共7文件的实际SHA-256全部匹配旧协议；仅读文件计算哈希，没有把权重加载为模型。首次交互检查后又以[可重放脚本](../../../scripts/verify_explanation_scope_model_files.py)实际复查，初次保存结果见[初始快照](model-fingerprints-initial.json)。
- [环境和48条指纹](input-fingerprints.json)：Python 3.11.15、PyTorch 2.5.1+cu121、Transformers 4.56.2；旧协议所列13项本地实现文件SHA均匹配。预检不加载权重，单独模型文件哈希另存。
- [独立chat组装检查](independent-input-verification.json)：另一个脚本未导入运行时验证模块，从材料重新组装48条chat输入，逐项比对问题/文档、prompt和token ID哈希；它仍复用同一个P0模板函数、tokenizer和历史指令，不是完全独立实现，更不是语义审核。
- [GPU快照](gpu-observation.json)：2026-11-06 08:12:08–08:12:12 UTC的沙箱外只读查询显示GPU 0为RTX 3090、24,576 MiB总显存、12 MiB已用、1%利用率；计算进程查询为空。该结果仅为当时快照。
- [PyTorch CUDA检查](torch-cuda-observation.json)：沙箱内无法初始化NVML并报告不可用；沙箱外识别到一块RTX 3090、CUDA 12.1、计算能力8.6、支持bfloat16。设备能力查询可能初始化CUDA驱动；没有加载模型或做前向。

## 测试与尚未完成的部分

真实本地tokenizer运行的26项新测试通过，包括48输入哈希、EOS/提前停止/截断/篡改、不同EOS解码同文本的token哈希、技术smoke、48合成输出至空评分模板、截断保留、跨进程重读已提交前缀、子进程在attempt后退出、文件替换故障及只读磁盘检查/锁竞争。测试通过真实tokenizer及临时文件，但输出token和文本都是人工构造的合成fixture，不是模型回答。另有原事务原型20项、原合成账本11项复验通过。首次测试尝试因逐token重复查询词表大小过慢被主动中断，退出130；随后改为每个运行时实例只查询一次并以最终版本通过测试。

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/explanation_scope_preflight.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_explanation_scope_runtime.py
python3 -B scripts/verify_explanation_scope_model_files.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/explanation_scope_disk_cache.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B -m unittest discover -s tests -p test_explanation_scope_runtime.py -v
```

真实生产采集器、实际模型加载与生成、非synthetic运行目录的写入/恢复、实际输出的审查与评分尚未完成或验证；GPU查询及权重哈希也不保证未来空闲或权重永不变化。真正运行前仍须实现并测试实际采集路径、在运行时重核权重/设备、处理材料语义和现有正式门禁。用户无需逐条人工审核，但助手的历史暴露不能被改写成独立语义批准。原拟合预算0、正式标签null及380题封存保持。

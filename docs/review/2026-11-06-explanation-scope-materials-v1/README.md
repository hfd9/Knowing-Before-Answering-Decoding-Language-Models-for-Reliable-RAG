# 解释行为材料草稿v1：保留的修订前版本

2026-11-06。该目录保留首次按seed42生成的12场景×四条件草稿及实际CPU检查；它不是独立审核材料、可执行采集协议或已完成实验。设计锁定后才生成48个输入，无模型回答。

检查发现目标单位编号在12场景中总小于另一单位，且XU-215与既有U-215共享数字后缀；完整ID不同，但数字后缀可能带来不必要的关联。本版不删除、不静默更改，后续在任何模型回答产生之前另存[v2](../2026-11-06-explanation-scope-materials-v2/README.md)：同样12个符号场景和四条件，调整单位编号并平衡大小关系，不增加实验样本。

本目录[design-lock.json](design-lock.json)包含条件映射及协调见证值，[materials.json](materials.json)包含条件标签，[coordinator.json](coordinator.json)含映射和见证；它们不可作为无暴露评审或模型的直接输入。[input-packet.json](input-packet.json)仅含匿名问题和五文档；此包也不会自动保证评审独立性。[preflight.json](preflight.json)是修订前实际检查的原始输出，后续脚本增加的编号后缀/大小检查不在该快照中。

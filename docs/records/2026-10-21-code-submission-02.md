# 2026-10-21：冻结probe绑定读出与校准诊断本地归档

用户要求“记录好提交代码”。本次在main上归档父提交`5152ca9dfcf63896fb5101ab7c64d17263d97441`之后的本轮成果，沿用仓库local hfd9身份，不覆盖为Codex、不改写历史。用户本次未要求推送，因此只创建本地提交，不联网核查远端。本记录所属Git提交即归档版本，实际完整哈希由Git及本轮回复给出，不在提交内容内嵌自引用哈希。

## 归档范围

- 背景恢复记录及交接维护。
- 原48条输入的旧冻结chat L28补充读出：固定协议、单次prefill/严格attempt与缓存恢复、联合分析、CPU测试及运行说明；用户实际48前向完成后的原输入/状态/probe/原行为联合结果、配对表和独立复算。
- 同一旧probe原线性判定与sigmoid校准的288条CPU离线诊断：固定事后口径、原线性分数/softmax/校准分数与三概率、288逐条/348配对/33切片/42底题、独立手算及8项相关测试。
- AGENTS、记录索引、活动日志、综合结论、迁移说明与描述性实验登记同步。

48补充中原主行为正确，但probe的S为answer13/conflict11、I全部24为answer。校准诊断显示48参照一致原线性18/48→校准13/48；240为117/236→117/236且4作者unknown保留。全部16次类别变化转conflict，I类别两阶段均不变，不能仅取消校准就宣称迁移修复。48引用归属unknown不计引用成功或失败；连续分数响应与可靠三分类保持区分。

归档共43文件：6个Python、15个JSON、1个shell、9个CSV、12个Markdown。最大有效载荷文件为288逐条CSV（335,394字节），整批约1.6MB。本次提交代码和轻量产物；runs、模型权重、probe pkl及激活数组仍按.gitignore仅存本地。

## 本次实际检查

6个Python AST、全部JSON解析、shell语法与归档路径/大小检查通过。提交前实际运行以下只读入口，均exit0：

```sh
PYTHONHASHSEED=233 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/probe_calibration_diagnostic.py --stage verify
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_behavior_binding_probe_results.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_probe_calibration_diagnostic.py
```

48概率及288各阶段独立复算最大误差均0；1132此前路径含12拟合封存和共享预算声明、本次CPU run10文件以及原48前向run116文件均不变。完整模型权重/原48完整verify-results已在完成核验阶段实际通过；本次不重复其耗时检查，也不把本次轻量复核写成新GPU结果。

旧测试套件和本轮同版本12项/8项测试未在提交时重跑，沿用已记录证据，不相加冒称一次全套测试。已有差异格式检查通过；暂存完整差异后，CSV按冻结CRLF允许CR-at-eol检查，其他文件按严格空白规则检查，不规范化已封存CSV字节。具体范围、有效载荷SHA256和检查值保存于[机器记录](2026-10-21-code-submission-02.json)。交接维护文件与本记录不做自引用哈希。

## 状态与边界

本次没有新增拟合、模型前向、GPU调用、回答或行为评分；只完成归档提交。原一次拟合预算0、独立语义批准0/正式gate=false/正式标签null、380保留题封存不变；不替换默认probe、增设阈值或进入patching。已见eval不恢复前瞻性，原阶段“未提交/committed=false”等字段保留其历史快照含义，不覆盖冻结结果。

本次仅本地提交，未推送、未联网重查远端，未修改Git历史或用户身份。

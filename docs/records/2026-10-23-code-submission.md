# 2026-10-23：关系附着研究归档与云端推送

用户要求“记录好后推送代码到云端”。本轮归档父提交`615d9c2ba10c3e84a198eb5184491842b56f0b83`之后的全部研究成果，沿用仓库local hfd9身份，正常提交与推送main，不改写历史。本记录所属Git提交即本次归档版本；不在提交内嵌自引用哈希，实际提交及推送后的远端完整哈希由Git与最终回复给出。

## 归档内容

- 10月23日背景恢复与交接维护。
- 旧23条缺证作答与48绑定任务的结构差异审计：23行/13底题、五统计切片、七维度、独立复算与两场景16例。
- 新关系附着六场景48输入的固定设计、完整材料、72兼容世界/72配对、作者检查、评分规则、严格attempt与缓存采集入口、10项CPU测试、真实CPU准备及独立提示/token核验。
- 用户完成采集后的48条结果、手写评分与封存、120输入/48完整输出引用、12主要配对/六场景、五条质性注记、独立字段/计数/原始token解码和完整核验记录。
- AGENTS、索引、活动日志与描述性实验登记。

本批结果为TQ有据12/12，全部36不足实质作答0/36，TA0/12−OA0/12=0pp；三条额外无据冲突解释保留，不能将零误绑定写成所有文本正确。240字段194确定/46具体引用归属unknown，作者历史暴露非独立语义审核。按预设停止规则结束本批，不追加网格或probe。

归档共61文件：7Python、30JSON、1shell、11CSV、12Markdown。只提交代码与轻量材料/结果/核验；原始runs、模型权重、probe pkl、激活数组及本机SSH配置/凭据均不加入Git。约1.4MB有效内容，最大单文件约169KB。

## 提交前实际核对

7个Python AST、全部JSON解析、shell语法、CSV列数与三个阶段payload SHA256检查通过。最新同版本10项CPU测试已在准备阶段8.115秒通过，本次不重跑或将它重复计为新测试。完整GPU结果入口已在完成阶段通过，本次只重放以下CPU只读分析，均exit0：

```sh
PYTHONHASHSEED=263 python3 -B scripts/relation_attachment_results.py --stage verify
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_relation_attachment_results.py
```

48字段/引用/12主要配对及六场景复算误差0，48原始token解码一致；1181此前路径及本次源run67文件集合/字节不变，原12拟合封存与共享预算保持。没有新增GPU、前向、回答、评分或拟合。暂存完整范围后CSV按允许CR-at-eol规则检查，其他文件按严格差异规则检查，不规范化封存CSV字节。有效载荷清单/哈希和检查口径保存于[机器记录](2026-10-23-code-submission.json)，不对交接维护与归档记录作自引用哈希。

## 远端与推送范围

提交前实际`git ls-remote origin refs/heads/main`正常退出，远端为`798345e1cad7c50f07eddc32752a0ec3a077492b`；该提交为本地HEAD祖先。远端尚未包含此前两次本地归档`5152ca9`和`615d9c2`，因此本次正常推送会同时上传它们及当前新提交，三次提交的历史全部保留。

目标是现有origin仓库`hfd9/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG`的main分支，使用已有SSH443配置。推送后再读远端main并与本地HEAD逐字匹配；最终成功状态与完整哈希以实际命令和本轮回复为准，不把推送意图当成功。

原拟合预算0、独立语义批准0/正式gate=false/标签null、380封存和研究解释边界均保持。原阶段记录中的“未提交/未推送/committed=false”保留历史快照含义。用户授权本次归档与正常推送，不自动扩大为新实验或历史改写。

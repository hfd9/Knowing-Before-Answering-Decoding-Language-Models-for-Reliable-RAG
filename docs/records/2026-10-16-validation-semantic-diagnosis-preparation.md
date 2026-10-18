# 2026-10-16：CPU诊断入口与新评审空白材料准备

记录时间与时区：2026-10-16，Asia/Shanghai。
状态：prepared；真实数据临时目录导出与只读检查已验证，正式导出待用户执行；新独立评分0条。
操作者：助手准备与测试，用户启动正式入口。

## 目标与背景

用户要求“你把代码写好我来跑”。接续[30条已完成诊断](2026-10-16-validation-semantic-pilot.md)，准备可复查的全文对照与新评审空白材料，先解决输入语义和引文支持问题。无需重复GPU或自动增加v5预算；本次不新增模型推理或语义判断。

## 实际操作

新增`scripts/validation_semantic_diagnosis.py`、`scripts/run_validation_semantic_diagnosis.sh`、`tests/test_validation_semantic_diagnosis.py`和[运行说明](../validation_semantic_diagnosis.md)。代码仅依赖标准库，先核验历史持久清单，再调用已冻结的原汇总器只读重放；原v1–v4及pilot代码、protocol、预测和封存判断保持原样。

新报告补充各类一致分母、high子集敏感性、引文支持与类别一致的交叉计数，并逐条展示完整五篇原文、v4完整前置分析/JSON/所选引文、旧四组原始输出及本轮助手判断。此为既有结果的再现与展示，不是新的独立语义准确率。

新评审包使用seed20261016重排匿名R编号，完整30条，只预填ID和材料哈希，语义、理由、来源和阅读声明均空白。将3unknown与4moderate列为7条优先项，具体原因与映射只在coordinator；全部30条仍提供，不能根据选择性队列外推总体比例。没有把旧判断填成第二评分，材料隔离也不能证明实际评审独立。

新目录一次性完整导出；已有目录只能逐文件验证相同内容，不重写。导出清单保存10份文件哈希和入口指纹，包含其自身共11份文件。新评分须另存副本，不修改生成的空白模板。

## 证据、检查与产物

助手实际执行：

```sh
sh scripts/run_validation_semantic_diagnosis.sh --check_only
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B -m unittest discover -s tests -p test_validation_semantic_diagnosis.py -v
sh -n scripts/run_validation_semantic_diagnosis.sh
git diff --check
```

只读检查通过：7份原始受保护来源、历史绑定文件哈希、30条输入映射、54条引文、封存/汇总重放，30条v4副本和旧四方法记录均与原始预测逐条一致。新增5项CPU测试通过，覆盖unknown与invalid分母、公开材料隔离/完整原文/7条优先选择、源变更及重复ID拒绝、完整导出/重复验证/变更保护、HTML原文转义。未重复旧62项GPU流程相关CPU测试或原3项pilot测试。

另外在`/tmp/kba-diagnosis-e2e-*/`用真实入口两次运行：首次导出、第二次只验证；核对10份产物哈希、30行评分全空、材料哈希绑定、7条优先映射及既有7/27重放一致。临时目录由测试清理。正式`runs/qwen2.5-3b-validation-semantic-diagnosis-v1/`未生成，保持待用户启动。只读检查本机约0.2秒，保守为用户预留1分钟，不涉及GPU等待。

## 结果与解释边界

已完成代码和检查；正式导出尚未启动，没有新的独立评分、语义指标、训练或模型输出。既有背景暴露、10底题小样本和同助手判断限制继续披露。原无合格提示词基线的结论不变，确认集未读取。不更新experiments.csv的新指标，不提交或推送。

## 未完成项与下一步

用户在根目录执行：

```sh
sh scripts/run_validation_semantic_diagnosis.sh
```

终端出现`DONE`仅表示报告与空白包导出完成。先看新目录`report.md`或协调者全文HTML；新评审仅使用`reviewer/`目录，在新副本填写后再单独核验、比较与裁定。不把运行代码当成独立语义复核完成，不自动新GPU实验。

## 索引更新

同步AGENTS、记录索引和activity_log。保存[准备校验清单](2026-10-16-validation-semantic-diagnosis-preparation.json)，保留工作区已有暂存/未暂存修改和旧快照。

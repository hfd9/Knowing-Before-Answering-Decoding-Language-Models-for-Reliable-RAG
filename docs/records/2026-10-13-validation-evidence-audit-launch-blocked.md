# 2026-10-13：验证集证据诊断启动被GPU占用保护阻止

记录日期与时区：2026-10-13，Asia/Shanghai。
状态：用户启动尝试退出；模型未加载，新生成0条。
操作者：用户执行顺序入口，助手只读检查日志和产物。

## 目标与背景

用户运行`sh scripts/run_validation_evidence_audit_review.sh`，终端打印smoke日志路径后返回提示符，询问是否仍在运行。前序代码与CPU准备见[准备记录](2026-10-13-validation-evidence-audit-preparation.md)。

## 实际操作与证据

助手只读查看正式目录`launch/smoke.log`、两目录progress及文件清单。日志显示9条CPU preflight通过，随后`infer`调用`assert_gpu_idle`在模型加载之前抛出：

```text
RuntimeError: Selected GPU has an active compute process; stop and choose an idle time
```

顺序包装的`set -e`因此退出，没有进入正式阶段。日志没有具体占用PID；本次未查询宿主实时GPU状态，不能断言当前占用进程身份或GPU仍被占用。

- smoke progress仍为`prepared_not_started`，saved_outputs=0、target_outputs=9。
- 正式progress仍为`prepared_not_started`，saved_outputs=0、target_outputs=285。
- 两目录未发现`drafts/predictions.json`，正式`launch/full.log`尚未创建。
- 保护检查发生在生成循环前，所以progress没有改成running；没有新GPU输出可分析。

## 结果与下一步

这次入口已因启动保护退出，未在后台继续生成，也没有完成smoke。用户可在宿主终端执行`nvidia-smi -i 0`查看当前占用，待其他任务释放GPU后原样重跑顺序入口。没有停止其他进程或绕过保护，不需改协议/代码或新建目录。

## 索引更新

追加本记录并更新索引、AGENTS及活动日志。代码、配置、协议、运行输出及历史准备记录未修改，没有新指标，不更新experiments.csv；未提交或推送。

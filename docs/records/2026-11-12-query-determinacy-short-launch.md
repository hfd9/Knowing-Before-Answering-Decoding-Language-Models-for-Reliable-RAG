# 2026-11-12：查询可判定性续做短命令

记录时间与时区：2026-11-12，Asia/Shanghai。状态：启动脚本准备完成；操作者：用户报告 shell 输出，助手核验及准备。

用户粘贴命令时 shell 将命令片段拼接，报告 `collectexport: not found` 与 `bad variable name`。助手只读 inspect 确认续做 run 仍为 0 attempts/0 records/143，原首条仍为技术截断未评分，本轮未启动 GPU。

新增项目根目录 [pilot.sh](../../pilot.sh)：切换到脚本所在目录、显式设置并导出 `CUDA_VISIBLE_DEVICES=0`，调用既有冻结 v2 入口的 `collect`。用 `sh -n pilot.sh` 检查语法，不执行脚本、不改原协议或模型。用户在项目根目录输入 `sh pilot.sh` 即可；完成或报错后按既有记录保留两个 run 并通知助手。原四处暂存内容保留，本记录和脚本单独提交推送。

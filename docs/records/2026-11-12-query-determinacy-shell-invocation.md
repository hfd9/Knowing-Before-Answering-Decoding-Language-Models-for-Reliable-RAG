# 2026-11-12：查询可判定性续做命令换行核对

记录时间与时区：2026-11-12，Asia/Shanghai。状态：只读核验完成；操作者：用户报告 shell 输出，助手核验。

用户报告两次运行续做命令时，`collect` 换行成为独立命令；Python 提示缺少 stage，shell 提示 collect not found。助手运行只读 inspect：续做目录仍0 attempts/0 records、总143、有效空前缀；原首条截断记录 SHA-256 仍为 `cbb58076c9acb1f1f601d2090a59f2f46501698d257c608d9ee99d0e87fb3136`。此次未启动 GPU 生成，未修改两个 run 的记录。

下一步在已确认的项目根目录执行：先 `export CUDA_VISIBLE_DEVICES=0`，再把 Python 路径、脚本路径和 `collect` 作为同一个 shell 命令；若分行，在 Python 路径行末使用反斜杠续行。其余中断处置和分母不变，详见[续做说明](../review/2026-11-12-query-determinacy-remaining-v2/README.md)。原暂存交接内容保留；本记录单独提交推送。

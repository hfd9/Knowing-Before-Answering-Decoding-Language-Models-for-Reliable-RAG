# 2026-11-15：提示对照短启动命令

记录时间与时区：2026-11-15，Asia/Shanghai。状态：prepared_not_started；操作者：用户报告命令失败，助手核验并修复启动方式。

用户两次粘贴的命令在Python脚本路径后换行，`collect` 未作为同一命令的参数，argparse因缺少stage退出；shell另将 `collect` 当作命令时报告找不到。实际inspect仍为valid_prefix、0 attempts/0 records/144、0技术缺失，未有真实采集，也无需删除或重新准备。

新增[项目根目录短启动脚本](../../prompt_control.sh)，将 GPU 设为0并传入原已冻结的 `collect` 参数；从项目根目录运行 `sh prompt_control.sh`。只新增启动壳，未更改清单、材料或运行器；`sh -n prompt_control.sh` 语法检查通过。运行后如完成或报错，保留现场并告知助手。按长期约定本记录、启动壳和入口说明单独提交推送，不动既有暂存和其他未跟踪材料。原门禁、预算与380封存不变。

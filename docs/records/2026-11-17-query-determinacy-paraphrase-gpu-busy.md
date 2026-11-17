# 2026-11-17：改写开发运行的GPU占用阻断

记录时间与时区：2026-11-17，Asia/Shanghai。状态：设备检查阻断，待GPU空闲；操作者：用户执行，助手CPU只读核验。

用户运行 `sh paraphrase_dev.sh` 并报告 `STOP: GPU has active compute processes; preserve run, do not delete or retry attempts`。该信息是用户粘贴的设备检查结果；助手未查询实时GPU、未识别或终止占用进程。

助手运行CPU `inspect`，结果 `valid_prefix`、0 attempts/0 records、0技术失败、计划96；运行目录清单与归档清单SHA均为 `664c4a57c2c1cbe887f67c03be0814ba13833f4e2dd9018be7530a935e835f15`。结合代码执行顺序，该设备检查发生在模型加载和写入attempt之前；当前无需删除或重建run。没有新生成、评分或GPU运行。

待用户确认GPU 0上的计算任务正常结束后，可再次执行同一 `sh paraphrase_dev.sh`；每次启动会重新检查设备。若仍占用，可由用户运行 `nvidia-smi -i 0 --query-compute-apps=pid,process_name,used_memory --format=csv,noheader` 查看并反馈；不要求终止其他任务。若以后出现attempt或其他错误，先停下并保留目录交助手核验。原门禁、预算与380封存不变；先前暂存及无关未跟踪内容保留。

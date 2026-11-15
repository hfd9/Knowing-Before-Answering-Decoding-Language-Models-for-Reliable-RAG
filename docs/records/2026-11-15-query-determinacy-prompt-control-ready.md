# 2026-11-15：查询可判定性同题提示对照准备

记录时间与时区：2026-11-15，Asia/Shanghai。状态：prepared_not_started；操作者：助手CPU准备，GPU待用户执行。

按用户持续推进要求，针对[前批72条知情复核](2026-11-15-query-determinacy-development-results.md)中双世界全36条保留不确定的现象，另立[同题提示对照](../review/2026-11-15-query-determinacy-prompt-control-v1/README.md)：每个旧输入各生成简短回答及逐值判断两个末句，72×2=144新输入；旧72保留为历史基线不重跑。旧6题已暴露、两种提示同时改变措辞或任务要求，类别析取歧义未消除，探索性比较不证明因果机制或总体泛化。

3项新CPU测试检验固定替换/参照不变、篡改拒绝和144模拟含截断留痕不重答；复用的开发运行器已通过4项测试覆盖smoke和未提交attempt。真实token 71–122，清单重建一致，7模型文件SHA与快照一致；[清单](../review/2026-11-15-query-determinacy-prompt-control-v1/manifest.json)哈希 `a406da0f993d0e8e6ce7370eb365b0dc038ce75f32f730df1553e6373aabbb26`，实际inspect 0 attempts/records/144。前4技术smoke覆盖两个提示、两族与单双世界；smoke空/截断即停止，之后技术失败留痕继续，结构异常停止。预计建议预留20–45分钟，仅规划；GPU由用户按入口执行，结束或报错后助手核验再评分。

未新启动GPU/前向或评分；原v1/E1-r1门禁false、正式独立批准0、正式标签null、原拟合预算0、380封存，不训练/阈值搜索/patching。原4暂存交接和未跟踪旧材料保留，本轮报告、源码、测试与记录单独提交推送，共享索引不改。

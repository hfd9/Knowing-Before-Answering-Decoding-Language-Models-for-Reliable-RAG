# 30条验证集诊断报告与空白复核包

代码准备完成，正式导出待用户启动。本步骤使用CPU和Python标准库，不加载模型；基于已完成的[30条输入语义复核](records/2026-10-16-validation-semantic-pilot.md)，不重新生成285条、不修改旧预测、封存判断或正式行为标注。

## 启动

在项目根目录执行：

```sh
sh scripts/run_validation_semantic_diagnosis.sh
```

预计几秒，保守预留1分钟。助手已在`/tmp`完成真实数据全流程检查，正式目录未提前生成。入口优先选择kba-rag Python，不依赖torch、transformers或GPU。终端显示`DONE (new_outputs_written)`代表报告和空白复核材料导出完成，后续评分仍待填写。

只检查来源和内存渲染、不写任何输出：

```sh
sh scripts/run_validation_semantic_diagnosis.sh --check_only
```

默认输出：`runs/qwen2.5-3b-validation-semantic-diagnosis-v1/`。

| 文件 | 用途 |
| --- | --- |
| `report.md` | 先看此文件：各方法的充分/不足/冲突分别一致计数及口径 |
| `diagnosis.json` | 完整重放汇总、全27确定输入与high23敏感性计数、引文支持和类别判断交叉表 |
| `coordinator/diagnosis.html` | 离线浏览30条完整原文、封存输入判断、v4全文分析/决策/引文、旧四组输出与手工归因 |
| `coordinator/review_mapping.json` | 新R编号与旧P编号的协调映射，勿提供给新评审 |
| `coordinator/priority_details.json` | 7条优先项的旧判断及原因，勿提供给新评审 |
| `reviewer/inputs.html`、`inputs.json` | 全部30条重新编号的问题和完整五篇原文，无发布标签、旧判断或模型输出 |
| `reviewer/ratings.blank.csv` | 30行空白评分模板，只预填新编号和材料哈希 |
| `reviewer/priority_ids.json` | 7条优先复核的新编号，不公开旧判断与选择原因 |
| `reviewer/README.md` | 复核规则、字段与来源披露说明 |
| `manifest.json` | 10个导出文件哈希、源清单哈希、代码指纹、重排seed和“新增评分0条”状态 |

HTML直接用浏览器打开，无需启动服务器。新评审只接收整个`reviewer/`目录；协调页面和原记录含旧判断及模型输出，不能同时作为新评审输入。匿名与隔离是材料准备方式，独立性取决于实际评审来源及已有暴露，不能由代码认证。

## 具体检查与计数口径

入口核验持久清单绑定的7份原始来源、3个原复核实现/测试文件、6份持久副本和7份运行产物；验证暴露披露和受保护源列表与持久副本一致。随后重放既有固定抽样、30条输入/五篇文档映射、54条精确引文与封存摘要，逐条比较揭示副本和原始v4/旧四组预测。此流程不会自动判断引文是否蕴含结论。

类别一致计数以封存助手判断为参照：unknown输入3条单列，其余27条包含技术invalid；充分11、不足12、冲突4分别保留分母。另列high23条仅作事后敏感性描述，不用于选方法或改原门槛。既有手工问题标签及引文支持评价带来源保存，不转换成自动评分或因果结论。所有unknown和moderate共7条优先复核，其余23条仍全部提供；不能用7条选择性队列估计总体错误率。

## 重复运行与后续评分

相同代码和来源重复执行原命令，只核验已有11个文件，不改写。任一旧产物改变，或更改本入口代码后继续用旧目录，都会退出并保留原文件。需要新版本时指定新的目录，不删除或改指纹绕过：

```sh
sh scripts/run_validation_semantic_diagnosis.sh --output_dir runs/qwen2.5-3b-validation-semantic-diagnosis-v2
```

填写时先将`ratings.blank.csv`复制为新的评分文件；不要改原空白模板。新增评分尚未发生，不能把运行成功当复核完成。填完后另行校验来源、原文引文、完整性和分歧，再决定是否扩展语义复核或固定新提示词实验；本入口没有自动导入功能，也不启动新GPU候选或确认集实验。

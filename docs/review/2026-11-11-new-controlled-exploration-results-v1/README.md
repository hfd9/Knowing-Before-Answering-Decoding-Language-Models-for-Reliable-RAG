# 新受控冻结 probe 探索：结果与核验

2026-11-11，Asia/Shanghai。用户报告完成运行；现场保存37条prefill记录：一条旧输入桥接及6个原创虚构底题×S/I/C×A/B的36个新输入。没有生成答案或拟合。此为有历史暴露的作者参照下的小规模开发探索，不是确认实验或独立语义准确率评估。

## 类别结果

| 作者参照的状态（12输入、6底题） | answer | refuse | conflict |
|---|---:|---:|---:|
| S 充分 | 9 | 0 | 3 |
| I 缺证 | 4 | 0 | 8 |
| C 冲突 | 0 | 0 | 12 |

逐底题的两个表达依次为 A/B：

| 底题 | S | I | C |
|---|---|---|---|
| novel01 | answer / conflict | conflict / conflict | conflict / conflict |
| novel02 | conflict / answer | conflict / conflict | conflict / conflict |
| novel03 | answer / answer | conflict / answer | conflict / conflict |
| novel04 | answer / answer | answer / conflict | conflict / conflict |
| novel05 | answer / answer | answer / conflict | conflict / conflict |
| novel06 | conflict / answer | conflict / answer | conflict / conflict |

18个A/B对中，S为3/6同类、I为2/6、C为6/6；I的两个同类对均为两端conflict，与作者缺证参照均不符。单个底题的两表达不是独立样本。全部42个预定关系对及每端三个概率见[原始报告](source/report.json)。

12个同底题、同表达的S→I对，refuse概率全部上升、平均+2.99个百分点，但12个I的最大概率类别没有一个是refuse；conflict概率10/12上升、平均+6.33个百分点。12个S→C对的conflict概率全部上升、平均+50.86个百分点；均为描述性读出，概率不直接代表校准后的真实概率。

在本批材料及知情作者参照下，旧L28 probe对构造的冲突有方向性响应，但不能可靠地将三状态映射为预期类别，尤其不能据此认定其可靠检测缺证。表达稳定也可能同时偏离参照。参照是同一有历史暴露的作者对相似单值场景的判断；提示、词汇、长度、位置和内容仍混杂，无法断言哪一个因素导致读出，更不能证明隐藏状态没有相关信息。此批仅prefill，未测同批模型回答或行为关系；不能推断“检测不足却未行动”。

## 技术核验与证据边界

- 冻结运行器 `--stage verify` 通过：重核计划及依赖、模型文件SHA、材料、37条完整提示和token身份、每条特征与冻结读出、attempt及42对报告。该路径为CPU只读验证，没有新前向。
- [独立重算脚本](verify_results.py)核验78份归档文件与现场SHA一致、37记录/attempt/特征顺序和绑定、特征形状与有限值，直接调用冻结scaler和router重新计算全部预测；概率最大误差0。脚本另从状态独立重组类别和配对统计，见[机器可读审计](audit.json)。它与运行器共用冻结模型、特征和sklearn组件，不是独立语义评分。
- 旧输入桥接对36层的最大相对L2误差0，probe最大概率误差0；这只覆盖一个旧输入。37条完成时间为06:53:20.441602–06:53:22.214423 UTC，表示记录时间，不包括模型加载或全部命令耗时。
- 用户报告运行完成，但未提供终端日志；本地未持久化设备全程独占证明，不能据此认证操作人身份或全过程设备状态。无失败标记或未提交attempt；没有访问380题正文。

来源[归档](source/)包括协议、37输入、37记录、37个attempt、37个特征及完整报告；[审计](audit.json)保存其SHA。作者材料与封存参见[准备说明](../2026-11-11-new-controlled-exploration-v1/README.md)。新探索不改变旧v1/E1-r1门禁、正式独立批准、正式标签、原拟合预算或380封存；不自动扩样、重训、阈值搜索或patching。

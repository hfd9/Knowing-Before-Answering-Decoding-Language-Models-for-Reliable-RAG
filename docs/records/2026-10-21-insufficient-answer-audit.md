# 2026-10-21：23条缺证作答的事实、依据与解释边界审计

记录日期与时区：2026-10-21，Asia/Shanghai。
状态：posthoc_insufficient_answer_audit_complete / history_exposed / independent_gold=false。
操作者：当前助手。用户要求直接完成上一轮建议的后续工作。

本轮已完成旧240回答中23条作者判不足且实质作答输出的逐条细分，关联同题同表达S对照，并收敛下一项行为实验的问题。23输出来自13底题；固定选择依据为旧作者refuse且旧has_substantive_answer=yes，未按新细分结果换样本。全文读取I与S共230文档槽、121篇去重全文，以及23条I和23条S完整回答。当前助手已接触项目历史、作者判断、旧评分及输出，所有新判断均为事后有暴露作者侧细分，不是独立金标准。

## 主要发现：不是23条同一种来源的回答

| 文本现象主编码 | 输出数/23 | 具体含义 |
| --- | --- | --- |
| 已有事实被挪到另一所问关系 | 8 | 重复已给名称代答别名、Dingzhou位置赋给Luoding、第一季22集赋给第二季、现象/条件变成成因、唱片名变录制者。 |
| 已有候选或线索被提升成未显式提供的关系 | 9 | 河流存在→主要河流、chess-like→board game、可见单季→overview总数、Pachisi基础→Sorry!类别、最大城市→首府。 |
| 补出文档均未出现的关键答案值 | 6 | 年份1963/1958、better两条、sushi/sashimi各一条。 |

三类是互斥的表面对应描述，合计23；不能当模型内部生成路径。前两类17条有相关名称/候选已在文本出现，也可能同时使用外部知识；最后6条的关键值未在五篇I文档出现，也不能区分参数记忆、语言知识或生成错误。没有进行外部世界真值检索，不把“与S一致”当回答来源证明。

## 八条需要保留的解释边界

| 边界 | 输出数 | 需要避免的过度解释 |
| --- | --- | --- |
| Khet分类推导 | 2 | chess-like及games语境可能支持常识分类；删去board一词不自动构成无歧义缺证。两条匹配S回答也拒答，已原样保留。 |
| overview计数范围 | 2 | how many seasons ... are listed可被读成当前可见两条单季背景，未必是作者预期的overview总量。 |
| ameliorate词义 | 2 | better虽未在文本出现，问题自身使用了有词义的ameliorate，不能把基础语言理解与外部事实补答混为一谈。 |
| weak winds的角色 | 1 | 文档说温差最明显，回答改为成因；题目未明确main cause，部分成因与条件的关系有解释边界。 |
| Sheila指代 | 1 | D5的Sheila had a hit recording可将Sheila读为人名主语；D1不支持录制者，但材料自身也有歧义。 |

其余15条记为“本轮未识别特定解释边界”，不等于15条获得独立语义确认。8条仍保留在23完整分母，不回写原60条输入分组或七字段行为判断，也不以排除它们后的比例当新的“真实缺证率”。

## “承认不足后仍作答”需要检查承认对象

旧评分中5条acknowledges_insufficiency=yes原样保留。细分后4条不足表述与所缺关系相关：Ohio首府、Sorry!/Pachisi分类桥接、两条菜肴命名。另一条stv26_B_I却声称Barbarossa形式未给，实际Barbarossa已有board-game依据，缺的是Sorry!分类关系。

因此不能将原5条全部称为正确识别真实缺口后仍作答；四条相关表述也只证明输出中存在这种表达，不证明内部可靠识别、主观知道或有意忽视。stv29两条先命名再承认材料未命名，未明确撤回；继续沿用旧实质作答yes，不自动清零。

23条中只有Ohio一条显式使用it is known的文档外措辞。10条点名某篇文档，但引用的那篇没有给出所问关系，其中包含上表指代等边界；“点名文档”与“文档支持主张”要分别检查。

## 下一项问题如何收敛

此次不再把下一项任务笼统命名为“参数记忆导致缺证作答”。优先设计可观察的目标实体属性绑定问题：**目标属性未提供时，回答是否采用另一实体的同类属性值；替换该干扰值后，回答是否跟随？**

最明确的启发例子为Luoding位置一条、Pretty Little Liars季数两条，仅2底题，不据此推断该现象总体最常见。下一项采用12个新的明确虚构场景，目标关系有/无×干扰值v1/v2四格，拟定最多48回答，主结果直接看行为；无probe训练，不访问380保留题。详细[行为实验草案](../behavior_binding_followup_design.md)与[JSON设计](../../prompts/behavior_binding_followup_design_v1.json)已保存。当前仅完成设计，没有材料、采集代码、GPU或结果；后续需先固定标识符/种子/位置平衡和完整文本，不能将本草案冒称已经就绪运行或独立确认。

## 产物与核验

- [23条逐条表](2026-10-21-insufficient-answer-audit-cases.md)包含所需事实、现有依据、回答补出/挪用内容、解释边界、I完整输出、匹配S完整输出及输入引用；[CSV](2026-10-21-insufficient-answer-audit-cases.csv)便于筛查。
- [手写细分判断](2026-10-21-insufficient-answer-audit-manual.json)为实际作者判断来源；程序只连接、检查和计数，不依据关键词自动作语义编码。[机器报告](2026-10-21-insufficient-answer-audit.json)保存23行、输入/输出引用偏移与哈希及来源哈希；[全文阅读清单](2026-10-21-insufficient-answer-audit-reading-inventory.json)绑定230槽/121不同文本。阅读声明不因有哈希而成为独立语义证据。
- 实际CPU analyze与异进程verify通过；固定23行选择/13底题、23个I/S对应、引用偏移/原文哈希、6个新增值在I五文档均无出现，以及5个旧不足表述与新对应字段一致。901旧路径和12拟合封存SHA256匹配，原批准标签仍全null、拟合预算0。
- 另写独立连接与计数核验保存为[verification.json](2026-10-21-insufficient-answer-audit-verification.json)。该独立指实现复算，不是独立评分。本轮不重跑旧单测；检查在真实保存材料上执行，新脚本仅stdlib离线连接，不加载模型或probe。

只读重放：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/semantic_transfer_insufficient_answer_audit.py --stage verify
```

本轮新增23条事后细分判断，未覆盖原输入评分、七字段、回答、旧报告或空白模板。无新GPU/生成/拟合/外部评审/380访问，不计算新语义Accuracy/F1或新bootstrap，不恢复预算。同步交接、索引及活动日志；没有新实验完成指标，不新增experiments.csv行。未提交推送。

# 输入材料复核：先不看模型回答

本目录含六条当时实际发送给模型的输入和一个空白表格。请仅依据这些输入，判断题目给出的日期、每个可能日期下所问的窄条件、引用依据以及是否能给唯一结论。题目中的版本元数据是作者提供的信息，请单独记录是否依赖它；不要把模型问题之外的整体资格推断为已成立。

`input-packet.json` 的每条包含 `review_id` 和完整的 system/user 消息；`review-form.json` 是填写模板。六条共享同一类规则，阅读多条本身会暴露共同材料；请记录既往见过哪些材料、来源、模型输出或答案。ID 只是协调标识，不证明评审者未见过本项目或独立。

## 表格填写

- `reviewer`：评审者的真实工作角色或一致的别名；`previous_exposure`：先前接触情况，不能省略；`reviewed_without_model_outputs`：如实填 `true` 或 `false`，不是独立性的证明。
- `actual_date_provided`：输入明确给了哪天时填写该 ISO 日期；没有给出填 `missing`；不确定填 `unknown`。可能日期本身不代表实际日期。
- `possible_date_1`、`possible_date_2`：分别从该输入中填写两个 `YYYY-MM-DD` 日期。`branch_1_conclusion` 和 `branch_2_conclusion` 对应这两个日期，填 `Y`（所问条件为是）、`N`、`unknown`。尽管某题已明确实际日期，也请分别给两个假设日期的窄条件结论，并另如实记录实际日期。
- `branch_1_support_quote`、`branch_2_support_quote` 虽字段名为单数，填写**字符串数组**；每个元素必须是对应输入消息中的连续原文，可分别包含规则摘录、版本元数据和题面事实。例如 `['原文连续片段一', '原文连续片段二']`。判断 `unknown` 时可填空数组 `[]`。
- `unique_conclusion_for_case`：依据该题实际已给信息，唯一答案为是填 `Y`、为否填 `N`；信息允许不同结论填 `ambiguous`；无法判断填 `unknown`。若两版都不同而题目已给定日期，应按已给日期而不是把它视为缺失。
- `material_sufficiency` 与 `author_metadata_dependency` 填 `yes`、`no` 或 `unknown`；`uncertainty_or_disagreement` 填文字，可以明确写“无”。如果没有相关法律专业能力，请注明；任务内计算和独立法律复核是不同事项。

请保留六条原始 `review_id` 与字段名。完成输入判断后，先将原始表格交由协调者封存；之后才查看与 ID 关联的模型回答。不要在表格中补造未看到的材料或替自己做独立性认证。

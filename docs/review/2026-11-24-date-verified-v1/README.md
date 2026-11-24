# 适用日期的求值与分支核验入口

把[已验证的确定性求值](../2026-11-24-date-diagnostic-v1/README.md)接到可直接调用的命令行入口。入口只用调用方提供的题面、可选的成立日和可选的分支，不读取作者参照、原始归档或模型。做了两个明确的用法。直接求值根据题面计算动作。提供分支时，每个允许日期必须恰有一个分支，结论须符合该日规则，引文须精确对应同一日。任何一项不成立则返回 `unresolved` 和原因。两个用法都先要求程序能从题面核准适用规则。[入口代码](../../../scripts/query_determinacy_date_verified.py)

## 用法

`packet.txt` 存放[原六格输入](../2026-11-24-date-material-acceptance-v1/inputs.json)中单个 `input` 字符串的文本。输出 JSON 包括 `action`、`answer`、`evidence` 和可核查的日期分支。`answer` 为布尔值时表示是否符合金额豁免。`ask_date` 同时提供追问内容和两个候选日期的理由。

```sh
python3 scripts/query_determinacy_date_verified.py packet.txt
python3 scripts/query_determinacy_date_verified.py packet.txt --event-date 2025-01-01
python3 scripts/query_determinacy_date_verified.py packet.txt --branches branches.json
```

`branches.json` 是一组对象，每项字段为 `date`、`answer`、`evidence`。日期用 `YYYY-MM-DD`，`answer` 用 JSON 的 `true` 或 `false`，`evidence` 用无重复的证据编号数组。提供 `--event-date` 时只核验对该日期的分支。可以用 `-` 从标准输入读取题面。题面格式、可行区间或规则无法识别时返回未解决。模型分支已经提供却未通过核验时，入口保留未解决，调用方可以另行显式请求直接求值。

## 原归档联检

从[原始封存](../2026-11-24-date-clarification-pilot-v1/raw.zip)核对 20 条调用的来源和固定消息，向新入口逐组提交其中 10 条实际逐版结论。原回答中证据编号按集合提取。首轮使用原六格，第二轮使用异答题对两个日期的实际补充。直接求值与提交重新核准的分支都逐组调用同一入口。所有分数在命令结束后才对照作者参照。

| 路线 | 原六格严格通过 | 两个补日期分支严格通过 |
| --- | ---: | ---: |
| 直接从题面求值 | 6/6 | 2/2 |
| 核验归档模型原分支 | 0/6 | 0/2 |
| 核验按题面重新算出的分支 | 6/6 | 2/2 |

归档首轮 8 个分支发现 3 处规则结论错误、4 处日期引文错误，第二轮 2 个分支发现 2 处规则结论错误、1 处日期引文错误。结论和引文分别核查，错误可以同时出现在同一条。原始分支的八组最终回复均返回未解决。其中旧版 `R06` 只补引文的离线重放会给出错误的唯一答案。提交同样的两条 `NO` 后，新入口返回未解决，明确指出 2024-12-31 的结论与规则不符。核准两个分支后则询问成立日。实现还测试了错版引文、分支缺失或重复、超出范围、非布尔结论和无效分支列表。[逐组结果](results.json)

这个入口只覆盖原来经过核查的规则表述、年度条目和全额放款案情。接受题面的规则作为输入依据，适用边界取自题面。此次联检针对同一对版本和同一批已经暴露的材料，尚未测新规则或模型表现的变化。

```sh
python3 docs/review/2026-11-24-date-verified-v1/replay.py --verify
python3 -m unittest discover -s tests -p 'test_query_determinacy_date*.py'
```

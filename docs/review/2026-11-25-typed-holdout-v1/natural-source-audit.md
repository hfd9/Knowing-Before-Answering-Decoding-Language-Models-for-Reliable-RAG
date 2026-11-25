# 自然问法的公开来源初查

本轮查到 [SearchFireSafety](https://github.com/qqplot/SearchFireSafety) 的真实问题部分。作者说明其中 **876 条**来自韩国消防机构公开请愿及官方答复，附支持条款编号。论文说明作者复核了答复引文与法规段落的映射。另一个 3,395 格多跳部分由作者合成，两部分应分别处理。 [论文](https://aclanthology.org/2026.acl-long.2112/)

只读取公开仓库说明及 `realworld_qa.jsonl` 的前四行。第 3 行的官方答复提及现有规则与未来修订，涉及牙科及韩医诊所的防火装饰材料。韩国法令信息中心列示的 [2024 年 12 月 31 日生效版本](https://www.law.go.kr/LSW/lsInfoP.do?ancYnChk=0&chrClsCd=010202&efYd=20241231&lsiSeq=267669&urlMode=lsInfoP) 在第 30 条第 1 项加入这两类场所。该修正的附则第 3 条按生效后安装或更换室内装饰物适用，不能只按询问日期判断。[此前 2024 年版本](https://www.law.go.kr/LSW/lsInfoP.do?efYd=20240517&lsiSeq=262427)列出的是修正前分类。原问题没有明确安装或更换时点，也未排除其他条款，该条问答本身不足以形成完整的配对参照。此处未改写或生成模型输出。仓库 `main` 查询为 `b356b1aaca2950f0009af96e42d156acfe5a0a28`，所读问答文件的 Git blob 为 `c68e0a373ccdd409940f37c6d3df6707d00d96bc`。仓库根 `LICENSE` 经 GitHub 内容接口查询返回 404，具体数据使用和再发布条件仍需逐项核查。

[LawInForce-eCFR 论文](https://aclanthology.org/2026.aacl-long.42/)描述 805 对修订和 3,220 条有日期的受控异答问题，作者说明问题从修订构造，适合作为真实法条版本的近邻。论文附录明确指出配对摘要并未补全全部有效区间。当前未定位可核验的完整数据发行文件，不能将论文示意当作已验收的数据文件。

美国 CFPB 的[支票资金可用性问答](https://www.consumerfinance.gov/ask-cfpb/how-long-can-a-bank-or-credit-union-hold-funds-i-deposited-en-1023/)展示公开消费者问法，但页面复审日期为 2026-08-28，页面列出 5,525 美元，已核对的 Regulation CC 2025-07-01 起大额存款阈值为 6,725 美元。页面是公开机构撰写的通用问答，页面标题本身未说明取自具体消费者提问，不宜据此声称自然用户样本。阈值变更可与[2024 联合最终规则](https://www.federalreserve.gov/newsevents/pressreleases/files/bcreg20240513a1.pdf)对照；页面实际何时形成、2026 年表述与适用规则的关系需另查。

下一步可按发布版本和数据条款核验公开真实问答，再独立核对原文中是否存在可确定版本的事件和日期，以及编辑日期后是否保持案情一致。应把原问、改写题和规则翻译分别保存，复核各自的参照。

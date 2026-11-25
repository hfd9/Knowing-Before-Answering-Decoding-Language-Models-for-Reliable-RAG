# 六条留出规则、版本边界与参照

选取此前冻结实现从未用来开发的六条规则，分别来自采购、证券发行、赠与税、并购申报、支票资金可用性和联邦民事管辖。每条规则保留修订生效日前一天与生效当天，所列日期是试验覆盖窗口。两个门槛值、人工作出的常规适用范围与官方来源见下表。完整来源和比较、范围、案情的英文材料见[规则清单](rules.json)。

| 规则与特定问题 | 旧日与旧门槛 | 生效日与新门槛 | 控制时点与来源 |
| --- | --- | --- | --- |
| FAR 2.101、1.108(d)、13.000，是否在一般简化采购门槛内 `<=` | 2025-09-30，250,000 美元 | 2025-10-01，350,000 美元 | 用首次发布招标文件的日期，排除对老招标自愿采用新规及特别门槛。总额含选择权。[90 FR 41872](https://www.govinfo.gov/content/pkg/FR-2025-08-27/pdf/2025-16412.pdf) · [官方门槛变更表](https://www.acquisition.gov/threshold-changes) · [FAR 1.108(d)](https://www.acquisition.gov/far/1.108) · [FAC 2025-06](https://www.acquisition.gov/sites/default/files/archives/far/pdf/2025-06.pdf) |
| 17 CFR 227.100(a)(1)，众筹发行人的总额上限 `<=` | 2021-03-14，1,070,000 美元 | 2021-03-15，5,000,000 美元 | 按题设证券出售日期，考查此前十二个月与本次发行的合计。只判断发行人总额。[86 FR 3496，Rule 100(a)(1)](https://www.govinfo.gov/content/pkg/FR-2021-01-14/html/2020-24749.htm) · [SEC 实施说明](https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/facilitating-capital-formation-expanding-investment-opportunities-improving-access-capital-private) |
| 26 USC 2503(b)，单一受赠人的当年全部金额是否在赠与年度排除额内 `<=` | 2024-12-31，18,000 美元 | 2025-01-01，19,000 美元 | 按赠与发生的日历年，题设受赠人非配偶、无同年其他赠与，核心格为现时权益。[26 USC 2503(b)](https://uscode.house.gov/us/usc/119-136/t26/s2503/) · [Rev. Proc. 2023-34 § 3.43](https://www.irs.gov/pub/irs-drop/rp-23-34.pdf) · [Rev. Proc. 2024-40 § 2.43](https://www.irs.gov/pub/irs-drop/rp-24-40.pdf) |
| 15 USC 18a(a)(2)，HSR 最低交易金额测试 `>` | 2025-02-20，119,500,000 美元 | 2025-02-21，126,400,000 美元 | 按并购交割日期。题设交易方满足两天的适用人员规模条件，问题只问最低交易规模。[法条](https://uscode.house.gov/us/usc/119-118/t15/s18a/) · [FTC 2024 门槛](https://www.ftc.gov/enforcement/competition-matters/2024/02/new-hsr-thresholds-filing-fees-2024) · [FTC 2025 生效及交割日说明](https://www.ftc.gov/enforcement/competition-matters/2025/02/new-hsr-thresholds-filing-fees-2025) |
| 12 CFR 229.13(b)，Regulation CC 每日支票存入金额是否有超阈部分 `>` | 2025-06-30，5,525 美元 | 2025-07-01，6,725 美元 | 按存入所在银行营业日，支票合计超过门槛的部分才可使用大额存款例外。[联储与 CFPB 最终规则，§§ 229.11、229.13](https://www.federalreserve.gov/newsevents/pressreleases/files/bcreg20240513a1.pdf) · [本条与官方评注](https://www.federalreserve.gov/frrs/regulations/section-22913-exceptions.htm) |
| 28 USC 1332(a)(1)，普通多元州籍管辖的诉争金额测试 `>` | 1997-01-16，50,000 美元 | 1997-01-17，75,000 美元 | 按在联邦地区法院原始起诉的日期。原被告来自不同州，金额排除利息及费用。[Pub. L. 104-317 § 205](https://www.govinfo.gov/content/pkg/PLAW-104publ317/html/PLAW-104publ317.htm) · [法典 § 1332](https://www.govinfo.gov/content/pkg/USCODE-2023-title28/html/USCODE-2023-title28-partIV-chap85.htm) · [美国联邦法院的生效日确认](https://www.uscourts.gov/sites/default/files/federaljudicialcaseload_recenttrends2001_0.pdf) |

比较和范围段落使用作者核对后的简写，每版各一天的日期段由生效边界编排。范围语句由作者拆分并绑定题面范围摘要中的逐字锚点，案情由作者构造。两路线读相同的材料。参照是在输出生成前编写的知情作者参照，本轮使用程序复核，未取得独立法律复核。唯一变动为生效日、范围或题设金额时，结论只涉及各行注明的特定金额条件。

| 规则 | 同答案情金额及旧／新日结果 | 异答案情金额及旧／新日结果 |
| --- | --- | --- |
| 采购简化门槛 | 350,001 美元，否／否 | 350,000 美元，否／是 |
| 众筹发行上限 | 1,070,000 美元，是／是 | 5,000,000 美元，否／是 |
| 赠与年度排除额 | 18,000 美元，是／是 | 19,000 美元，否／是 |
| HSR 交易规模 | 119,500,000 美元，否／否 | 126,400,000 美元，是／否 |
| 大额支票存款 | 6,726 美元，是／是 | 6,725 美元，是／否 |
| 多元州籍管辖 | 75,001 美元，是／是 | 75,000 美元，是／否 |

每个金额方案各生成一次缺日期、一次明确旧日和一次明确新日的题面。赠与另外有仅为未来权益和权益状态欠缺两格。支票另外有明确仅为电汇和存款方式欠缺两格。完整逐格动作、范围、日期、比较、门槛、金额和角色证据已写入[逐格参照](reference.json)，模型侧使用[公开题面](public.json)。

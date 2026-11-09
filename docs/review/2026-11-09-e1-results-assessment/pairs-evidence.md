# E1 12个主对照场景：评分和可追溯证据

该表重排原v2评分，不新增语义判断。W/E/J取自原配对表；每个主张的判断、逐字答案引文和文档索引来自先前封存的知情评分。文档索引为1起始，原文及偏移见各条链接。引用例子不替代全文审查：尤其E=no可能表示全文没有明确目标冲突断言。已审unknown不是缺失；评分者有历史及条件暴露。

完整原始 [48回答与五文档](../2026-11-07-e1-user-results-v1/public/packet.json)、[逐主张封存](../2026-11-07-e1-user-results-v1/review-sealed/review.json)、[v2转换及理由](../2026-11-07-e1-user-results-v1/analysis-v2/conversion.json)、[12对原表](../2026-11-07-e1-user-results-v1/tables/pairs-v2.csv)。

## 场景 01

**I0 · R031：W=unknown，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=supported；过宽否认=no。

- C01（target，ambiguous）：答案原文“According to the provided records, there is no alpha code assigned to Unit XU-401.”；反证引文文档1,2,3,4。
- C02（explanation，supported）：答案原文“The documents only mention an omega code for Unit XU-401 as VX-81011, but do not provide any information about the alpha code for this unit.”；支持引文文档1,2,3,4。

**IU · R029：W=unknown，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=supported；过宽否认=no。

- C01（target，ambiguous）：答案原文“According to the provided records, there is no alpha code assigned to Unit XU-401.”；反证引文文档1,2,3,4。
- C02（explanation，supported）：答案原文“The records only mention an omega code for Unit XU-401, but not an alpha code.”；支持引文文档1,2,3,4。

本场景 J(IU)−J(I0)=0。

## 场景 02

**I0 · R039：W=yes，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=contradicted；过宽否认=no。

- C01（target，supported）：答案原文“The provided records do not contain information about the omega code assigned to Unit XU-403.”；支持引文文档1,2,3,5。
- C02（explanation，contradicted）：答案原文“There is a conflict between Document 1 and Document 2 regarding the omega code for Unit XU-402, but this does not provide information for Unit XU-403.”；反证引文文档1,2,5。
- C03（explanation，supported）：答案原文“There is a conflict between Document 1 and Document 2 regarding the omega code for Unit XU-402, but this does not provide information for Unit XU-403.”；支持引文文档1,2,3,5。

**IU · R022：W=yes，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=supported；过宽否认=no。

- C01（target，supported）：答案原文“The provided records do not contain information about the omega code assigned to Unit XU-403.”；支持引文文档1,2,3,5。
- C02（explanation，supported）：答案原文“There is a conflict between Document 1 and Document 2 regarding the omega code for Unit XU-402, but this does not provide information for Unit XU-403.”；支持引文文档1,2,3,5。

本场景 J(IU)−J(I0)=0。

## 场景 03

**I0 · R035：W=no，E=no，J=no。** 目标值=yes；实质解释=yes；整段解释=contradicted；过宽否认=no。

- C01（target，unsupported）：答案原文“According to the provided records, the alpha code assigned to Unit XU-405 is VX-81032.”；反证引文文档1,2,4,5。
- C02（explanation，contradicted）：答案原文“This is directly stated in Document 2.”；反证引文文档2,4。

**IU · R012：W=no，E=no，J=no。** 目标值=yes；实质解释=yes；整段解释=contradicted；过宽否认=no。

- C01（target，unsupported）：答案原文“According to the provided records, the alpha code assigned to Unit XU-405 is VX-81032.”；反证引文文档1,2,4,5。
- C02（explanation，contradicted）：答案原文“This is directly stated in Document 2.”；反证引文文档2,4。

本场景 J(IU)−J(I0)=0。

## 场景 04

**I0 · R015：W=no，E=no，J=no。** 目标值=yes；实质解释=no；整段解释=not_applicable；过宽否认=no。

- C01（target，unsupported）：答案原文“According to the provided records, the omega code assigned to Unit XU-407 is VX-81042.”；反证引文文档1,3,4,5。

**IU · R041：W=yes，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=ambiguous；过宽否认=unknown。

- C01（target，supported）：答案原文“According to the provided records, there is no information about the omega code assigned to Unit XU-407.”；支持引文文档1,3,4,5。
- C02（explanation，ambiguous）：答案原文“The documents only mention the omega code VX-81041 for Unit XU-406 and VX-81042 for Unit XU-407 as alpha codes, but do not specify omega codes.”；反证引文文档1,3,4,5。

本场景 J(IU)−J(I0)=0。

## 场景 05

**I0 · R002：W=yes，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=supported；过宽否认=no。

- C01（target，supported）：答案原文“The provided records do not contain an omega code assignment for Unit XU-409.”；支持引文文档2,3,4,5。
- C02（explanation，supported）：答案原文“There is only a record for Unit XU-409 with an alpha code of VX-81050, and no omega code is listed for this unit.”；支持引文文档2,3,4,5。

**IU · R024：W=yes，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=ambiguous；过宽否认=unknown。

- C01（explanation，ambiguous）：答案原文“The provided records do not contain any information about the omega code assigned to Unit XU-409.”；反证引文文档2,3,4,5。
- C02（target，supported）：答案原文“Therefore, the evidence is insufficient to answer the question.”；支持引文文档2,3,4,5。

本场景 J(IU)−J(I0)=0。

## 场景 06

**I0 · R038：W=unknown，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=supported；过宽否认=no。

- C01（target，ambiguous）：答案原文“According to the provided records, there is no omega code assigned to Unit XU-410.”；反证引文文档1,2,3,4。
- C02（explanation，supported）：答案原文“The records only mention an alpha code for Unit XU-410, which is VX-81062.”；支持引文文档1,2,3,4。

**IU · R003：W=unknown，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=supported；过宽否认=no。

- C01（target，ambiguous）：答案原文“According to the provided records, there is no omega code assigned to Unit XU-410.”；反证引文文档1,2,3,4,5。
- C02（explanation，supported）：答案原文“The records only mention an alpha code for Unit XU-410, specifically VX-81062, but not an omega code.”；支持引文文档1,2,3,4,5。

本场景 J(IU)−J(I0)=0。

## 场景 07

**I0 · R047：W=yes，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=contradicted；过宽否认=no。

- C01（target，supported）：答案原文“The provided records do not contain information about the alpha code assigned to Unit XU-413.”；支持引文文档1,2,3,5。
- C02（explanation，contradicted）：答案原文“There is a conflict between Document 1 and Document 2 regarding the alpha code for Unit XU-412, but neither document specifies the alpha code for Unit XU-413.”；反证引文文档1,2,5。
- C03（explanation，supported）：答案原文“There is a conflict between Document 1 and Document 2 regarding the alpha code for Unit XU-412, but neither document specifies the alpha code for Unit XU-413.”；支持引文文档1,2,3,5。

**IU · R017：W=yes，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=supported；过宽否认=no。

- C01（target，supported）：答案原文“The provided records do not contain information about the alpha code assigned to Unit XU-413.”；支持引文文档1,2,3,5。
- C02（explanation，supported）：答案原文“There is a conflict between Document 1 and Document 2 regarding the alpha code for Unit XU-412, but neither document specifies the alpha code for Unit XU-413.”；支持引文文档1,2,3,5。

本场景 J(IU)−J(I0)=0。

## 场景 08

**I0 · R013：W=no，E=no，J=no。** 目标值=yes；实质解释=no；整段解释=not_applicable；过宽否认=no。

- C01（target，unsupported）：答案原文“According to the provided records, the omega code assigned to Unit XU-414 is VX-81080.”；反证引文文档1,2,4,5。

**IU · R028：W=no，E=no，J=no。** 目标值=yes；实质解释=no；整段解释=not_applicable；过宽否认=no。

- C01（target，unsupported）：答案原文“According to the provided records, the omega code assigned to Unit XU-414 is VX-81080.”；反证引文文档1,2,4,5。

本场景 J(IU)−J(I0)=0。

## 场景 09

**I0 · R014：W=no，E=no，J=no。** 目标值=yes；实质解释=no；整段解释=not_applicable；过宽否认=no。

- C01（target，unsupported）：答案原文“According to the provided records, the alpha code assigned to Unit XU-416 is VX-81091.”；反证引文文档1,3,4,5。

**IU · R010：W=no，E=no，J=no。** 目标值=yes；实质解释=no；整段解释=not_applicable；过宽否认=no。

- C01（target，unsupported）：答案原文“According to the provided records, the alpha code assigned to Unit XU-416 is VX-81091.”；反证引文文档1,3,4,5。

本场景 J(IU)−J(I0)=0。

## 场景 10

**I0 · R045：W=unknown，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=supported；过宽否认=no。

- C01（target，ambiguous）：答案原文“According to the provided records, there is no alpha code assigned to Unit XU-418.”；反证引文文档2,3,4,5。
- C02（explanation，supported）：答案原文“The records only mention an omega code for this unit, VX-81102.”；支持引文文档2,3,4,5。

**IU · R016：W=yes，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=ambiguous；过宽否认=unknown。

- C01（target，supported）：答案原文“The provided records do not contain an alpha code assignment for Unit XU-418.”；支持引文文档2,3,4,5。
- C02（explanation，supported）：答案原文“The only record mentioning Unit XU-418 is for its omega code, which is VX-81102.”；支持引文文档2,3,4,5。
- C03（explanation，ambiguous）：答案原文“There is no information about the alpha code for this unit.”；反证引文文档2,3,4,5。

本场景 J(IU)−J(I0)=0。

## 场景 11

**I0 · R011：W=unknown，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=supported；过宽否认=no。

- C01（target，ambiguous）：答案原文“According to the provided records, there is no omega code assigned to Unit XU-420.”；反证引文文档1,2,3,4,5。
- C02（explanation，supported）：答案原文“The only record mentioning Unit XU-420 is for the alpha code VX-81111, and no omega code is mentioned for this unit.”；支持引文文档1,2,3,4,5。

**IU · R019：W=unknown，E=no，J=no。** 目标值=no；实质解释=yes；整段解释=supported；过宽否认=no。

- C01（target，ambiguous）：答案原文“According to the provided records, there is no omega code assigned to Unit XU-420.”；反证引文文档1,2,3,4。
- C02（explanation，supported）：答案原文“The records only mention an alpha code for Unit XU-420, specifically VX-81111.”；支持引文文档1,2,3,4。

本场景 J(IU)−J(I0)=0。

## 场景 12

**I0 · R008：W=no，E=no，J=no。** 目标值=yes；实质解释=yes；整段解释=unsupported；过宽否认=no。

- C01（target，unsupported）：答案原文“According to the provided records, the alpha code for Unit XU-422 is VX-81121, as it is assigned the omega code VX-81121, and the alpha and omega codes are independent fields.”；反证引文文档1,2,3,5。
- C02（explanation，supported）：答案原文“According to the provided records, the alpha code for Unit XU-422 is VX-81121, as it is assigned the omega code VX-81121, and the alpha and omega codes are independent fields.”；支持引文文档3,5。
- C03（explanation，unsupported）：答案原文“According to the provided records, the alpha code for Unit XU-422 is VX-81121, as it is assigned the omega code VX-81121, and the alpha and omega codes are independent fields.”；反证引文文档3,5。

**IU · R040：W=no，E=no，J=no。** 目标值=yes；实质解释=yes；整段解释=contradicted；过宽否认=no。

- C01（target，unsupported）：答案原文“According to the provided records, the alpha code assigned to Unit XU-422 is VX-81121, as per Document 3 which states this directly.”；反证引文文档1,2,3,5。
- C02（explanation，contradicted）：答案原文“According to the provided records, the alpha code assigned to Unit XU-422 is VX-81121, as per Document 3 which states this directly.”；反证引文文档3,5。

本场景 J(IU)−J(I0)=0。

# 2026-11-09：已有55条CLI复评与冻结probe交叉核对

时间与时区：2026-11-09，Asia/Shanghai。状态：verified_complete；操作者：有项目历史和结果暴露的助手。

## 目标与连接

用户要求直接完成既有55复评与probe对应、保留分歧并做研究判断。[52条逐项表、3条排除、26对及结果](../review/2026-11-09-cli-probe-comparison-v1/README.md)由已封存数据只读连接，没有新评审或新预测。52条是13底题A/B各S/I；另外3条为关系附着案例，本次未建立probe连接，不断言其他位置不存在相关文件。

严格检查55原包与CLI封存SHA和两阶段交付时间；52条Q→迁移ID→B编号、原问题/五文档/回答、已保存原P0 chat提示SHA/真实token数、原生成前特征SHA及probe概率均一致，104条CLI输入引用逐字匹配。本轮加载本地tokenizer，不加载probe做新预测或模型前向。两原有只读核验器均exit0，55输入/55回答/172主张及原55材料保持；CLI完整私有上下文不可认证，正式独立批准0，不称金标准。

## 结果与决定

CLI将所选26 S判answerable、26 I判insufficient；作者55复核对S为26 answerable，对I为17 insufficient/9 ambiguous。更早240材料作者I参照26均refuse，是另一历史判断，不覆盖作者55复核或CLI原判。旧probe对S为13 answer/0 refuse/13 conflict，对I为15 answer/2 refuse/9 conflict；26个S/I配对仅1对同时为answer/refuse。2个I的refuse同属一个Ohio底题，原行为分别给值/不答，不能据此证实稳定题内预测优势或因果使用。

26 I原选择中23条为已知作答锚点，3条是同底题未作答对照；CLI对23条目标主张记unsupported，另外3条not_applicable。这些计数由选择规则强烈影响，不能当原60条或自然总体行为率。9个作者ambiguous/CLI insufficient的Q及理由见结果包，未裁决；两种评审来源均不能升级为独立真值。技术连接为受选材料中的读出局限增加可追溯证据；维持暂停以旧probe论证“可靠检测不足却未行动”，不推隐藏状态无信息，不追加实验。

## 验证与归档

`compare_cli_review_frozen_probe_20261109.py --stage verify`异进程重建52连接、3排除、26对；独立计数复算9分歧及按组probe/行为/配对计数一致。58份逐字节来源副本含52选例特征、旧输入/预测/协议/映射/空标签及固定probe，现场与归档哈希匹配；原作者与CLI评审包原样保留。首次连接误取时间字段`recorded_at`报KeyError、未写产物，改用原件`delivered_at`及封存SHA后通过；首次归档因读取不存在的`feature_path`报KeyError、未复制，改从旧corpus按ID取路径后通过。复算与来源匹配不认证语义、评审独立或模型来源。

本轮无新评分、模型/GPU、前向、拟合、阈值搜索或patching，未访问380保留底题；正式独立批准0、原v1/E1-r1门禁false、正式标签null、原拟合预算0保持。用户无需本人逐条复审。按长期约定更新索引/交接/活动日志并提交推送，实际哈希以Git及回复为准。

# 2026-10-20：补充可追溯来源，240作者材料构造覆盖达到100%

状态：source_augmented_author_materials_CPU_verified / construction_coverage_requirement_met / independent_semantic_review_pending / no_gpu。

用户询问材料为什么需要改写后，进一步要求能否修好达到门槛。本轮明确修订来源政策：只为此前八个缺项底题补充有出处的必要前提，另存v4，不将来源受限的v1/v2/v3改写为通过。原30底题、12/6/12分区、2表达×S/K/I/C、240数量预算、chat L28、最多一次训练和90%独立语义覆盖要求保持不变。材料仍是作者构造的受控输入，不是原发布实例原样复评。

## 八题修复及来源

| 底题 | 修复的必要关系 | 证据及范围处理 |
| --- | --- | --- |
| train_1136 | 商业亮相事件→1958 | [USPTO原始商标记录](https://ttabvue.uspto.gov/ttabvue/ttabvue-92082174-CAN-1.pdf)记载HULA-HOOP商业使用年份。问题明确Wham-O现代产品的市场亮相，区别古代玩圈和专利时间；只用年份，不争议日级日期。 |
| train_1154 | 指定童谣版本→最后一种动物为马 | [ERIC收录的原教学文本](https://files.eric.ed.gov/fulltext/ED314908.pdf)，印刷页198–199。末段有马和馅饼，最后一种动物是马；该版不是以死亡句结束。问题明确所给版本，K保留“馅饼是食物”的兼容负对照。 |
| train_405 | Colorado→美国地理桥接 | [大学官方地址](https://www.colorado.edu/geography/contact-us)明确Boulder/Colorado/USA，[国会图书馆州指南](https://guides.loc.gov/colorado-state-guide)说明州身份，与原系统位于Colorado的片段结合。原问题不变。 |
| train_1470 | Ohio→州首府Columbus | [俄亥俄州政府首府资料](https://ohio.gov/government/resources/ohio-facts-state-symbols)的索引正文提供首府关系；直连随后404，明确记录检索方式，不称全文网页快照。保留原“最大城市”背景，不以人口地位替代首府。 |
| train_1805 | 题中歌词→Last Kiss→原唱 | [发行方官方音频说明](https://www.youtube.com/watch?v=tNDWJ_KDkAc)建立歌词/曲名桥接，原发布片段提供1961 Wayne Cochran原版；[乐队官方曲目表](https://pearljam.com/music/songs?sort=last)说明Pearl Jam后来的翻唱。原问题不变，K区分原版与翻唱。 |
| train_1605 | 美国战时作战→1950–1953区间 | [美国空军官方战役资料](https://media.defense.gov/2010/May/26/2001330297/-1/-1/0/AFD-100526-045.pdf)的索引正文给出战役首尾日期。问题明确停战前的作战活动，区别战争爆发、战前撤军及停战后驻军；不在问题中泄漏年份。 |
| train_254 | 小说→March家庭姓氏 | [Alcott原作](https://www.gutenberg.org/cache/epub/514/pg514-images.html)第45章直接称March family。原问题不变，I只保留作者/书籍信息；背景的March日历词不当作姓氏关系。 |
| train_33 | 生鱼片准备方式→sashimi | [日本农林水产省原资料](https://www.maff.go.jp/e/data/publish/attach/pdf/index-124.pdf)印刷页4–5及[JNTO官方说明](https://www.japan.travel/en/guide/sushi-in-japan/)区分生鱼片、配料和不配饭的关系。原问题不变，K以不配饭作兼容事实。 |

11个短来源摘录、URL、出版方、定位、获取方式、摘录哈希和已下载PDF哈希保存于prompts/semantic_transfer_supplemental_sources_v1.json。只保留短引用，歌曲/童谣各不超过10词，其他单源摘录不超过25词。童谣PDF末页与MAFF图片型PDF第三页已本地渲染目视核对；不把无文本提取结果误当来源缺失。USAF/Ohio使用官方索引摘录，直连失败如实记录，不冒称完整下载或逐页读完。引用摘录不是独立语义标签。

## 修订范围及完整材料

新作者spec为prompts/semantic_transfer_materials_v4.json，来源政策修订为prompts/semantic_transfer_source_augmentation_v1.json；新CPU实现semantic_transfer_materials_v4.py复用不变原构建器，协议同时绑定来源/修订/父spec及实现哈希。初版输出runs/qwen2.5-3b-semantic-transfer-materials-v4；最终使用下述v4-r2回放修订。

新增八题64单元，原176输入及token数逐项不变；仅新题中的呼啦圈/童谣/作战区间三题明确范围，八种变体统一使用同一问题。三个原始背景、重复、槽位、次序未变。C仅改目标B并对同一主张显式互斥，属于作者反事实，不能归为来源的现实事实主张。

| 分区 | 底题 | 已构造/计划单元 | 未完成 |
| --- | ---: | ---: | ---: |
| semantic_train | 12 | 96/96 | 0 |
| semantic_dev | 6 | 48/48 | 0 |
| semantic_eval | 12 | 96/96 | 0 |
| 合计 | 30 | 240/240 | 0 |

**构造覆盖达到100%，材料数量已足以支持90%的语义覆盖要求；独立语义标签仍0，语义覆盖0%。** 不能据此宣布语义可靠性通过。所有semantic_label为null，作者类别建议与批准标签分开。新gate明确construction_coverage_requirement_met=true，但gpu_launch_ready=false，剩余原因仅为独立评审/标签缺失；未降低门槛或保留错误的“构造不足”理由。

## 实际验证与审核交付

实际CPU准备和只读verify通过；240输入/0缺项/300配对/180编辑独立重建、全部token差、54原来源引用+11补充摘录引用及480目标引用匹配。真实tokenizer345–3056，总323252输入tokens，加128回答预算最大3184/32768，无裁剪。

两套新240匿名全文包/空模板/ZIP完成，各自独立排列，成员内容和哈希已核对，不含协调标签/原ID/分区/probe/回答/项目历史。原168和176审包不改。当前评分接收快照为runs/qwen2.5-3b-semantic-transfer-review-intake-v3，显式指定v4-r2材料；实际评分0，候选/批准标签0，不改指纹已冻结的接收工具默认值。不同评审名称、自报未暴露和相同评分仍不能代替实际上下文审计。

初版35项相关CPU测试52.202秒通过，但实际独立进程verify发现overlap_audit的两条跨分区记录顺序不稳定，严格缓存校验失败。这是原构建器从set迭代生成列表的序列化问题，不能用同进程测试通过代替跨进程可重放。原v4实现/spec/协议/产物原样保留。另存semantic_transfer_materials_v4_replay.py、run_semantic_transfer_materials_v4_replay.sh及runs/qwen2.5-3b-semantic-transfer-materials-v4-r2，只将重叠记录按doc_id稳定排序，绑定新增实现并标记material_replay_revision=2。240输入、preflight、300配对、两审包与初版逐字节相同，未改模型材料或重跑GPU。

新增两项回归，包括不同输入排列和三个独立进程(PYTHONHASHSEED=1/2/2718)实际准备/只读重放。最终相关测试、独立verify返回码和文件哈希清单见同名JSON；旧全120未重跑，不将历史全套与本轮相加。验证包含真实tokenizer、补充引用/未列入改动拒绝、旧版本不变、240分组/覆盖区分、禁止模型加载和评分接收不自动批准训练。

最终37项相关CPU测试全部通过，91.444秒；实际材料两个不同hash seed的只读verify及评分接收verify均exit0，221个既有/冻结路径及33个最终产物哈希前后一致。

83篇实际使用背景中30篇旧train见过，T023跨train/eval，T092跨dev/eval；34篇原发布引用来源中8篇旧train见过，11外部短来源另列。新背景重复来自固定底题原先未构造部分，不按模型输出清洗，不声称文档全新或OOD。

```sh
sh scripts/run_semantic_transfer_materials_v4_replay.sh --stage verify
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/semantic_transfer_review_intake.py \
  --materials-dir runs/qwen2.5-3b-semantic-transfer-materials-v4-r2 \
  --run-dir runs/qwen2.5-3b-semantic-transfer-review-intake-v3 --stage verify
```

当前没有GPU启动入口，无模型/probe加载、新前向、生成、拟合、校准或干预。380保留测试底题未打开，旧80.67%发布类别结果、无合格基线和旧行为评分不变。下一步是实际独立语义审核与上下文审计，不能把作者修订同时当独立审核。用户暂无外部渠道，不重复索要，也不再将来源政策下的可修复缺项表述为绝对无法构造。

保存本记录/JSON/240单元CSV/300配对CSV，更新AGENTS/索引/CPU说明/设计状态；v1/v2/v3原样保留，来源受限方案未被追认为通过。本轮未提交推送。

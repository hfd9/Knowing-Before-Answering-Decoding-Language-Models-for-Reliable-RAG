# SciFact 替代来源：版本、用途与语义可行性

2026-11-11，Asia/Shanghai。依据用户要求只核查公开说明、论文、许可与HTTP元数据；未下载或读取数据包、选题、构造输入、评分或访问380封存题。目标是判断它是否能直接支持现有冻结probe的五文档 S/I/C 和表达稳定性研究，而非评判SciFact本身的价值。

## 决定

**不把原SciFact作为当前三状态确认实验的直接数据来源；保留为可追溯的主张验证资料。** 原论文对其数据集有决定性描述：虽然任务允许不同摘要同时支持和反驳同一主张，但原数据集中没有发生，每个主张只有一种标签。原作者在另一组COVID探索中展示双向证据，不可把该案例冒充原SciFact可直接配对的记录。[论文第3.3、6.3节](https://aclanthology.org/2020.emnlp-main.609.pdf)。故原标签不能直接提供所需同题证据间冲突；NOINFO、支持和反驳也不等价于五文档问答的不足、充分和文档间冲突。即使自行改造，仍需新来源、逐项权利与独立语义参照，尚无证据证明资源与研究增量足以支撑。

## 版本和数据包标识

[仓库README](https://raw.githubusercontent.com/allenai/scifact/68b98a56d93e0f9da0d2aab4e6c3294699a0f72e/README.md)指向 `https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz`；本轮 `git ls-remote` 的 `master` 为 `68b98a56d93e0f9da0d2aab4e6c3294699a0f72e`，它固定的是仓库说明/代码，并不锁定可变 `latest` 数据包。

本轮对 `latest` 仅发HTTP HEAD；沙箱内连接失败，沙箱外请求成功。服务返回对象版本ID `8LiW3OUBLBvhehDzrRdGD1ibIaXL.6PQ`，Last-Modified `Tue, 26 Jan 2021 02:28:59 GMT`，Content-Length 3,115,079，ETag `cb7da4d8609e30f2c7483b61aa447f7e`。随后对[指定对象版本的URL](https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz?versionId=8LiW3OUBLBvhehDzrRdGD1ibIaXL.6PQ)单独发HEAD返回200，版本ID、长度、修改时间与ETag一致。两次响应是该时点的服务器元数据，不保证版本永久可用、内容或发布者身份；未读取数据包字节、未计算SHA-256，未验证内容与论文原版逐字一致。ETag不能在未知上传和加密方式时认作经验证的MD5或SHA，见[AWS说明](https://docs.aws.amazon.com/AmazonS3/latest/API/API_Object.html)。若将来必要且许可允许，需重新确认版本可访问并对实际下载字节计算SHA-256；此处未授权下载。

## 分项用途与权利边界

| 材料 | 原始声明 | 当前用途判断 |
| --- | --- | --- |
| `claims_*.jsonl` 中主张与证据标注 | [固定仓库许可](https://raw.githubusercontent.com/allenai/scifact/68b98a56d93e0f9da0d2aab4e6c3294699a0f72e/LICENSE.md)标CC BY 4.0 | 对作者许可覆盖的主张和标注可依据[CC BY 4.0条款](https://creativecommons.org/licenses/by/4.0/legalcode)评估保存、改写与分享，涉及署名、许可及修改说明等条件；尚未检查实际文件及再组合的其他权利，未构成最终材料放行。 |
| `corpus.jsonl` 中摘要 | 同一文件标ODC-By 1.0，称来自S2ORC | [ODC-By条款](https://opendatacommons.org/licenses/by/1-0/)明确其针对数据库权利，单项内容的独立权利另行处理。[S2ORC说明](https://github.com/allenai/s2orc)提示核实底层内容；因此不能仅凭数据库许可认定每篇摘要的保存、改写、再发布及外发均已获准。 |
| 代码 | 许可文件标Apache 2.0 | 代码许可不自动覆盖数据或上游摘要。 |

具体研究用途需分别核对临时读取、持久保存、改写成问答及五文档、向评审或外部服务传输、公开论文短引文或重放数据；本轮未确定各摘要权利、项目用途的全部条件及处理者约束，也未把缺少信息等同禁止。可行时应以具体内容版本和权利声明确定引用和再发布方式，而非用整体仓库许可证作替代。

## 语义与标注：不能直接构造原定参照

[作者数据schema](https://raw.githubusercontent.com/allenai/scifact/68b98a56d93e0f9da0d2aab4e6c3294699a0f72e/doc/data.md)将 evidence 按摘要ID组织，并以 SUPPORT/CONTRADICT 和句子编号给出依据；论文标注是针对**主张—单篇摘要**的 SUPPORTS/REFUTES/NOINFO 关系。论文还说对每个主张的引用摘要进行证据标注；不能把整个语料、任何未列摘要或新五文档组合视作已穷尽检查。原标签中摘要反驳主张不等于两份文档对同一问题给出互斥答案；摘要NOINFO不直接证明新问答输入中的五文档都不足。

原论文报告1,409条主张、5,183篇摘要；表中train/dev/test为809/300/300条，标签分别为 train 332支持/304无信息/173反驳，dev 124/112/64，test 100/100/100。该统计是论文报告，不是本轮包内容计数、可用样本数或底题隔离证明。原论文称232个主张—摘要对独立复标，标签Cohen κ=0.75、依据句子κ=0.71；这是原任务局部一致性，不认证新任务。仓库README说明test金标签未公开；train/dev有标注，不能将论文test分布当成本轮可获得的正式标签。

若未来有人希望将其另行改造，必须重新定义问题、在同实体/人群/时间/条件/结局下检查证据是否真正互斥，检查全部最终五文档是否泄漏答案或存在可消解差异，审查A/B语义是否保持并记录unknown与评审暴露。新增冲突对通常还需要另找或构造证据；这些步骤并非本轮完成，不证明科学事实的世界真值。实际旧训练、验证和已暴露材料的文本重叠、与380碰撞、模型预训练暴露，以及原论文统计对应版本，均未检查。

## 去留与状态

原SciFact可支持独立的科学主张—摘要验证研究，但作为本项目固定五文档问答的直接三状态确认集不成立。研究可继续以[冻结probe综合报告](../2026-11-11-frozen-probe-synthesis-v1/README.md)作为探索成果；若另选权属清晰的新原创受控材料，应先论证真实用途、来源权利、独立审阅、底题隔离、自然性、资源及相对近邻的实质增量，不能把素材选择当实验放行。本轮没有制作新数据或新的实验协议。

旧v1/E1-r1门禁false、正式独立批准0、标签null、原拟合预算0；380正文封存。无新样本下载、评分、模型加载、前向、GPU、拟合、阈值搜索或patching。

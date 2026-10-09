# 本地复现环境

专用 Conda 环境名称为 `kba-rag`，默认使用本地 Qwen2.5-3B-Instruct。
Qwen2.5 用于验证方法流程；它与论文使用的 Qwen3 模型不同，结果应记录模型名称。

环境目录：`/large_disk/wf/miniconda3/envs/kba-rag`。
Python 3.11.15，PyTorch 2.5.1+cu121，Transformers 4.56.2，
scikit-learn 1.5.2，NumPy 1.26.4，SciPy 1.13.1。

## 激活

先进入项目根目录，再激活环境。下面的写法同时适用于 `/bin/sh`、Bash 和 Zsh：

```sh
cd '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG'
. /large_disk/wf/miniconda3/etc/profile.d/conda.sh
conda activate kba-rag
. ./configs/local.env
```

`configs/local.env` 指定 GPU 0、离线模型路径和 CPU 线程数。
如 GPU 被其他任务占用，先检查 `nvidia-smi` 再调整该文件。

## 验证

无需激活 Conda，可以在任何目录直接执行：

```sh
sh '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG/scripts/check_environment.sh' --load-model
```

如果当前目录已经是 `scripts`，也可以执行 `sh ./check_environment.sh --load-model`。
这个入口会自动使用 `kba-rag` 的 Python 和本地模型配置。

已激活环境且当前目录是项目根目录时，运行：

```bash
python scripts/check_environment.py
python scripts/check_environment.py --load-model
# 也可以检查 7B 的配置和权重完整性，不加载 7B 权重：
python scripts/check_environment.py --model "$KBA_MODEL_7B"
python -m pip check
```

加载模型的检查仅使用短输入，验证隐藏状态、eager attention 和生成接口。
长文档实验的显存需要单独测量，不能根据短输入的结果推断。

## 重新安装

```bash
conda env create -f environment.yml
conda activate kba-rag
python -m pip check
```

PyTorch CUDA 12.1 wheel 自带 CUDA 运行库；不需要修改系统 CUDA 或驱动。
安装依赖时应保持联网，完成后再 source `configs/local.env` 启用离线模型加载。

`requirements.txt` 固定项目的直接依赖版本。scikit-learn 1.5.2 保留原代码
使用的 `multi_class` 和 `cv="prefit"` 接口；接口会产生弃用提示但仍可运行。
安装完成后的完整 pip 版本列表保存在 `requirements.lock.txt`。

若要复建包含全部传递依赖的相同 pip 版本，在新建 Python 环境中运行：

```bash
python -m pip install -r requirements.lock.txt --extra-index-url https://download.pytorch.org/whl/cu121
```

## 本机验证记录

2026-10-08 在 GPU 0（RTX 3090，24 GiB，驱动 535.183.01）验证通过：

- `pip check`：未发现依赖冲突。
- `StandardScaler`、多分类逻辑回归和 `cv="prefit"` sigmoid 校准接口正常。
- CUDA 12.1 运行库可用，BF16 矩阵运算正常。
- 完整加载本地 Qwen2.5-3B-Instruct，获取 36 层隐藏状态（每层 2048 维）。
- 36 层 MLP hook 和 eager attention 输出正常，短文本生成正常。
- 短输入验证的峰值已分配显存为 5.77 GiB；这个数值不代表长文档实验的显存需求。
- 7B 的模型配置、tokenizer 文件和全部四个权重分片已确认存在；本次未加载 7B 进行 GPU 前向。

模型加载检查使用独立的短示例，用于验证运行接口，不属于基准数据上的准确率实验。

## 项目代码状态

原仓库缺失的 `prompts.py` 已按发布 JSON 补齐。小规模隐藏状态路由器入口见
[小规模复现说明](small_reproduction.md)，入口包含数据准备、特征提取、选层和路由器评估。
原 SLURM 流程仍引用部分缺失文件，原 `code/2.py` 的 SAD 输出和错误处理仍需进一步修复；
当前的小规模入口独立处理缓存与失败样本，先使用该入口运行。

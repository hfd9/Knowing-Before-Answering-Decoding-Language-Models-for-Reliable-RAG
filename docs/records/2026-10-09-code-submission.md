# 2026-10-09：实验代码与交接文档归档

用户明确要求：一句话总结上次提交后的工作，并提交代码、推送到远端。
本地代码已归档；远端推送因缺少可用 GitHub 凭据而阻塞。最终本地提交哈希以 git log 为准。

## 工作摘要与提交范围

补齐四条件分类对照、同模板自由回答探针与行为盲审流程，并建立项目交接入口和实验记录索引。

上一提交：`35fd098`（300条测试集复线）。本次归档：

- 分类对照、公共实验工具、自由回答与盲审脚本，两个 sh 入口和新增测试。
- 固定实验计划、运行说明、准备快照、AGENTS.md、记录索引/模板/交接记录。
- README 入口与活动日志更新。

不包含被 Git 忽略的 runs/；本次归档没有改动正在运行的自由回答代码、配置或实验输出。

## 提交前检查

- 实验代码哈希与准备快照一致，对应此前全部 22 项测试通过的版本；未重复启动 GPU 检查。
- git diff --check 和新增交接文档空白检查通过。
- 沿用上一提交的单次提交身份 Codex <codex@openai.com>，不改变全局 Git 配置。
- 目标为 origin/main，使用普通推送；不强制改写远端历史。

## 后续

首次本地提交后执行普通 HTTPS 推送，实际返回 `could not read Username`（禁用了终端交互，避免挂起）。
本地 credential.helper 为 cache --timeout=3600，但此次未提供凭据；未发现 gh、相关 token 环境变量或标准 SSH 私钥。
认证阻塞记录追加到同一次尚未发布的提交中；没有改写远端历史。

需要用户在自己的交互终端重新认证并推送；针对此前代理 TLS 失败，可直接执行：

```sh
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy git -c http.proxy= -c http.version=HTTP/1.1 push origin main
```

推送成功后再核验远端 main 与本地 HEAD 一致。用户的自由回答实验继续运行，
后续先核验完整产物并完成行为审核；研究背景见 [AGENTS.md](../../AGENTS.md)。

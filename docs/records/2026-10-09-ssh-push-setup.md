# 2026-10-09：长期 SSH 推送配置

状态：本机配置与握手核验完成；等待用户将公钥添加到 GitHub，尚未推送成功。
用户要求：解决远端推送，并选择长期使用。

## 实际操作与证据

- HTTPS 凭据缓存 socket 不存在，无已提供登录凭据；直连出现 Empty reply 和 curl 超时。
- HTTPS 经本机代理读取远端 main 成功，仍为 35fd0988dff6d0c96b1cb1a42a56e31879be9e6f。
- 新建项目专用 Ed25519 密钥，私钥在 /large_disk/wf/.ssh/id_ed25519_kba_github，权限 0600，不纳入 Git。
- 公钥指纹：SHA256:slmTo6c3Cq5+3RZZUizLHZz6QmDDX5KHBcyVet4XvHU。
- GitHub 服务器 Ed25519 指纹与官方文档一致：SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU。
- SSH 443 直连及本机代理 CONNECT 均到达 GitHub，未授权公钥时返回 Permission denied (publickey)。
- 安装专用 kba_github_config / kba_github_known_hosts；以仓库本地 core.sshCommand 选择它，origin 改为标准 SSH URL。
- 原配置备份到 .git/kba-github-ssh-backup.json；没有覆盖全局 SSH 配置，没有关闭主机验证。
- 仅修改 Git 与专用 SSH 配置和文档，没有修改运行中的实验脚本、配置或输出。

## 下一步

用户在 GitHub Settings → SSH and GPG keys 添加专用 .pub；具体命令见 [git_push.md](../git_push.md)。
用户回复“已添加”后，助手验证仓库读写权限，普通推送 main，并核对远端哈希与本地 HEAD。
不能在公钥尚未授权时宣称推送或长期认证已经完成。

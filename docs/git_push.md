# 本机长期 SSH 推送

2026-10-09 按用户“长期使用”要求配置。仅影响当前仓库，模型实验不受影响。
用户已添加专用公钥；2026-10-09 通过本机 SSH 443 配置成功推送，且核验远端 main 与本地提交一致。

## 当前配置

| 项目 | 值 |
| --- | --- |
| origin | `git@github.com:hfd9/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG.git` |
| 仓库 core.sshCommand | `/usr/bin/ssh -F /large_disk/wf/.ssh/kba_github_config` |
| 实际连接 | `git@ssh.github.com:443` |
| 专用公钥 | `/large_disk/wf/.ssh/id_ed25519_kba_github.pub` |
| 专用私钥 | `/large_disk/wf/.ssh/id_ed25519_kba_github`，权限 0600，保留在账号目录，不进入 Git |
| 专用连接配置 | `/large_disk/wf/.ssh/kba_github_config` |
| 专用主机信任文件 | `/large_disk/wf/.ssh/kba_github_known_hosts` |
| 配置前备份 | `.git/kba-github-ssh-backup.json`，不随 Git 发布 |

专用配置使用 IdentitiesOnly、严格主机校验、官方 Ed25519 主机公钥及 15 秒连接超时。
密钥未设口令，以支持该账号在此机器上的自动推送；私钥不需要发给助手或上传到 GitHub。
本机配置与私钥不会随克隆迁移到其他机器。HTTP 凭据缓存不再承担此 origin 的认证。

## 首次授权：用户完成一次

本机已完成以下首次授权步骤，后续直接使用 git push origin main 即可；更换机器时使用新机器的公钥重新授权。

1. 登录有该仓库写权限的 GitHub 账号，打开 <https://github.com/settings/ssh/new>。
2. Title 填 `ahuhzh-kba-rag`；Key type 选择 Authentication Key。
3. 执行以下命令，把显示的完整一行公钥复制到 Key，点击 Add SSH key。

```sh
cat /large_disk/wf/.ssh/id_ed25519_kba_github.pub
```

然后在项目根目录测试并推送：

```sh
git ls-remote origin refs/heads/main
git push origin main
```

也可告诉助手“公钥已添加”，由助手完成核验及已授权的推送。
若添加后仍提示 Permission denied (publickey)，先核对上传的是此 .pub 文件及正确账号。

## 诊断与解释

- 此前 HTTPS 认证缓存没有可用凭据，cache --timeout=3600 本身不会完成 GitHub 登录。
- 本次 HTTPS 直连出现 Empty reply / 15 秒超时；通过本机代理读远端 main 成功。
- SSH 443 直连及 HTTP CONNECT 代理连接均完成握手，且核验了 GitHub 官方主机公钥。
- 公钥上传前返回 Permission denied (publickey) 是尚未授权，不是 TLS 握手错误。
- 正常操作继续使用 git push origin main；无需每次复制取消 HTTP 代理的长命令。

仅测试 SSH 账号认证：

```sh
ssh -F /large_disk/wf/.ssh/kba_github_config -T github.com
```

GitHub 的成功认证消息会说明不提供 shell；该测试可能以状态码 1 结束，应按认证消息判断。
Git 读写仓库则按正常退出码与远端哈希判断。

## 恢复旧 HTTPS origin

```sh
git remote set-url origin https://github.com/hfd9/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG.git
git config --local --unset core.sshCommand
```

保留专用密钥文件即可；恢复 HTTPS 后仍需有效 PAT 或其他 HTTPS 登录方式。

官方依据：[SSH 443 端口](https://docs.github.com/en/authentication/troubleshooting-ssh/using-ssh-over-the-https-port)、
[主机公钥](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints)、
[添加账号公钥](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account)。

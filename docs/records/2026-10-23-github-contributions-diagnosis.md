# 2026-10-23：个人GitHub贡献图未显示的只读诊断

用户反馈最近提交仍未显示在GitHub个人主页contributions。本轮只读检查本地作者、时间、远端仓库及GitHub提交账户关联，对照官方贡献规则；不修改邮箱、不改写历史、不新建仓库、不退出fork网络或修改远端设置。

## 已确认原因

GitHub原始REST API返回当前仓库`hfd9/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG`为`fork: true`，上游为`SyedHuq28/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG`。仓库公开，默认分支main，最近推送已在远端，不是未上传或非默认分支。

GitHub API将最近`9464e16`、`615d9c2`、`5152ca9`以及`798345e`、`ac5cc87`的author和committer均关联为`hfd9`。本地配置邮箱与这些提交一致；无需为最近这些提交再次改邮箱。更早的Codex署名记录仍关联旧账户，是未改写的历史问题，不能靠现在修改配置追溯更改。

[GitHub贡献规则](https://docs.github.com/en/account-and-profile/reference/profile-contributions-reference)要求提交在独立仓库而非fork，且邮箱关联账户、位于默认或gh-pages分支。[缺失贡献排查](https://docs.github.com/en/account-and-profile/how-tos/contribution-settings/troubleshooting-missing-contributions)明确fork内提交不计入个人贡献；仅等待刷新不会消除fork条件。此前只核对作者身份和推送，漏查fork统计条件，核验范围不完整，本次补足。

## 可选择的后续处理

保守方案是保留现有fork，另建独立研究仓库并推送完整现有main历史，原始上游及作者信息保持，不制造空提交。此方案尚未执行，需用户确定新仓库及公开性。

如希望继续使用当前仓库，可按[GitHub官方退出fork说明](https://docs.github.com/en/pull-requests/how-tos/work-with-forks/detaching-a-fork)，在Settings→General→Danger Zone使用Leave fork network。官方说明Git提交元数据保留，符合其他条件的提交可能计入贡献；退出永久，相关issues/PR/wiki/stars/watchers/comments等非Git元数据不保留。本仓库当前公开、约26MB、子fork数0，符合文档列出的基本条件，实际选项以GitHub页面为准。该永久变更未获本轮明确授权，不执行。

另一方式是把真正适合上游的修改通过PR合入上游默认分支；不为贡献图向上游自动提交实验归档或发送消息。统计刷新最多可能需要24小时，但必须先满足计入条件；贡献按原作者日期归属，不一定全部落到推送当天。

证据与账户关联的脱敏摘要保存在[JSON记录](2026-10-23-github-contributions-diagnosis.json)，不重复保存提交邮箱或任何凭据。连接器先确认公开性/main，但未返回fork和author关联字段，之后补用公开REST API确认。没有调用任何GitHub写入接口。本轮新增诊断记录并维护交接，未提交或推送新诊断记录。

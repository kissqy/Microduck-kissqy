# VS Code 上传 GitHub：超简版

## 第一次上传

1. 注册或登录 [GitHub](https://github.com/)，安装 [Git for Windows](https://git-scm.com/install/windows)，再重开 VS Code。
2. 解压整套交付包；VS Code **文件 → 打开文件夹**，选择其中的 **microduck-hd1910** 文件夹。
3. 按 **Ctrl+Shift+G → 初始化仓库**。若已初始化则跳过。
4. 首次使用 Git，在 VS Code 终端设置提交署名；邮箱可用 GitHub **Settings → Emails** 中的 noreply 邮箱：

```powershell
git config --global user.name "你的GitHub用户名"
git config --global user.email "你的GitHub提交邮箱"
```

5. 在“源代码管理”点 **暂存全部 → 输入「首次公开发布」→ 提交**。
6. 按 **Ctrl+Shift+P**，输入 **Publish to GitHub**，按提示在浏览器登录。
7. 仓库名填 `microduck-hd1910`，选 **Publish to GitHub public repository**。完成后打开 GitHub 核对。

保留现有 LICENSE，不另选 MIT 或 Apache 覆盖仓库的分项授权。无需先配置 SSH 密钥；VS Code 可以通过浏览器登录 GitHub。

## 上传可直接使用的包

在 GitHub 仓库点 **Releases → Draft a new release**：

- 标签：`r17-v1.0.146-training-r1.5.17-public1`；目标选择刚上传的分支（通常为 main）。
- 标题：`R17 v1.0.146 + Training R1.5.17`。
- 说明：复制交付包 `release-assets/RELEASE-NOTES.txt`。
- 附件：上传 `release-assets/` 下的 3 个 Public ZIP 和 `SHA256SUMS.txt`。
- 本版实机完整验收尚未完成，首次发布勾选 **This is a pre-release**，再点 **Publish release**。

源码目录上传 Git；供人下载运行的 ZIP 上传 Releases。每个普通 Git 文件需不超过 100 MiB；每个 Release 附件需小于 2 GiB。本次准备的文件均低于限额。

## 以后更新

VS Code 改好文件 → **暂存 → 提交 → 推送 / Push**。提交只保存在本地，推送后 GitHub 才更新。
有新固件或运行包时，再新建对应版本的 Release。

## 官方参考

- [VS Code Git 入门与发布](https://code.visualstudio.com/docs/sourcecontrol/quickstart)
- [VS Code 仓库与远端](https://code.visualstudio.com/docs/sourcecontrol/repos-remotes)
- [GitHub 创建 Release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [GitHub 文件大小限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [Release 附件限制](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
- [提交邮箱与 noreply](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address)

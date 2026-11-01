# 提交状态：本地已就绪，阻塞在「仓库不存在 / 没有凭据」

**当前不可提交。** 记录、补丁、PR 正文都已生成并通过本地校验；剩下的只有三件必须由账号持有人做的事。

## 三个硬性前提的核验结果

| # | 前提 | 状态 | 证据 |
| --- | --- | --- | --- |
| 1 | 公开 GitHub 仓库存在 | ❌ 不满足 | 本目录已 `git init`（commit `4dc2438`、tag `v1.0.0`），但记录里的 `https://github.com/OWNER/heightforge-workshop` 经 API 查询返回 `HTTP 404` |
| 2 | Release 非 draft 且非 prerelease | ❌ 不满足 | 仓库不存在 → 无 Release 可查 |
| 3 | 资产地址可下载且字节与 `dist/` 一致 | ❌ 不满足 | 资产地址 `…/releases/download/v1.0.0/studio.heightforge.heightmap-1.2.0.lumina-workshop` 返回 404 |

本地实测（这三项是**已确认**的，可直接作为 CI 的比对基准）：

```text
文件     : studio.heightforge.heightmap-1.2.0.lumina-workshop
字节数   : 194969
sha256   : a516432f66661a8f7b0d70277045450a548c09fe7e2241eb8f2fee0b77bc48a9
manifest : 4b305567d0593b31586436cd103e38f78c6918cec80ec887c1db849127e86f88
```

## 本地已经做完的事

- 仓库已初始化：`main` 分支、单个提交 `4dc2438`、注释标签 `v1.0.0`；`dist/`、`.tmp/` 已忽略。
- `.gitattributes` 固定 `* -text`：本机 `core.autocrlf=true`，不锁死会让检出后的 `ui/index.html` 变成 CRLF，
  打包字节随之变化、sha256 与 Release 对不上。加锁后重新打包字节不变（当时基线 `17e92c08…`，属 1.0.0 时代；当前 1.2.0 见上表）。
- `tools/make_registry_patch.py` 已能从记录生成可 `git apply` 的补丁；在临时仓库里
  `git apply --check` 通过，应用后字节与 `registry/modules/…json` 完全一致。
- `registry/PR_BODY.md` 已按 Registry 的 `.github/pull_request_template.md` 六项写好（中英双段）。

## 解除阻塞需要你做的三件事

0. 若命令行访问 GitHub 报 `CRYPT_E_REVOCATION_OFFLINE`，给 git 加 `-c http.schannelCheckRevoke=false`。

1. **建公开仓库并推送**（在 GitHub 上新建空仓库，不要勾 README/License）：

   ```bash
   cd D:/DSH/heightforge-workshop
   git remote add origin https://github.com/<owner>/heightforge-workshop.git
   git -c http.schannelCheckRevoke=false push -u origin main
   git -c http.schannelCheckRevoke=false push origin v1.0.0
   ```

2. **发一个不可变 Release**：tag 选 `v1.0.0`，标题任意，**只挂一个资产**
   `dist/studio.heightforge.heightmap-1.2.0.lumina-workshop`，且不要勾 prerelease。

3. **把地址告诉机器人**（或本地自己跑）：

   ```bash
   python tools/make_registry_record.py \
     --repository https://github.com/<owner>/heightforge-workshop \
     --publisher "HeightForge Studio"
   python tools/make_registry_patch.py          # 生成 registry/registry-pr.patch
   ```

   然后用 `python tools/build_package.py --check dist/…lumina-workshop` 核对 sha256 与 Release 上一致。

## 之后提 Registry PR 的三条命令

```bash
git clone https://github.com/<你的fork>/Lumina-Workshop-Registry.git
cd Lumina-Workshop-Registry && git switch -c add-heightforge
git apply D:/DSH/heightforge-workshop/registry/registry-pr.patch
git add modules/studio.heightforge.heightmap.json && git commit -m "feat(modules): add studio.heightforge.heightmap 1.0.0"
git push -u origin add-heightforge        # 然后在网页上开 PR，正文用 registry/PR_BODY.md
```

## 记录文件

- 正式记录（待替换占位地址）：`registry/modules/studio.heightforge.heightmap.json`
- 早期草稿：`registry/draft/studio.heightforge.heightmap.json`（可删）

两份内容一致，都是 `official: false`、`publisher: HeightForge Studio`、`state: active`、
`revocation: null`，并且**不含**派生字段 `downloadUrl`。

## 为什么不能先提交

Registry 的 CI 会真的去下载那个资产、比对字节与两个 sha256。仓库不存在时，
PR 会直接卡在“资产不可达/身份不匹配”，属于无效提交；而伪造仓库地址或摘要属于
明确禁止的行为，所以这里停在“生成好、等地址”。

# 提交状态：本地已就绪（1.2.0 已按 SDK 规范锁定依赖），阻塞在「仓库不存在 / 没有凭据」

**当前不可提交。** 记录、补丁、PR 正文都已生成，并通过了 Registry 自带的校验脚本；
剩下的只有三件必须由账号持有人做的事。

## 三个硬性前提的核验结果（2026-11-02 复查）

| # | 前提 | 状态 | 证据 |
| --- | --- | --- | --- |
| 1 | 公开 GitHub 仓库存在 | ❌ 不满足 | 本目录 `git remote -v` 为空；记录里的占位地址经 API 查询 `HTTP 404`；GitHub 搜索 `heightforge-workshop` 命中 0 |
| 2 | Release 非 draft 且非 prerelease | ❌ 不满足 | 仓库不存在 → 无 Release 可查 |
| 3 | 资产可下载且字节一致 | ❌ 不满足 | 资产地址返回 404 |
| 4 | 推送凭据 | ❌ 不满足 | `git credential fill` 对 github.com 无凭据；无 `gh`、无 SSH key（不索取 Token） |

本地实测（可直接作为 CI 比对基准）：

```text
文件     : studio.heightforge.heightmap-1.2.0.lumina-workshop
字节数   : 194969
sha256   : a516432f66661a8f7b0d70277045450a548c09fe7e2241eb8f2fee0b77bc48a9
manifest : eaa48d3be7661d4cc128f2136e544685e91dcd33d844286444d72ebc9a6d3545
模块版本 : 1.2.0（tag v1.2.0，commit c007f21）
```

## SDK 依赖已按官方规范执行（1.2.0 起）

- `package.json` 的依赖是**含确切版本的 Release URL**，不是 `latest`、也不来自 npm registry：

  ```json
  "@lumina/workshop-sdk": "https://github.com/lumina-layer-studio/Lumina-Workshop-SDK/releases/download/v1.0.2/lumina-workshop-sdk-1.0.2.tgz"
  ```

- `pnpm install` 生成并提交了 `pnpm-lock.yaml`（含同一 URL 与 `integrity: sha512-UrkhqQvZubot…`）。
- 下载后与官方 `lumina-workshop-sdk-1.0.2.tgz.sha256` 核对：`f23f8d0b…93ad` **一致**。
- 运行时仍是单文件：`tools/bundle_sdk.mjs` 把 SDK 的 ESM 产物内联为 `window.LuminaWorkshop`，
  包内 `ui/index.html` 无任何外链；握手/RPC 全部由 `connectWorkshop()` 完成。

## 本地跑过 Registry 自己的校验

```bash
git clone --depth 1 https://github.com/lumina-layer-studio/Lumina-Workshop-Registry .tmp/registry
python -m venv .tmp/venv && .tmp/venv/Scripts/pip install -r .tmp/registry/requirements.in
cd .tmp/registry && PYTHONPATH=src ../../.tmp/venv/Scripts/python.exe scripts/validate_sources.py --modules .tmpcheck
```

把官方 `modules/lumina.bead-pattern.json` 与本项目的记录放在同一目录一起跑：**退出码 0，无报错**
（即闭集 schema、文件名=moduleId、版本字段、权限白名单、sha256 形状等全部通过）。

## 解除阻塞：三步

0. 若命令行访问 GitHub 报 `CRYPT_E_REVOCATION_OFFLINE`，给 git 加 `-c http.schannelCheckRevoke=false`。

1. **建公开仓库并推送**（GitHub 上新建空仓库，不勾 README/License）：

   ```bash
   cd D:/DSH/heightforge-workshop
   git remote add origin https://github.com/<owner>/heightforge-workshop.git
   git -c http.schannelCheckRevoke=false push -u origin main
   git -c http.schannelCheckRevoke=false push origin v1.2.0
   ```

2. **发一个不可变 Release**：tag 选 `v1.2.0`，只挂一个资产
   `dist/studio.heightforge.heightmap-1.2.0.lumina-workshop`，不要勾 prerelease。

3. **一条命令把记录/补丁/PR 描述刷成真实地址**：

   ```bash
   python tools/finalize_registry.py --repo https://github.com/<owner>/heightforge-workshop
   ```

   它会拒绝占位地址、重算字节与摘要、重新生成 `registry/registry-pr.patch`，并打印后续 push/PR 命令。

## 之后提 Registry PR

```bash
git clone https://github.com/<你的fork>/Lumina-Workshop-Registry.git
cd Lumina-Workshop-Registry && git switch -c add-studio-heightforge
git apply D:/DSH/heightforge-workshop/registry/registry-pr.patch
git add modules/studio.heightforge.heightmap.json
git commit -m "feat(modules): add studio.heightforge.heightmap 1.2.0"
git push -u origin add-studio-heightforge   # 网页开 PR，正文用 registry/PR_BODY.md
```

## 记录文件

- 正式记录（占位地址待替换）：`registry/modules/studio.heightforge.heightmap.json`
- 早期草稿：`registry/draft/studio.heightforge.heightmap.json`（可删）

`official: false`、`publisher: HeightForge Studio`、`state: active`、`revocation: null`，
**不含**派生字段 `downloadUrl`。

## 为什么不能先提交

Registry CI 会真的下载资产、比对字节与两个 sha256，并且每个 module ID 永久绑定一个已审核仓库。
仓库不存在时 PR 会卡在「资产不可达」，属于无效提交；伪造地址或摘要则是明确禁止的行为，
所以停在「生成好、等地址」。

## 当前状态（2026-11-02）

PR 已提交：<https://github.com/lumina-layer-studio/Lumina-Workshop-Registry/pull/5>

| 环节 | 结果 |
| --- | --- |
| 模块仓库 | `https://github.com/xueseyinlang-cmyk/LUMINA-`（public，main = `12bb190`） |
| Release | `v1.2.0`（非 draft、非 prerelease），资产 `studio.heightforge.heightmap-1.2.0.lumina-workshop` |
| 资产复核 | 194,969 字节，sha256 `a516432f…`，与本地包一致 |
| Fork 分支 | `xueseyinlang-cmyk:Lumina-Workshop-Registry` → `add-studio-heightforge` |
| PR 内容 | 1 提交、1 文件、+36 行（仅 `modules/studio.heightforge.heightmap.json`） |
| CI | 工作流 `Pull Request Validation` 结论 `action_required`（首次贡献者需维护者批准运行） |

阻塞项已全部解除；后续只需等待维护者批准工作流并 review。

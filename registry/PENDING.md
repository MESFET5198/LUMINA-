# 提交状态：1.2.0 已通过 PR #5 提交，1.3.1 为四个验收问题的修复版本

## 现在的状态

| 项目 | 值 |
| --- | --- |
| 模块 | `studio.heightforge.heightmap`（社区发布者 `HeightForge Studio`） |
| 已提交版本 | `1.2.0`（PR [#5](https://github.com/lumina-layer-studio/Lumina-Workshop-Registry/pull/5)，open / mergeable） |
| 本次版本 | `1.3.1` |
| 包文件 | `studio.heightforge.heightmap-1.3.1.lumina-workshop` |
| 字节数 | 197,712 |
| sha256 | `984361f65526f1bd38928e149be0bc717418f6ecd5837111c92623376dcb6232` |
| manifest sha256 | `da26be3c722a0d6f907dd45596b1533b12ab50019b2b3ef974f2ca4527bc61e8` |
| 模块仓库 | `https://github.com/xueseyinlang-cmyk/LUMINA-` |
| Registry 记录 | `registry/modules/studio.heightforge.heightmap.json` |
| 可应用补丁 | `registry/registry-pr.patch` |
| PR 正文 | `registry/PR_BODY.md` |

1.3.1 修的是 PR #5 评审提出的四个功能问题（首次出图即可交接、已有图片时二次确认替换、
宿主内收起无效导出并说明、台阶化后 Gamma/对比真正不参与）；管线、权限与兼容范围均未扩张。

## 发布 1.3.1 的三步（本地已全部跑过一次，重跑即可）

```bash
cd D:/DSH/heightforge-workshop

# 1) 打包 + 重算记录与补丁（摘要来自现场计算，不要手改）
python tools/build_package.py
python tools/make_registry_record.py \
  --repository https://github.com/xueseyinlang-cmyk/LUMINA- \
  --publisher "HeightForge Studio" \
  --package dist/studio.heightforge.heightmap-1.3.1.lumina-workshop
python tools/make_registry_patch.py

# 2) 推送模块仓库并打 tag（github.com 需走本地代理，且关掉 schannel 吊销检查）
git -c http.schannelCheckRevoke=false push origin main
git tag -f -a v1.3.1 -m "studio.heightforge.heightmap 1.3.1"
git -c http.schannelCheckRevoke=false push -f origin v1.3.1

# 3) 发不可变 Release（只挂一个资产，非 draft、非 prerelease）后更新 PR 正文
```

Release 资产地址（记录里已引用）：
`https://github.com/xueseyinlang-cmyk/LUMINA-/releases/download/v1.3.1/studio.heightforge.heightmap-1.3.1.lumina-workshop`

## 本地校验（全部通过）

```text
python tools/run_js_tests.py          -> RESULT OK 83
python tests/test_registry_record.py  -> RESULT OK（16 例）
PYTHONPATH=src python scripts/validate_sources.py --modules <registry>/modules -> exit 0
```

## 仍然缺的东西

- 维护者对 PR #5 的审批：首次贡献者的 `Pull Request Validation` 工作流处于
  `action_required`，需要维护者点一次批准才会开跑。
- 若审核要求「版本必须与模块仓库 tag 一一对应且不可重打」，1.3.1 的 tag 必须是新 tag
  （不要复用 `v1.2.0`）；本次已按新 tag `v1.3.1` 处理。

## 1.3.1 发布进展（2026-11-02 21:0x 实测）

| 环节 | 状态 |
| --- | --- |
| 模块仓库 main | 已推送 `89f7601`（tag `v1.3.1`） |
| Release | 已创建 id `431476858`，非 draft、非 prerelease |
| 资产 | `studio.heightforge.heightmap-1.3.1.lumina-workshop`，API 记录 197,712 字节 / sha256 `984361f6…` |
| 下载地址复核 | `https://github.com/xueseyinlang-cmyk/LUMINA-/releases/download/v1.3.1/studio.heightforge.heightmap-1.3.1.lumina-workshop` → 197,712 字节、sha256 一致（首次替换后 CDN 有约 8 分钟旧缓存，已过期） |
| Registry fork 分支 | 本地已提交 `6d81605`（记录改为 1.3.1），**尚未推送**（沙箱禁止 remote-https 建管道） |
| PR 正文 | `registry/PR_BODY.md` 已按 1.3.1 重写，**尚未 PATCH 到 PR #5** |

推送 fork 分支只需一条命令：

```bash
cd D:/DSH/heightforge-workshop/.tmp/fork
git -c http.schannelCheckRevoke=false -c http.proxy=http://127.0.0.1:7890     push origin HEAD:add-studio-heightforge
```

# 德语课堂 v2 · GitHub Pages 版

手机上独立运行、**不需要电脑、不需要 API Key** 的德语跟读工具。同一套 Conrad 德语男声，和电脑上完全一致。

---

## 这套东西怎么运作

| 文件 | 作用 |
| --- | --- |
| `index.html` | 工具本体（单文件，105 句语料已内联，295 KB） |
| `audio.json` | 文本 → 音频文件 的清单，页面据此播放（**由工作流生成**，首次上传时不在包里） |
| `audio/*.mp3` | 预合成好的德语音频（**由工作流生成**，首次上传时不在包里） |
| `scripts/corpus.json` | 待合成清单：整句 105 句 × 5 档语速 + 词块 415 条 × 1 档 = **940 个音频** |
| `scripts/build_audio.py` | 用免 Key 的 `edge-tts` 预合成这些音频，输出 `audio/` 与 `audio.json` |
| `.github/workflows/build-audio.yml` | 手动触发 + 每周自动跑一次，合成完提交回仓库，Pages 自动重部署 |

**为什么不需要 Key**：电脑版用的是 `edge-tts`（微软 Edge「大声朗读」背后的同一套神经语音），它本身免 Key。
现在把这一步搬到 GitHub 的服务器上跑，合成结果提交进仓库，网页直接播放这些 MP3。
所以手机上听到的是**和电脑上字节级一致的 Conrad 德语男声**，且不用注册任何账号。

**语速怎么实现的**：五档语速（逐词 0.50× / 很慢 0.65× / 慢速 0.80× / 常速 0.95× / 播报 1.10×）
不是播放时拉伸变调，而是**每档各预合成一份**（edge-tts 服务端原生变速），页面按当前语速直接取对应那份。
词块为了省体积只合成一档（常速），播放时用 `playbackRate` 补偿到当前语速。

---

## 一次性部署（约 10 分钟）

### 1. 建仓库

github.com → **`New repository`** → 名字随意（建议 `Deutsch-v2`）→ **Public** → Create。

> 免费账号的 Pages 只支持公开仓库。本包不含任何密钥、账号或个人路径。

### 2. 上传文件

仓库页 → `Add file` → `Upload files` → 把本文件夹里**全部内容**拖进去：

```
.nojekyll        index.html        README.md
scripts/         (corpus.json, build_audio.py)
.github/workflows/build-audio.yml
```

→ Commit。

> **`.github` 是点开头的文件夹，网页拖拽常常进不去。** 用 `Add file` → `Create new file`，
> 文件名栏直接输入 `.github/workflows/build-audio.yml`（斜杠会自动建目录），粘贴内容后 Commit。

### 3. 开 Pages

仓库 `Settings` → `Pages` → Source = **`Deploy from a branch`** → Branch `main`、`/ (root)` → Save。

> 不要选 `GitHub Actions` 作为 Source。

### 4. 跑一次工作流（关键）

仓库顶部 **`Actions`** 标签 → 左侧选 **`build-audio`** → `Run workflow`。

第一次会合成 **940 个音频**，大约 5–10 分钟。跑完会自动提交 `audio/`（约 25–30 MB）和 `audio.json`，
Pages 随即重新部署。

### 5. 访问

`https://<用户名>.github.io/<仓库名>/`

手机上 Safari 打开 → **分享 → 添加到主屏幕**，以后从桌面图标进，全屏像 App。

---

## 手机上不需要配置任何东西

页面加载时自动读取同源的 `audio.json`：

- 找到了 → 状态灯显示 **`📦 离线语音包 · 940 条离线音频`**，直接用 Conrad 音色播放。
- 还没生成（Action 没跑完） → 状态灯显示 `⚠️ 没有可用的德语语音`，这是**预期的**，跑完 Action 就好。

> 如果你之前在手机上手动点过别的引擎，它不会自动切回来。
> 到「设置 → 语音引擎」点 **📦 仅离线语音包** 即可；或清除该网站数据后重开。

---

## 想改内容 / 换音色

本包里的 `index.html` 和 `scripts/corpus.json` 都是**构建产物**，源头在本地项目里：

| 想改什么 | 怎么做 |
| --- | --- |
| 改语料 | 改 `deutsch-klasse/data/corpus.json` → `python tools\check_corpus.py` → `python tools\export_pack_corpus.py` → `python tools\build.py` → 把新的 `index.html` 和 `scripts/corpus.json` 传上来 |
| 换音色 | 改 `scripts/corpus.json` 里的 `voice` 字段（或跑 `build_audio.py --voice de-DE-KatjaNeural`）→ 重跑 Action |
| 改音频设置 | 改 `scripts/build_audio.py` 的 `--workers`（并发）、`MIN_BYTES`；语速档在 `scripts/corpus.json` 的 `sentenceRates` / `chunkRates` |

改完语料后重跑 Action 即可：**只补新文件**，已有的音频会跳过（文件名是 `sha256(音色|语速|文本)`）。

---

## 常见问题

**Q：`.github` 文件夹拖不进去怎么办？**
用 `Add file` → `Create new file`，文件名栏直接输入 `.github/workflows/build-audio.yml`，粘贴内容后 Commit。

**Q：Actions 里找不到 `build-audio`？**
它在仓库顶部的 **`Actions`** 标签里，不在 `Settings` 里。
直接打开 `https://github.com/<用户名>/<仓库名>/actions`。

**Q：工作流跑完但页面还是没声音？**
看仓库里有没有 `audio.json` 和 `audio/` 文件夹。没有 → 工作流失败了，点进那次运行看日志。
有 → 硬刷新页面（手机上关掉标签页重开）。

**Q：工作流报 `403` 或合成全失败？**
微软临时拒绝了机房 IP。过一两天在 Actions 里点 `Re-run all jobs`；仍然不行就换 Azure 免费 Key。

**Q：手机上声音很小 / 很怪？**
离线包是预合成的固定音色。检查状态灯是不是 `📦 离线语音包`（不是 `🖥️ 系统语音`）。
iOS 没有德语语音包时，系统语音会退化成英语音色或没声音——那种情况一律用离线包。

**Q：每次播放都要联网吗？**
要。从 GitHub 下载当前这句的一个 mp3（约 20–60 KB）。第一次播某句时稍慢，之后浏览器会缓存。
不联网只能看语料，不能听。

**Q：能不能放到已有仓库的子目录？**
可以。把整个包放进子目录（如 `v2/`），工作流里的路径要相应改成 `v2/scripts/...`、
提交路径改成 `v2/audio`；网址变成 `https://<用户名>.github.io/<仓库名>/v2/`。
页面用的是相对路径，放子目录不用改代码。

---

## 已知限制

- **离线包是快照**：改了语料必须重跑 Action 才有新句子和音频。
- **每次播放一次网络请求**：完全离线使用需要改用电脑版（`deutsch-klasse/` 目录 + `tts-server.py`）。
- **词块只有一档音频**，切到非常速语速时用 `playbackRate` 补偿，音质比整句略逊。
- Pages 是 HTTPS，属于安全上下文；不过 v2 本身没有录音功能，用不到麦克风。

---

## 与旧版的关系

仓库 `xavercai/Deutsch` 上的旧版（复习计划 / 录音评分 / 新闻抓取 / 分享码）**继续保留、互不影响**。
v2 是重新写的精简版：只做跟读，语料 105 条离线内置，数据层收敛成单一事实源 `corpus.json`，
语音链路在本地与静态托管两处都验证过。

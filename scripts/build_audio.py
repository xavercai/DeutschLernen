#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线语音包构建（GitHub Actions 里跑）
=====================================
用免 Key 的 edge-tts 把语料预合成成 MP3，输出到 audio/ 并写 audio.json 清单。
页面（静态托管 / GitHub Pages）同源读取 audio.json 播放 ——
手机不依赖电脑、不需要任何 API Key、不需要本地 Python 服务。

- 整句：5 档语速各一份（-50 / -35 / -20 / -5 / +10 %），edge-tts 服务端原生变速，音质最好
- 词块：1 档（-5 %），页面用 playbackRate 补偿到当前语速
- 增量：已存在的 mp3 直接跳过，重跑只补新的
- 文件名：sha256(voice|rate|text) 前 32 位 + .mp3
- 清单 audio.json：{ "德语文本": { "-5": "audio/xxx.mp3", ... }, ... }

用法：
    python scripts\\build_audio.py                  # 全量（缺什么补什么）
    python scripts\\build_audio.py --workers 8      # 指定并发
    python scripts\\build_audio.py --limit 20       # 只做前 20 个（本地试跑）
    python scripts\\build_audio.py --voice de-DE-KatjaNeural
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import edge_tts
except ImportError:
    print("缺少依赖 edge-tts，请先执行：python -m pip install edge-tts", file=sys.stderr)
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "audio"
MANIFEST = ROOT / "audio.json"
CORPUS = ROOT / "scripts" / "corpus.json"

MIN_BYTES = 600


def digest(voice: str, rate: int, text: str) -> str:
    return hashlib.sha256(("%s|%+d|%s" % (voice, rate, text)).encode("utf-8")).hexdigest()[:32]


async def _synth(text: str, voice: str, rate: int) -> bytes:
    # edge-tts 7.x：Communicate(text, voice, rate="+N%")；这一版没有 ssml= 参数
    comm = edge_tts.Communicate(text, voice, rate="%+d%%" % rate)
    buf = bytearray()
    async for chunk in comm.stream():
        if chunk.get("type") == "audio":
            buf.extend(chunk["data"])
    return bytes(buf)


def synth_one(job):
    """返回 (text, rate, filename, status)；status ∈ new / skip / FAIL:原因"""
    text, rate, voice = job
    name = digest(voice, rate, text) + ".mp3"
    dest = AUDIO_DIR / name
    if dest.exists() and dest.stat().st_size >= MIN_BYTES:
        return (text, rate, name, "skip")
    last = "unknown"
    for attempt in range(3):
        try:
            data = asyncio.run(_synth(text, voice, rate))
            if len(data) < MIN_BYTES:
                raise RuntimeError("音频过短（%d 字节）" % len(data))
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(data)
            os.replace(tmp, dest)   # 原子改名，避免半截文件被当成有效音频
            return (text, rate, name, "new")
        except Exception as e:
            last = str(e)
            time.sleep(1.5 * (attempt + 1))
    return (text, rate, name, "FAIL:" + last)


def load_jobs(voice_default: str):
    if not CORPUS.exists():
        print("[x] 找不到 %s" % CORPUS, file=sys.stderr)
        raise SystemExit(1)
    doc = json.loads(CORPUS.read_text(encoding="utf-8"))
    voice = doc.get("voice") or voice_default
    jobs = []
    seen = set()
    for group in ("sentences", "chunks"):
        for item in doc.get(group) or []:
            text = (item.get("text") or "").strip()
            if not text:
                continue
            for rate in item.get("rates") or []:
                key = (text, int(rate))
                if key in seen:
                    continue
                seen.add(key)
                jobs.append((text, int(rate), voice))
    return jobs, voice


def main() -> int:
    ap = argparse.ArgumentParser(description="预合成离线语音包")
    ap.add_argument("--voice", default="de-DE-ConradNeural", help="德语音色名")
    ap.add_argument("--workers", type=int, default=8, help="并发数")
    ap.add_argument("--limit", type=int, default=0, help="只做前 N 个（0=全部）")
    args = ap.parse_args()

    jobs, voice = load_jobs(args.voice)
    if args.limit > 0:
        jobs = jobs[: args.limit]
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    print("[..] 待处理 %d 个音频，音色 %s，并发 %d" % (len(jobs), voice, args.workers))

    t0 = time.time()
    results = []
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        for r in ex.map(synth_one, jobs):
            results.append(r)
            done += 1
            if r[3].startswith("FAIL"):
                print("[x] %+d%% %r -> %s" % (r[1], r[0][:40], r[3]))
            if done % 50 == 0 or done == len(jobs):
                print("    %d/%d  (%.0fs)" % (done, len(jobs), time.time() - t0))

    # 清单：只写磁盘上确实存在的文件（失败项沿用旧文件，不丢音频）
    manifest = {}
    for (text, rate, _voice), (_t, _r, name, _st) in zip(jobs, results):
        p = AUDIO_DIR / name
        if not (p.exists() and p.stat().st_size >= MIN_BYTES):
            continue
        manifest.setdefault(text, {})[str(rate)] = "audio/" + name
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=0), encoding="utf-8")

    n_new = sum(1 for r in results if r[3] == "new")
    n_skip = sum(1 for r in results if r[3] == "skip")
    n_fail = sum(1 for r in results if r[3].startswith("FAIL"))
    total_bytes = sum(f.stat().st_size for f in AUDIO_DIR.glob("*.mp3"))
    print("[ok] 新合成 %d，跳过 %d，失败 %d，耗时 %.0fs" % (n_new, n_skip, n_fail, time.time() - t0))
    print("[ok] 清单 %d 条文本 -> %s" % (len(manifest), MANIFEST))
    print("[ok] 音频目录共 %.1f MB" % (total_bytes / 1024 / 1024))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())

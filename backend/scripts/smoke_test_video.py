"""本地冒烟测试：用 storage 中授课视频验证通用情感识别链路与内存占用。"""
from __future__ import annotations

import json
import os
import resource
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))

# 强制通用情感路径（与当前产品默认一致）
os.environ.setdefault("EMOTION_MODEL", "emotion2vec")
os.environ.setdefault("PRELOAD_EMOTION", "1")
os.environ.setdefault("PRELOAD_FACE", "0")
os.environ.setdefault("RELEASE_MODELS_AFTER_JOB", "0")


def rss_mb() -> float:
    # ru_maxrss on macOS is bytes; on Linux is KB
    v = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return v / (1024 * 1024)
    return v / 1024.0


def main() -> int:
    from core import memory_config as memcfg
    print("=== Memory profile ===")
    print(memcfg.describe())
    print(f"RSS after import config: {rss_mb():.1f} MB")

    uploads = BACKEND / "storage" / "uploads"
    psy = uploads / "Psychology-01.mp4"
    eng = uploads / "English-01.mp4"
    print("\n=== Videos ===")
    for p in (psy, eng):
        if p.is_file():
            print(f"  {p.name}: {p.stat().st_size / 1024 / 1024:.1f} MB")
        else:
            print(f"  missing: {p}")
    if not psy.is_file():
        print("No Psychology-01.mp4, abort")
        return 1

    # ---- 1) 用已有切片测 emotion2vec ----
    seg_dir = None
    jobs = BACKEND / "storage" / "jobs"
    candidates = sorted(jobs.glob("*/segments/Psychology-01_seg*.mp4"))
    if candidates:
        seg_dir = candidates[0].parent
    print(f"\n=== Existing segments from {seg_dir} ===")

    sample_segs = []
    if seg_dir:
        sample_segs = sorted(seg_dir.glob("*.mp4"))[:3]
    print(f"sample count: {len(sample_segs)}")

    print("\n=== Load emotion2vec (warmup) ===")
    t0 = time.time()
    from core.recognizer import _get_predictor, recognize_segment
    pred = _get_predictor()
    print(f"emotion2vec load: {time.time() - t0:.1f}s, RSS={rss_mb():.1f} MB")

    print("\n=== Emotion on existing segments ===")
    for seg in sample_segs:
        t1 = time.time()
        r = recognize_segment(str(seg))
        dt = time.time() - t1
        print(
            f"  {seg.name}: {r.get('label_name_9')} "
            f"(conf={r.get('confidence')})  {dt:.2f}s  RSS={rss_mb():.1f} MB"
            + (f"  ERR={r.get('error')}" if "error" in r else "")
        )

    # ---- 2) 短音频测 ASR + 一句话情感 ----
    print("\n=== ASR on one segment audio ===")
    from core.asr import transcribe
    from core.ffmpeg_utils import extract_audio
    if sample_segs:
        wav = extract_audio(str(sample_segs[0]))
        if wav:
            t2 = time.time()
            sents = transcribe(wav)
            print(f"ASR load+transcribe: {time.time() - t2:.1f}s, sentences={len(sents)}, RSS={rss_mb():.1f} MB")
            for s in sents[:5]:
                print(f"    [{s['start']:.2f}-{s['end']:.2f}] {s['text'][:80]}")
            try:
                os.remove(wav)
            except OSError:
                pass
        else:
            print("extract_audio failed")
    print(f"RSS after ASR: {rss_mb():.1f} MB")

    # ---- 3) 从原视频切 25s，跑 mini pipeline（前 3 段）----
    print("\n=== Mini pipeline: cut 25s from Psychology-01 ===")
    from core.ffmpeg_utils import cut_video, get_video_duration
    from core.segmentation import split_video_by_utterances

    dur = get_video_duration(str(psy))
    print(f"full video duration: {dur:.1f}s")

    out_dir = BACKEND / "storage" / "jobs" / "_smoke_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    clip = out_dir / "psy_25s.mp4"
    ok = cut_video(str(psy), 0.0, 25.0, str(clip))
    print(f"cut ok={ok}, size={clip.stat().st_size / 1024 / 1024:.2f} MB" if clip.is_file() else "cut failed")
    if not ok or not clip.is_file():
        return 2

    seg_out = out_dir / "segments"
    seg_out.mkdir(exist_ok=True)
    t3 = time.time()
    segments = split_video_by_utterances(str(clip), str(seg_out), progress_callback=lambda m: print("  seg:", m))
    print(f"segmentation: {len(segments)} segments in {time.time() - t3:.1f}s, RSS={rss_mb():.1f} MB")

    print("\n=== Emotion on mini segments (max 5) ===")
    results = []
    for i, seg in enumerate(segments[:5]):
        t4 = time.time()
        r = recognize_segment(seg.output_path)
        row = {
            "index": seg.index,
            "start": round(seg.start_time, 2),
            "end": round(seg.end_time, 2),
            "text": (seg.text or "")[:60],
            "e2v": r.get("label_name_9"),
            "conf": r.get("confidence"),
            "sec": round(time.time() - t4, 2),
        }
        results.append(row)
        print(f"  {row}")

    print(f"\nPeak RSS (ru_maxrss): {rss_mb():.1f} MB")
    print(f"Config: {memcfg.describe()}")

    summary = {
        "video": psy.name,
        "duration_s": dur,
        "mini_segments": len(segments),
        "tested": results,
        "peak_rss_mb": round(rss_mb(), 1),
        "config": memcfg.describe(),
    }
    summary_path = out_dir / "smoke_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSummary written: {summary_path}")
    print("SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

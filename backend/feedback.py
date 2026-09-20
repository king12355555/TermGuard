# -*- coding: utf-8 -*-
"""反馈闭环：裁决落库 / 词条豁免 / 回归历史
闭环逻辑：
  - 译员对问题的裁决（confirm=确认是错/已修复，ignore=误报/允许）持久化
  - 同一词条的术语类问题被 ignore >= 2 次 -> 生成"豁免建议"（加入后该词条不再检查）
  - 同一词条被 confirm 多次 -> 生成"术语提醒"（该词条高频违规，建议加强规范）
  - 每次质检快照按数据指纹存档 -> 再次质检同数据时返回对比（回归报告）
"""
import json
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
FB_FILE = DATA_DIR / "feedback.json"
HIST_FILE = DATA_DIR / "check_history.json"

# 写操作加锁：多条裁决可能并发到达（线程池），read-modify-write 必须串行
_LOCK = threading.Lock()


def _read(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path, obj):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _fb():
    return _read(FB_FILE, {"reviews": [], "exceptions": []})


# ---------- 裁决落库 ----------

def add_review(item):
    with _LOCK:
        fb = _fb()
        key = item.get("key") or f'{item.get("line")}|{item.get("type")}|{item.get("title")}'
        item["key"] = key
        item["ts"] = int(time.time())
        reviews = fb["reviews"]
        for i, r in enumerate(reviews):
            if r.get("key") == key:          # 同一条问题更新裁决，避免重复计数
                reviews[i] = item
                break
        else:
            reviews.append(item)
        fb["reviews"] = reviews[-500:]
        _write(FB_FILE, fb)
    return item


# ---------- 豁免 ----------

def add_exception(source, reason=""):
    with _LOCK:
        fb = _fb()
        for e in fb["exceptions"]:
            if e["source"] == source:
                return False
        fb["exceptions"].append({
            "source": source,
            "reason": (reason or "译员反馈：该词条在此项目允许非标准译法").strip()[:200],
            "ts": int(time.time()),
        })
        _write(FB_FILE, fb)
    return True


def remove_exception(source):
    with _LOCK:
        fb = _fb()
        fb["exceptions"] = [e for e in fb["exceptions"] if e["source"] != source]
        _write(FB_FILE, fb)


def load_exceptions():
    return {e["source"] for e in _fb()["exceptions"]}


# ---------- 汇总 / 建议生成 ----------

def summary():
    fb = _fb()
    reviews = fb["reviews"]
    exceptions = fb["exceptions"]
    ex_sources = {e["source"] for e in exceptions}

    confirms = [r for r in reviews if r.get("verdict") == "confirm"]
    ignores = [r for r in reviews if r.get("verdict") == "ignore"]

    # 豁免建议：术语类问题、带词条、被 ignore >= 2、尚未豁免
    ig_cnt = {}
    ig_example = {}
    for r in ignores:
        t = r.get("term")
        if not t:
            continue
        ig_cnt[t] = ig_cnt.get(t, 0) + 1
        ig_example.setdefault(t, r.get("title", ""))
    exception_suggestions = [
        {"source": src, "count": cnt, "example": ig_example.get(src, "")}
        for src, cnt in ig_cnt.items()
        if src not in ex_sources and cnt >= 2
    ]

    # 术语提醒：被 confirm >= 1 的词条（高频违规信号）
    cf_cnt = {}
    for r in confirms:
        t = r.get("term")
        if t:
            cf_cnt[t] = cf_cnt.get(t, 0) + 1
    term_alerts = [{"source": src, "count": cnt} for src, cnt in cf_cnt.items()]

    return {
        "confirm": len(confirms),
        "ignore": len(ignores),
        "exceptions": exceptions,
        "exception_suggestions": exception_suggestions,
        "term_alerts": term_alerts,
    }


# ---------- 回归历史 ----------

def save_history(hash_key, stats):
    with _LOCK:
        hist = _read(HIST_FILE, {})
        hist[hash_key] = {
            "issue_lines": stats["issue_lines"],
            "total_issues": stats["total_issues"],
            "total_lines": stats["total_lines"],
            "ts": int(time.time()),
        }
        hist = dict(list(hist.items())[-5:])   # 只保留最近 5 个数据源的快照
        _write(HIST_FILE, hist)


def prev_stats(hash_key):
    return _read(HIST_FILE, {}).get(hash_key)

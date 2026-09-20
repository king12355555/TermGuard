# -*- coding: utf-8 -*-
"""术语库持久化层
设计：
  - 权威数据: backend/data/glossary.json （原子写入，防止写坏代码文件）
  - 同步可见: 保存时把 SAMPLE_GLOSSARY 段重写回 sample_data.py（纯文本替换）
  - 出厂备份: 首次保存前复制 sample_data.py -> sample_data.default.py，供"恢复内置"
"""
import json
import shutil
from pathlib import Path

import sample_data

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "glossary.json"
SAMPLE_FILE = ROOT / "sample_data.py"
DEFAULT_BACKUP = ROOT / "sample_data.default.py"

MARKER = "SAMPLE_GLOSSARY = ["


# ---------- 渲染 sample_data.py 的术语库段 ----------

def _field_repr(v):
    if isinstance(v, bool):
        return "True" if v else "False"
    return json.dumps(str(v), ensure_ascii=False)


def _glossary_block(glossary):
    lines = ["SAMPLE_GLOSSARY = ["]
    for t in glossary:
        parts = ["    {"]
        parts.append('"source": %s' % _field_repr(t.get("source", "")))
        parts.append(', "target": %s' % _field_repr(t.get("target", "")))
        parts.append(', "context": %s' % _field_repr(t.get("context", "")))
        parts.append(', "keep_english": %s' % _field_repr(bool(t.get("keep_english", False))))
        parts.append(', "note": %s' % _field_repr(t.get("note", "")))
        parts.append("},")
        lines.append("".join(parts))
    lines.append("]")
    return "\n".join(lines) + "\n"


def _ensure_default_backup():
    """首次保存前，把当前（出厂）sample_data.py 备份一份"""
    if not DEFAULT_BACKUP.exists() and SAMPLE_FILE.exists():
        shutil.copy2(SAMPLE_FILE, DEFAULT_BACKUP)


def sync_sample_file(glossary):
    """把术语库段同步重写到 sample_data.py（内容一致则跳过，避免无谓改动）"""
    if not SAMPLE_FILE.exists():
        return
    text = SAMPLE_FILE.read_text(encoding="utf-8")
    start = text.find(MARKER)
    if start == -1:
        raise ValueError("sample_data.py 中找不到 SAMPLE_GLOSSARY 定义")
    close = text.find("\n]", start)
    if close == -1:
        raise ValueError("SAMPLE_GLOSSARY 段格式异常，请检查文件")
    new_text = text[:start] + _glossary_block(glossary) + text[close + 2:]
    if new_text == text:
        return
    _ensure_default_backup()
    # 原子写：先写临时文件再替换，避免写入中断损坏
    tmp = SAMPLE_FILE.with_suffix(".py.tmp")
    tmp.write_text(new_text, encoding="utf-8")
    tmp.replace(SAMPLE_FILE)


# ---------- 对外 API ----------

def load_glossary():
    """读取权威术语库；首次运行时用内置默认初始化 data 文件"""
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    default = [dict(t) for t in sample_data.SAMPLE_GLOSSARY]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
    _ensure_default_backup()
    return default


def save_glossary(glossary):
    """保存术语库：写权威 JSON + 同步 sample_data.py，返回清洗后的列表"""
    clean = []
    for t in glossary or []:
        source = str(t.get("source", "") or "").strip()
        if not source:
            continue
        clean.append({
            "source": source,
            "target": str(t.get("target", "") or "").strip(),
            "context": str(t.get("context", "") or "").strip(),
            "keep_english": bool(t.get("keep_english", False)),
            "note": str(t.get("note", "") or "").strip(),
        })
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    sync_sample_file(clean)
    return clean


def reset_glossary():
    """恢复出厂术语库：整文件还原出厂备份，重建权威数据"""
    if DEFAULT_BACKUP.exists():
        # 还原 sample_data.py 整文件，并重新加载模块
        text = DEFAULT_BACKUP.read_text(encoding="utf-8")
        SAMPLE_FILE.write_text(text, encoding="utf-8")
        import importlib
        importlib.reload(sample_data)
        default = [dict(t) for t in sample_data.SAMPLE_GLOSSARY]
    else:
        default = [dict(t) for t in sample_data.SAMPLE_GLOSSARY]
    if DATA_FILE.exists():
        DATA_FILE.unlink()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
    return default

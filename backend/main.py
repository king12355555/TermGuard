# -*- coding: utf-8 -*-
"""TermGuard —— 游戏本地化术语一致性智能质检助手（后端 API）"""
import hashlib
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from checkers.rules import check_entries, compute_stats
from checkers.llm_check import check_with_llm
from sample_data import get_sample
from storage import load_glossary, save_glossary, reset_glossary
from feedback import (add_review, add_exception, remove_exception, load_exceptions,
                      summary as feedback_summary, save_history, prev_stats)

app = FastAPI(title="TermGuard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Term(BaseModel):
    source: str = ""
    target: str = ""
    context: str = ""
    keep_english: bool = False
    note: str = ""


class Entry(BaseModel):
    line: int = 0
    source: str = ""
    target: str = ""


class LLMOptions(BaseModel):
    enabled: bool = False
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"


class CheckRequest(BaseModel):
    entries: list[Entry] = Field(default_factory=list)
    glossary: list[Term] = Field(default_factory=list)
    llm: LLMOptions = Field(default_factory=LLMOptions)


@app.get("/api/sample")
def api_sample():
    d = get_sample()
    d["glossary"] = load_glossary()   # 术语库以持久化数据为准
    return d


class GlossarySaveRequest(BaseModel):
    glossary: list[Term] = Field(default_factory=list)


@app.post("/api/glossary/save")
def api_glossary_save(req: GlossarySaveRequest):
    clean = save_glossary([t.model_dump() for t in req.glossary])
    return {"ok": True, "count": len(clean)}


@app.post("/api/glossary/reset")
def api_glossary_reset():
    default = reset_glossary()
    return {"ok": True, "glossary": default}


@app.post("/api/check")
def api_check(req: CheckRequest):
    entries = [
        {"line": e.line, "source": e.source, "target": e.target}
        for e in req.entries if e.source.strip() or e.target.strip()
    ]
    # 豁免表：译员反馈后豁免的词条直接从本次检查中剔除
    exceptions = load_exceptions()
    glossary = [
        {"source": t.source, "target": t.target, "context": t.context,
         "keep_english": t.keep_english, "note": t.note}
        for t in req.glossary if t.source not in exceptions
    ]
    if not entries:
        return {"ok": False, "error": "没有可检查的文本，请先添加数据。"}

    issues = check_entries(entries, glossary)

    ai_issues, ai_error = [], None
    if req.llm.enabled and req.llm.api_key:
        ai_issues, ai_error = check_with_llm(
            entries, glossary, req.llm.api_key,
            base_url=req.llm.base_url, model=req.llm.model,
        )
    # LLM 复核类型归并到主列表（行号相同时排后展示）
    issues += ai_issues

    stats = compute_stats(issues, len(entries))
    stats["ai_issues"] = len(ai_issues)

    # 回归对比：同数据源上次检查的结果
    hash_key = hashlib.sha1(
        "".join(f"{e['line']}|{e['source']}|{e['target']}" for e in entries).encode("utf-8")
    ).hexdigest()
    prev = prev_stats(hash_key)
    save_history(hash_key, stats)

    return {"ok": True, "stats": stats, "issues": issues,
            "ai_error": ai_error, "llm_enabled": bool(req.llm.enabled and req.llm.api_key),
            "prev": prev}


# ---------- 反馈闭环 API ----------

@app.get("/api/feedback")
def api_feedback():
    return {"ok": True, **feedback_summary()}


class ReviewRequest(BaseModel):
    line: int = 0
    type: str = ""
    title: str = ""
    source: str = ""
    target: str = ""
    term: str = ""
    verdict: str = "ignore"   # confirm=确认有错/已修复, ignore=忽略/允许


@app.post("/api/review")
def api_review(req: ReviewRequest):
    add_review(req.model_dump())
    return {"ok": True}


class ExceptionRequest(BaseModel):
    source: str = ""
    reason: str = ""


@app.post("/api/exceptions/add")
def api_exceptions_add(req: ExceptionRequest):
    added = add_exception(req.source, req.reason)
    return {"ok": True, "added": added}


@app.post("/api/exceptions/remove")
def api_exceptions_remove(req: ExceptionRequest):
    remove_exception(req.source)
    return {"ok": True}


# ---------- AI 质检报告 ----------

class ReportRequest(BaseModel):
    name: str = ""
    stats: dict = Field(default_factory=dict)
    issues: list = Field(default_factory=list)
    llm: LLMOptions = Field(default_factory=LLMOptions)


@app.post("/api/report/generate")
def api_report_generate(req: ReportRequest):
    from report import generate_report
    return generate_report(
        name=req.name, stats=req.stats, issues=req.issues,
        api_key=req.llm.api_key, base_url=req.llm.base_url, model=req.llm.model,
    )


# ---------- 托管前端构建产物（单端口部署） ----------
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8010"))
    uvicorn.run(app, host="0.0.0.0", port=port)

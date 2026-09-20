# -*- coding: utf-8 -*-
"""TermGuard 规则检查引擎
层级设计（体现"用最合适的工具解决当前问题"的实用主义）：
  规则层（本文件）：快、确定性强 —— 占位符/数字/术语精确匹配/漏译
  LLM 层（llm_check.py）：慢、抓语义 —— 语境复核、语域提示（可选，无 Key 自动降级）
"""
import re

# ---------- 基础工具 ----------

_PH_RE = re.compile(r"\{[^{}]+\}|%[sdifb]|%\([^)]+\)[sdifb]|\[[A-Za-z0-9_ /]+\]|<[^<>]+>")
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?%?")

def _counts(items):
    d = {}
    for it in items:
        d[it] = d.get(it, 0) + 1
    return d

def _diff(source_items, target_items):
    """返回 (源文独有, 译文独有) —— 用于定位缺失/多余"""
    sc, tc = _counts(source_items), _counts(target_items)
    only_s, only_t = [], []
    for k, v in sc.items():
        if tc.get(k, 0) < v:
            only_s += [k] * (v - tc.get(k, 0))
    for k, v in tc.items():
        if sc.get(k, 0) < v:
            only_t += [k] * (v - sc.get(k, 0))
    return only_s, only_t

def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ---------- 主检查 ----------

def check_entries(entries, glossary):
    """entries: [{line, source, target}]  glossary: [{source,target,context,keep_english,note}]
    返回 issues: [{line, type, sev, title, detail, fix}]"""
    issues = []
    # 术语词条排序：source 长度降序（长词条优先匹配，实现上下文限定词条覆盖）
    terms = sorted(
        [t for t in glossary if (t.get("source") or "").strip()],
        key=lambda t: len(t["source"]), reverse=True,
    )

    # 记录每个词条在各行的命中情况（用于"跨行不一致"提示）
    term_hits = {i: [] for i in range(len(terms))}   # 每个词条命中的行号列表
    line_ok_term = {}                                # (line, term_idx) -> 是否合规

    for ent in entries:
        line = ent["line"]
        src, tgt = ent["source"] or "", ent["target"] or ""
        src_l = src.lower()

        # ===== 0. 未翻译 / 空译文 =====
        if not tgt.strip():
            issues.append({"line": line, "type": "漏译", "sev": "high",
                           "title": "译文为空", "detail": "该句未提供译文。",
                           "fix": "补充译文后再提交 QA。"})
        elif tgt.strip().lower() == src_l.strip():
            issues.append({"line": line, "type": "未翻译", "sev": "high",
                           "title": "译文与源文相同（疑似未翻译）",
                           "detail": "译文内容与英文源文完全一致，疑似漏翻。",
                           "fix": "确认是否需要翻译该句；若是保留英文（如专有名词句），可在术语库中登记。"})
        else:
            # ===== 长度比：疑似漏译（中文比英文紧凑，仅对长句且明显过短时触发，避免误报） =====
            if len(src) >= 70 and len(tgt) < len(src) * 0.30:
                issues.append({"line": line, "type": "疑似漏译", "sev": "mid",
                               "title": "译文长度异常偏短，疑似漏译后半句",
                               "detail": f"源文 {len(src)} 字符，译文仅 {len(tgt)} 字符。",
                               "fix": "对照源文检查是否遗漏了后半句信息。"})

        # ===== 1. 占位符比对 =====
        sp, tp = _PH_RE.findall(src), _PH_RE.findall(tgt)
        if sp or tp:
            miss_s, extra_t = _diff(sp, tp)
            if miss_s:
                issues.append({"line": line, "type": "占位符", "sev": "high",
                               "title": "译文缺少占位符",
                               "detail": f"源文含 {', '.join(_esc(m) for m in miss_s)}，译文中未找到。",
                               "fix": "在译文对应位置补回占位符（参数由游戏客户端动态替换，不能丢失或改写）。"})
            if extra_t:
                issues.append({"line": line, "type": "占位符", "sev": "mid",
                               "title": "译文出现源文没有的占位符",
                               "detail": f"译文中多出 {', '.join(_esc(m) for m in extra_t)}。",
                               "fix": "核对占位符是否被误添加，避免运行时替换出错。"})

        # ===== 2. 数字比对 =====
        sn, tn = _NUM_RE.findall(src), _NUM_RE.findall(tgt)
        if sn or tn:
            miss_n, extra_n = _diff(sn, tn)
            if miss_n:
                issues.append({"line": line, "type": "数字", "sev": "high",
                               "title": "数字与源文不一致",
                               "detail": f"源文数字 {', '.join(miss_n)} 在译文中缺失或被改写。",
                               "fix": "数值（伤害/费用/时长等）必须与源文完全一致，请核对。"})
            if extra_n:
                issues.append({"line": line, "type": "数字", "sev": "mid",
                               "title": "译文出现源文没有的数字",
                               "detail": f"译文多出数字 {', '.join(extra_n)}，请确认非笔误。",
                               "fix": "核对译文数字是否误加。"})

        # ===== 3. 术语检查（长词条优先，命中区间去重叠） =====
        occupied = []  # 已命中区间 [(start, end, term_idx)]

        def overlaps(s, e):
            return any(s < oe and e > os for (os, oe, _) in occupied)

        for ti, term in enumerate(terms):
            tsrc = term["source"]
            # 源文中查找（忽略大小写，词边界）
            for m in re.finditer(re.escape(tsrc), src, re.IGNORECASE):
                s, e = m.start(), m.end()
                if overlaps(s, e):
                    continue
                occupied.append((s, e, ti))
                break  # 每行每个词条只判一次（出现多处同样处理）

        for (s, e, ti) in occupied:
            term = terms[ti]
            tsrc, tgt_s, keep = term["source"], term.get("target", ""), term.get("keep_english", False)
            expected = tsrc if keep else tgt_s
            tgt_l = tgt.lower()
            ok = expected and expected.lower() in tgt_l
            term_hits[ti].append(line)
            if ok:
                line_ok_term[(line, ti)] = True
            else:
                # 构建违规描述
                ctx = term.get("context") or ""
                ctx_note = f"（语境：{ctx}）" if ctx else ""
                if keep:
                    title = f"专有名词「{tsrc}」不应意译"
                    detail = f"词条 {tsrc} 为保留英文的专有名词{ctx_note}，译文中未找到原文。"
                    fix = f"保留英文「{tsrc}」，可译为「{tsrc}（说明性译名）」首次出现时加注。"
                else:
                    title = f"术语「{tsrc}」未按标准译法翻译"
                    detail = f"术语库要求译作「{tgt_s}」{ctx_note}；译文中未找到。"
                    fix = f"统一改为「{tgt_s}」"
                sev = "high"
                issues.append({"line": line, "type": "术语", "sev": sev,
                               "term": tsrc,
                               "title": title, "detail": detail, "fix": fix})

    # ===== 4. 术语跨行一致性（同词条在多行出现，部分行合规部分违规） =====
    for ti, lines in term_hits.items():
        if len(lines) < 2:
            continue
        term = terms[ti]
        ok_lines = [l for l in lines if line_ok_term.get((l, ti))]
        bad_lines = [l for l in lines if not line_ok_term.get((l, ti))]
        if ok_lines and bad_lines:
            tsrc, tgt_s = term["source"], term.get("target", "")
            for l in bad_lines:
                issues.append({"line": l, "type": "术语不一致", "sev": "mid",
                               "term": tsrc,
                               "title": f"「{tsrc}」在本文件内译法不一致",
                               "detail": f"第 {', '.join(str(x) for x in ok_lines[:3])} 行使用标准译法「{tgt_s}」，本行未遵循。",
                               "fix": f"与本文件其它行保持一致，统一为「{tgt_s}」。"})

    # 排序：按行号、类型
    issues.sort(key=lambda x: (x["line"], x["type"]))
    return issues


def compute_stats(issues, total_lines):
    by_type = {}
    sev_high = 0
    for it in issues:
        by_type[it["type"]] = by_type.get(it["type"], 0) + 1
        if it["sev"] == "high":
            sev_high += 1
    clean_lines = total_lines - len({i["line"] for i in issues})
    return {
        "total_lines": total_lines,
        "issue_lines": len({i["line"] for i in issues}),
        "clean_lines": clean_lines,
        "total_issues": len(issues),
        "high": sev_high,
        "by_type": by_type,
    }

# -*- coding: utf-8 -*-
"""AI 质检报告总结
把规则层发现的"一堆技术问题"用大模型翻译成业务人员（PM/客户/译员主管）能听懂的语言。
无论是否配置 AI，都保证有输出：
  - 有 Key 且调用成功 -> 返回 AI 生成的 Markdown 报告 (mode=ai)
  - 无 Key 或调用失败 -> 返回基于规则的统计总结 (mode=rule)，并注明原因
"""
import json
from collections import Counter

REPORT_SYSTEM = """你是一名资深的游戏/软件本地化质量管理专家，擅长把技术质检结果翻译成业务人员（产品经理、客户、译员主管）能听懂的语言。

我会给你一份本地化 QA 质检的结构化结果（JSON），包含：检查规模、问题分布、高频出错的术语、若干示例。

请生成一份**简洁、有洞察、可执行的中文质检报告**，Markdown 格式，包含以下部分（用 ## 作为标题）：
## 总体评价 —— 用 2-3 句话概括本次翻译质量（结合问题句占比、严重度、问题集中度）
## 主要问题 —— 按类别列出，重点强调高频重复出错的术语/问题（这是译员最该改的），并指出背后的业务风险（如：术语不统一会让玩家困惑、降低品牌质感、影响后续版本复用）
## 优先级建议 —— 给出明确的修复先后顺序（先修什么、为什么），越具体越好
## 一句话总结 —— 给非技术负责人看的结论

要求：
- 语言通俗，不要堆技术术语；但术语库词汇（如 HP、Cloud Sync）要直接点名
- 要有洞察：不只罗列问题，要指出"反复出错的模式"和"对业务的影响"
- 控制在 350 字以内（不含标题）
- 只输出报告正文，不要输出任何说明、前言或代码块标记"""


def _rule_summary(name, stats, repeated, note=""):
    by = stats.get("by_type") or {}
    lines = ["## 总体评价（规则统计 · 未启用 AI 分析）",
             "- 数据源：%s；共 %s 句，%s 句有问题，命中 %s 处。"
             % (name, stats.get("total_lines", 0), stats.get("issue_lines", 0), stats.get("total_issues", 0))]
    if by:
        order = sorted(by.items(), key=lambda kv: -kv[1])
        lines.append("- 问题分布：" + "、".join(f"{k} {v} 处" for k, v in order) + "。")
    top = [r for r in repeated if r["count"] >= 2][:5]
    if top:
        lines.append("- 反复出错词条：" + "、".join(r["term"] for r in top) + "。")
    lines.append("\n## 优先级建议")
    lines.append("- 建议优先处理**反复出错**的术语类问题（术语不统一是最容易被玩家感知、也最影响后续版本复用的）。")
    if note:
        lines.append("\n> " + note)
    return "\n".join(lines)


def generate_report(name, stats, issues, api_key, base_url="https://api.deepseek.com", model="deepseek-chat"):
    # 聚合高频出错词条
    term_count = Counter()
    for it in issues:
        t = it.get("term")
        if t:
            term_count[t] += 1
    repeated = [{"term": t, "count": c} for t, c in term_count.most_common()]

    # 每类最多取 3 条示例（控制 token）
    samples = {}
    for it in issues:
        typ = it.get("type", "")
        if len(samples.get(typ, [])) < 3:
            samples.setdefault(typ, []).append({
                "line": it.get("line"),
                "title": it.get("title", ""),
                "fix": it.get("fix", ""),
            })

    payload = {
        "name": name,
        "total_lines": stats.get("total_lines", 0),
        "issue_lines": stats.get("issue_lines", 0),
        "total_issues": stats.get("total_issues", 0),
        "high": stats.get("high", 0),
        "by_type": stats.get("by_type", {}),
        "repeated_terms": repeated[:8],
        "samples": samples,
    }

    if not api_key:
        return {"ok": True, "mode": "rule",
                "text": _rule_summary(name, stats, repeated,
                                      note="未配置 API Key，仅生成了规则统计总结。配置 DeepSeek Key 后可生成 AI 深度分析。")}

    # 失败兜底文案
    fail = lambda msg: {"ok": True, "mode": "rule",
                        "text": _rule_summary(name, stats, repeated, note=("AI 调用失败，已降级为规则总结。原因：" + msg))}

    try:
        from openai import OpenAI
    except Exception:
        return fail("未安装 openai 库")

    try:
        client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/") + "/v1", timeout=60)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": REPORT_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.3,
            max_tokens=900,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return fail("模型返回为空")
        return {"ok": True, "mode": "ai", "text": text}
    except Exception as ex:
        return fail(str(ex)[:120])

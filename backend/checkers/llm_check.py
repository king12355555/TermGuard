# -*- coding: utf-8 -*-
"""TermGuard LLM 语境复核层（可选）
用大模型对规则层结果做语义复核与补充（语域、上下文限定词条、误译提示）。
无 API Key 时前端自动降级为"仅规则检查"，不影响主流程。
"""
import json

TYPE_MAP = {
    "术语": "术语",
    "术语不一致": "术语不一致",
    "占位符": "占位符",
    "数字": "数字",
    "漏译": "漏译",
    "未翻译": "未翻译",
    "疑似漏译": "疑似漏译",
}

SYSTEM_PROMPT = """你是一名专业的游戏本地化 QA 专家，精通中英游戏文案的术语一致性与语境校验。

我会给你一段双语对照（JSON 数组，每项含 line/source/target）和一份术语库（Glossary）。
请做两件事：
1. 对【每一条】译文做复核，找出规则工具难以发现的语义问题：上下文限定词条用错语境、语域不统一（正式/口语混用）、明显误译、遗漏关键信息等。
2. 只输出有问题的条目，格式为 JSON 数组：
[{"line": 行号, "type": "语境/语域/误译/信息遗漏", "reason": "为什么有问题(中文,一句话)", "suggestion": "建议修改(中文)"}]

规则：
- 术语库词条与标准译法必须严格遵守；keep_english=true 的词条必须保留英文原文。
- 若某词条在此语境有更合适的译法而术语库未覆盖（例如 Level 3 在章节标题语境应译“第 3 章”而非“等级 3”），请指出。
- 不要对没有把握的地方乱报，宁可少报不要误报。
- 只输出 JSON，不要输出任何其他文字。"""

def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, list) else []
    except Exception:
        return []

def check_with_llm(entries, glossary, api_key, base_url="https://api.deepseek.com", model="deepseek-chat"):
    """返回 (issues, error)。issues 为前端可直接展示的格式。"""
    if not api_key:
        return [], "未配置 API Key，本次仅执行规则检查。"

    try:
        from openai import OpenAI
    except Exception:
        return [], "未安装 openai 库，无法调用 LLM。"

    client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/") + "/v1", timeout=60)

    def render_glossary():
        lines = []
        for t in glossary:
            tgt = t.get("target", "")
            keep = "（保留英文）" if t.get("keep_english") else ""
            lines.append(f"- {t.get('source','')} → {tgt}{keep}"
                         + (f"  语境: {t.get('context','')}" if t.get("context") else ""))
        return "\n".join(lines)

    gloss_txt = render_glossary() or "(空)"
    all_issues = []
    error = None

    BATCH = 10
    total_batches = (len(entries) + BATCH - 1) // BATCH
    for i in range(0, len(entries), BATCH):
        batch = entries[i:i + BATCH]
        print(f"[LLM] 批次 {i // BATCH + 1}/{total_batches}，{len(batch)} 行，模型 {model}", flush=True)
        payload = json.dumps([
            {"line": e["line"], "source": e["source"], "target": e["target"]} for e in batch
        ], ensure_ascii=False)
        user_msg = f"=== 术语库 ===\n{gloss_txt}\n\n=== 待复核的双语文本 ===\n{payload}"
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.1,
                max_tokens=1200,
            )
            content = resp.choices[0].message.content or ""
            parsed = _extract_json(content)
            print(f"[LLM] 批次成功，返回 {len(content)} 字符，解析出 {len(parsed)} 条"
                  + (f"，样例: {str(parsed[0])[:150]}" if parsed else ""), flush=True)
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                try:
                    line = int(item.get("line", 0))
                except Exception:
                    continue
                all_issues.append({
                    "line": line,
                    "type": "AI 复核",
                    "sev": "mid",
                    "title": f"AI 提示：{item.get('type', '语义问题')}",
                    "detail": item.get("reason", ""),
                    "fix": item.get("suggestion", ""),
                })
        except Exception as ex:
            error = f"LLM 调用失败：{ex}"
            print(f"[LLM] 批次异常: {ex}", flush=True)

    print(f"[LLM] 完成：共 {len(all_issues)} 条 AI 提示，error={error}", flush=True)
    return all_issues, error

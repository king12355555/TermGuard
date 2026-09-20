# -*- coding: utf-8 -*-
"""引擎自测：跑内置 Demo 数据，输出每类问题命中情况"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\86199\Desktop\TermGuard\backend")

from sample_data import get_sample
from checkers.rules import check_entries, compute_stats

data = get_sample()
issues = check_entries(data["entries"], data["glossary"])
stats = compute_stats(issues, len(data["entries"]))

print("=== 期望违规行 ===")
expected = {2,4,6,7,8,9,10,12,13,14,17,22,24,25}
got = sorted({i["line"] for i in issues})
print("命中行:", got)
miss = expected - set(got)
extra = set(got) - expected
print("漏报(应报未报):", sorted(miss) if miss else "无 ✓")
print("误报(不应报却报):", sorted(extra) if extra else "无 ✓")
print()
print("=== 各类型统计 ===")
print(stats)
print()
print("=== 全部 issue 明细 ===")
for it in issues:
    print(f"L{it['line']:>2} [{it['type']}] ({it['sev']}) {it['title']} | {it['detail']} | 建议: {it['fix']}")

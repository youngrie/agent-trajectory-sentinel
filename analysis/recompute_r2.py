"""S3.2 — 独立复算 R2（确定性校验 vs 行为监控器）。

设计原则：**不 import derail**。只读 results/tables/ 下已提交的 CSV，
自己数 True、自己算比例，再与 CLAIMS.md 记录的目标值对照。

用途：把"我跑了作者的脚本"升级为"我独立验证了脚本输出的数字"。
若本脚本的输出与 runner 产出的汇总表一致，才说明那张表是对的。

运行：
    ..\\.venv\\Scripts\\python.exe analysis\\recompute_r2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Windows 控制台默认 cp936，print "✓" 会 UnicodeEncodeError 并让脚本半路死掉。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "results" / "tables"

# ---- 目标值：来自 CLAIMS.md 第 112-117 行 + 论文 Table 3 ----
# key = (dataset, arm)  →  {指标: 目标值}
EXPECTED = {
    ("organic_demo7b_cold", "T=0.2 (serving)"): {
        "checks_totals": 34 / 57,   # 0.597
        "checks_cov": 55 / 57,      # 0.965
        "monitor": 31 / 57,         # 0.544
        "checks_fp_rate": 0.0,
        "monitor_fp_rate": 11 / 63,  # 0.175
        "healthy_n": 63,
        "failed_n": 57,
    },
    ("organic_demo7b_ext", "T=0.9 (provoking)"): {
        "checks_totals": 53 / 82,   # 0.646
        "monitor": 33 / 82,         # 0.402
        "checks_fp_rate": 0.0,
        "monitor_fp_rate": 6 / 38,  # 0.158
        "healthy_n": 38,
        "failed_n": 82,
    },
}

# 论文 Table 3 附文对 held-out 语料的说法（episode 级明细需自己汇总）
HOLDOUT_PAPER = {"checks_totals": 0.54, "checks_cov": 0.93,
                 "checks_fp": 0, "healthy_n": 64}


def rate(num: float, den: float) -> float:
    return float(num) / float(den) if den else float("nan")


def fmt(x: float) -> str:
    return f"{x:.4f}"


def episode_level(name: str) -> dict:
    """从 episode 级明细表直接数真值。"""
    path = TABLES / name
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    for col in ("total_consistency", "required_coverage"):
        df[col] = df[col].astype(bool)
    healthy = df[df.label == "healthy"]
    failed = df[df.label != "healthy"]
    caught = failed.total_consistency
    caught_cov = failed.total_consistency | failed.required_coverage
    return {
        "file": name,
        "n": len(df),
        "healthy_n": len(healthy),
        "failed_n": len(failed),
        "checks_totals": rate(caught.sum(), len(failed)),
        "checks_cov": rate(caught_cov.sum(), len(failed)),
        "checks_fp": int(healthy.total_consistency.sum()),
        "checks_fp_rate": rate(healthy.total_consistency.sum(), len(healthy)),
        "labels": dict(failed.label.value_counts()),
        # 逐类召回，便于解释"为什么是这个数"
        "per_label": {
            lbl: (int(g.total_consistency.sum()), len(g),
                  int((g.total_consistency | g.required_coverage).sum()))
            for lbl, g in failed.groupby("label")
        },
    }


def from_summary() -> dict:
    """从 runner 汇总表读同一批数字，用于交叉核对。"""
    path = TABLES / "verification_vs_monitor.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    out = {}
    for (ds, arm), g in df.groupby(["dataset", "arm"]):
        h = g[g.label == "healthy"]
        f = g[g.label != "healthy"]
        out[(ds, arm)] = {
            "healthy_n": int(h.n.sum()),
            "failed_n": int(f.n.sum()),
            "checks_caught": int(f.total_consistency.sum()),
            "checks_cov_caught": int(f.with_coverage.sum()),
            "monitor_caught": int(f.monitor_alarmed.sum()),
            "checks_fp": int(h.total_consistency.sum()),
            "monitor_fp": int(h.monitor_alarmed.sum()),
            "checks_totals": rate(f.total_consistency.sum(), f.n.sum()),
            "checks_cov": rate(f.with_coverage.sum(), f.n.sum()),
            "monitor": rate(f.monitor_alarmed.sum(), f.n.sum()),
            "checks_fp_rate": rate(h.total_consistency.sum(), h.n.sum()),
            "monitor_fp_rate": rate(h.monitor_alarmed.sum(), h.n.sum()),
        }
    return out


def main() -> int:
    print("=" * 78)
    print("S3.2  独立复算 R2 —— 不 import derail，只读 CSV")
    print("=" * 78)

    summary = from_summary()
    # 只有 cold 与 holdout 有 episode 级产物；ext 语料只在汇总表里出现
    # （它由 run_verification_study 的默认 main() 打分，不写 episode 级 CSV），
    # 所以 ext 那一组只能核对汇总表，无法二次独立复算 —— 报告里要写明这一点。
    ep = {
        "organic_demo7b_cold": episode_level("verification_cold.csv"),
        "organic_demo7b_holdout": episode_level("verification_holdout.csv"),
    }

    ok = True
    for (ds, arm), exp in EXPECTED.items():
        print(f"\n### {ds} / {arm}")
        got = summary.get((ds, arm))
        if got is None:
            print("  !! 汇总表里没有这一组，检查 dataset/arm 名称")
            ok = False
            continue
        e = ep.get(ds, {})
        rows = [
            ("healthy n",        exp["healthy_n"], got["healthy_n"], None),
            ("failed n",         exp["failed_n"],  got["failed_n"],  None),
            ("checks 召回(仅总量)", exp["checks_totals"], got["checks_totals"], e.get("checks_totals")),
            ("checks 召回(+覆盖)",  exp.get("checks_cov"), got["checks_cov"], e.get("checks_cov")),
            ("monitor 召回",      exp["monitor"],     got["monitor"],     None),
            ("checks 误报率",     exp["checks_fp_rate"], got["checks_fp_rate"], e.get("checks_fp_rate")),
            ("monitor 误报率",    exp["monitor_fp_rate"], got["monitor_fp_rate"], None),
        ]
        print(f"  {'指标':<20}{'目标':>9}{'汇总表':>10}{'独立复算':>10}   判定")
        for label, want, got_v, indep in rows:
            if want is None or want != want:      # 未设定目标值（如 ext 的 +覆盖）
                print(f"  {label:<20}{'(未设目标)':>9}{fmt(got_v):>10}"
                      f"{(fmt(indep) if indep is not None else '—'):>10}   —")
                continue
            verdict = "✓" if abs(want - got_v) < 5e-4 else f"✗ 差 {got_v - want:+.4f}"
            if verdict != "✓":
                ok = False
            if indep is None:
                ind = "—"
            else:
                ind = fmt(indep)
                if abs(indep - want) >= 5e-4:
                    verdict += " / 独立复算不符!"
                    ok = False
            print(f"  {label:<20}{fmt(want) if isinstance(want, float) else want:>9}"
                  f"{fmt(got_v) if isinstance(got_v, float) else got_v:>10}{ind:>10}   {verdict}")

        if e.get("per_label"):
            print("  逐类（抓到/总数，含覆盖）:")
            for lbl, (c, n, c2) in sorted(e["per_label"].items()):
                print(f"    {lbl:<18} {c:>3}/{n:<3}  ({c2}/{n} 含覆盖)")
            if e.get("labels"):
                print(f"  注意：incomplete 类的 total_consistency 恒为 0，"
                      f"只有 coverage 能抓 —— 这就是"
                      f"「仅总量」比「含覆盖」低一截的原因。")

    # held-out 语料：论文只给了比例，自己汇总核对
    h = ep.get("organic_demo7b_holdout", {})
    if h:
        print(f"\n### organic_demo7b_holdout（120 episodes，正文称这是冻结的 held-out 测试）")
        print(f"  healthy n = {h['healthy_n']}, failed n = {h['failed_n']}")
        print(f"  checks 召回(仅总量) 复算 = {fmt(h['checks_totals'])}"
              f"  论文 {HOLDOUT_PAPER['checks_totals']}")
        print(f"  checks 召回(+覆盖)  复算 = {fmt(h['checks_cov'])}"
              f"  论文 {HOLDOUT_PAPER['checks_cov']}")
        print(f"  checks 误报         复算 = {h['checks_fp']}/{h['healthy_n']}"
              f"  论文 {HOLDOUT_PAPER['checks_fp']}/{HOLDOUT_PAPER['healthy_n']}")
        for lbl, (c, n, c2) in sorted(h["per_label"].items()):
            print(f"    {lbl:<18} {c:>3}/{n:<3}  ({c2}/{n} 含覆盖)")

    # provoked 语料：论文 §10 的 26/26 诱发幻觉
    p = episode_level("verification_provoked.csv")
    if p:
        print(f"\n### organic_demo7b_provoked（诱发语料，论文 §10：26/26 被抓）")
        print(f"  healthy n = {p['healthy_n']}, failed n = {p['failed_n']}, "
              f"总数 = {p['n']}")
        print(f"  checks 召回(仅总量) = {fmt(p['checks_totals'])}"
              f"  ({int(p['checks_totals'] * p['failed_n'])}/{p['failed_n']})")
        print(f"  checks 误报 = {p['checks_fp']}/{p['healthy_n']}")
        for lbl, (c, n, c2) in sorted(p["per_label"].items()):
            print(f"    {lbl:<18} {c:>3}/{n:<3}  ({c2}/{n} 含覆盖)")

    print("\n" + "=" * 78)
    print("结论：" + ("全部与目标值一致 ✓" if ok else "存在差异，见上方 ✗ 标记"))
    print("=" * 78)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

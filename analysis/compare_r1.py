"""S3.1 — R1 复现核对：工作副本 vs git HEAD 逐字节 + 逐指标比对。

两件事一起做：
  1) 字节级：把当前的 results/tables/multiseed_summary.csv 与 HEAD 里提交的版本比较，
     判断这次重跑是否"原样重建"了已发布的表。
  2) 指标级：把 esn_cusum_max 的四个核心指标与 CLAIMS.md 的目标值比较，
     给出偏差，并以"标准差的倍数"表示（因为多 seed 天然有波动）。

运行（在 agent-trajectory-sentinel 根目录）：
    ..\\.venv\\Scripts\\python.exe analysis\\compare_r1.py

退出码：0 = 全部通过；1 = 有差异（差异本身不一定是错误，需人工判读）。
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REL = "results/tables/multiseed_summary.csv"
WORK = ROOT / REL

# ---- 目标值：CLAIMS.md 第 40-43 行 + multiseed_summary.csv 首行 ----
TARGET = {
    "esn_cusum_max": {
        "detection_rate": (0.7065, 0.0682),
        "episode_auc":    (0.87205, 0.01529),
        "mean_lead_all":  (4.613, 0.974),
        "healthy_fa_rate": (0.04375, 0.01593),
    },
    "delta_mahalanobis": {
        "detection_rate": (0.3745, 0.0313),
    },
}


def git_show_head() -> str | None:
    """取 HEAD 里提交的原始 CSV 文本。"""
    try:
        out = subprocess.run(
            ["git", "show", f"HEAD:{REL}"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout
    except subprocess.CalledProcessError:
        return None


def main() -> int:
    print("=" * 78)
    print("S3.1  R1 复现核对（multiseed_summary.csv）")
    print("=" * 78)

    if not WORK.exists():
        print(f"!! 找不到 {REL} —— S1 还没跑完，或跑到了别的路径。")
        return 1

    head_text = git_show_head()
    cur_text = WORK.read_text(encoding="utf-8")

    # ---------- 1. 字节级 ----------
    print("\n### 1. 字节级比对（工作副本 vs HEAD 已提交版本）")
    if head_text is None:
        print("  !! 无法从 git 取到 HEAD 版本（可能不在仓库根目录）")
    elif head_text == cur_text:
        print("  结果：**逐字节完全一致** ✓")
        print("  含义：本次重跑原样重建了已发布的表，这是最强的复现证据。")
    else:
        print("  结果：文本不一致，逐列看差异 ↓")
        h = pd.read_csv(io.StringIO(head_text))
        c = pd.read_csv(io.StringIO(cur_text))
        if list(h.columns) != list(c.columns):
            print("  !! 列名变了 —— 说明代码或配置不是同一版，先查这个")
        else:
            num = [x for x in h.columns if x != "monitor"]
            diff = (h.set_index("monitor")[num] - c.set_index("monitor")[num]).abs()
            worst = diff.max()
            changed = worst[worst > 0]
            if changed.empty:
                print("  数值全等，差异只在格式（行序/精度/换行）—— 仍算复现成功")
            else:
                print("  有数值变化的列：")
                for col, v in changed.items():
                    print(f"    {col:<28} 最大绝对差 {v:.6g}")

    # ---------- 2. 指标级 ----------
    print("\n### 2. 指标级比对（对照 CLAIMS.md 目标值）")
    cur = pd.read_csv(WORK).set_index("monitor")
    colmap = {
        "detection_rate": ("detection_rate_mean", "detection_rate_std"),
        "episode_auc":    ("episode_auc_mean", "episode_auc_std"),
        "mean_lead_all":  ("mean_lead_all_mean", "mean_lead_all_std"),
        "healthy_fa_rate": ("healthy_fa_rate_mean", "healthy_fa_rate_std"),
    }

    ok = True
    for monitor, targets in TARGET.items():
        if monitor not in cur.index:
            print(f"\n  [{monitor}] 不在表里 —— 检查 torch 是否装好（GRU/LSTM/TCN 需要）")
            ok = False
            continue
        print(f"\n  [{monitor}]")
        print(f"    {'指标':<20}{'目标':>10}{'本次':>10}{'偏差':>10}{'σ 倍数':>8}  判定")
        for key, (mu, sd) in targets.items():
            mcol, scol = colmap[key]
            got = float(cur.loc[monitor, mcol])
            got_sd = float(cur.loc[monitor, scol])
            delta = got - mu
            z = abs(delta) / sd if sd else float("inf")
            if abs(delta) < 1e-9:
                v = "✓ 完全一致"
            elif z < 1.0:
                v = f"✓ 在 1σ 内"
            elif z < 2.0:
                v = f"~ 在 {z:.1f}σ（需解释）"
            else:
                v = f"✗ {z:.1f}σ（复现失败）"
            if z >= 2.0:
                ok = False
            print(f"    {key:<20}{mu:>10.4f}{got:>10.4f}{delta:>+10.4f}{z:>8.2f}  {v}")
            print(f"    {'  (std)':<20}{'':>10}{got_sd:>10.4f}")

    # ---------- 3. 全表概览 ----------
    print("\n### 3. 全表概览（11 个监控器，检测率降序）")
    view = cur[["detection_rate_mean", "healthy_fa_rate_mean", "episode_auc_mean"]]
    print(view.sort_values("detection_rate_mean", ascending=False)
              .round(4).to_string())

    print("\n" + "=" * 78)
    print("判定：" + ("通过（可写入报告「结果」一节）" if ok else "有超标偏差，需在报告里解释归因"))
    print("=" * 78)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

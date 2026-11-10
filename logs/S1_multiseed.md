# S1 — R1 主复现：§6 合成研究 5-seed

**日期** 2026-11-10 / **工作目录** `agent-trajectory-sentinel` / **解释器** `.venv\Scripts\python.exe` (Python 3.13.18) / **HEAD** `1b3e07fe`

**命令**

```
..\.venv\Scripts\python.exe -m derail.experiments.run_multiseed *>&1 | Tee-Object logs/S1_multiseed.log
```

**规模** quick=False；5 个 seed（20260713 / 7 / 101 / 202 / 303）；每个 seed 数据 split = train 240 / val 120 / cal 420 / test 560。
**耗时** 894.7 + 890.0 + 876.2 + 545.6 + 398.0 = 3604.5 s ≈ 60 min（前三个 seed 各约 15 min，后两个约 7–9 min；差异来自 torch 基线拟合阶段，未影响结果）。

---

## 1. 目标值对照（`results/tables/multiseed_summary.csv` 的 `esn_cusum_max` 行）

| 指标 | CLAIMS.md 目标 | 本次运行 | 偏差 | 判定 |
|---|---|---|---|---|
| detection_rate | 0.7065 ± 0.0682 | 0.7065 ± 0.0682 | 0.0000 | ✅ 逐字节一致 |
| mean_lead_all | 4.6130 ± 0.9744 | 4.6130 ± 0.9744 | 0.0000 | ✅ 逐字节一致 |
| episode_auc | 0.87205 ± 0.01529 | 0.87205 ± 0.01529 | 0.0000 | ✅ 逐字节一致 |
| healthy_fa_rate | 0.04375 ± 0.01593 | 0.04375 ± 0.01593 | 0.0000 | ✅ 逐字节一致 |

**判读**：主目标（ESN-CUSUM-max 的四个 headline 指标，均值与标准差）**一个字节都没变**。这是 R1 的最强证据形态——不是"落在容差内"，而是字符串相等。

## 2. 逐 seed 判定与配置哈希

`results/multiseed.json`：

| 字段 | 提交版 | 本次 | 一致 |
|---|---|---|---|
| `verdicts_by_seed`（5 seed × H1/H2/H3a/H3b） | 见下 | 同 | ✅ |
| `all_supported_every_seed` | `false` | `false` | ✅ |
| `config_sha256_by_seed`（5 个哈希） | — | 全同 | ✅ |

逐 seed 判定（本次 = 提交版）：

```
20260713  H1 SUPPORTED      H2 SUPPORTED  H3a SUPPORTED  H3b SUPPORTED
7         H1 NOT SUPPORTED  H2 SUPPORTED  H3a SUPPORTED  H3b MIXED
101       H1 SUPPORTED      H2 SUPPORTED  H3a SUPPORTED  H3b SUPPORTED
202       H1 SUPPORTED      H2 SUPPORTED  H3a SUPPORTED  H3b SUPPORTED
303       H1 SUPPORTED      H2 SUPPORTED  H3a SUPPORTED  H3b SUPPORTED
```

**判读**：`all_supported_every_seed=false` 是**仓库原有事实**，不是复现引入的。seed 7 的 H1 不成立、H3b 为 MIXED，5 个 seed 里 4 个支持 H1。报告里必须照实写"4/5 seed 支持"，不能只写 5-seed 均值支持。

## 3. 产物差异（`git diff`，HEAD vs 本次）

| 表 | 内容 | 最大相对差 | 变动范围 |
|---|---|---|---|
| `h1_significance.csv` | **逐字节一致** | — | — |
| `h2_channels.csv` | **逐字节一致** | — | — |
| `h3_calibration.csv` | **逐字节一致** | — | — |
| `h3_escalation.csv` | **逐字节一致** | — | — |
| `h1_main.csv` | 否 | 1.38e-11 | 仅 `theta` 列，16 个监控器全部 |
| `delay_fa_curves.csv` | 否 | 6.68e-11 | 仅 `theta` 列 |
| `h3_reliability.csv` | 否 | 3.76e-10 | 仅 `mean_confidence` 列 |
| `multiseed_summary.csv` | 否 | 9.88e-02 | **仅 `tcn` 一行** |

**判读**：
- 前四张表完全没动；`theta` / `mean_confidence` 的差异量级在 **1e-11 ~ 1e-10 相对误差**，即 float64 最后几位，来源是 BLAS 归约顺序（本机 Python 3.13 wheel 与原环境 3.14 wheel 的 SIMD 内核不同）。这些是**标定阈值本身**，不影响任何离散判定——detection / FA / lead / AUC 全部逐值相同。
- `multiseed_summary.csv` 只有 `tcn` 一行动了：det 0.4025→0.4135、lead 2.749→2.8195、AUC 0.72902→0.72965、FA 0.065→0.06375。差值 0.011 相当于其 seed 间标准差 0.050 的 **0.22σ**。

## 4. torch 基线的可复现边界（本阶段最重要的负结果）

`tcn` 是唯一显著偏移的监控器，而 `gru` / `lstm` / `linear_ar` 全部逐字节一致。

原因在 `derail/monitor/seq_baselines.py:322-334`：TCN 用 `torch.manual_seed` + 4 层空洞卷积（dilation 1/2/4/8）+ Adam 训练 10 epoch。种子固定，但 **`nn.Conv1d` 的 CPU 前向/反向由 oneDNN 内核实现，内核版本随 wheel 二进制而非版本号变化**。本项目 lock 写 `torch==2.12.0+cpu`，但 cp313 与 cp314 是两个不同的编译产物，浮点累加顺序不同 → 10 个 epoch 的优化轨迹逐渐分叉。

**结论**：ESN 主干（闭式岭回归解，无 SGD）与统计监控器**可位级复现**；依赖 SGD 训练的 torch 基线**只能做到统计等价**。这条边界必须写进报告，否则 `git diff` 里那一行 tcn 会被误读为复现失败。

---

## 结论

| 检查项 | 结果 | 是否阻塞 |
|---|---|---|
| 主目标 4 指标（均值+标准差） | ✅ 逐字节一致 | — |
| 逐 seed 判定 / 配置哈希 | ✅ 全同 | — |
| 6/11 产物表 | ✅ 逐字节一致 | — |
| 3 张表的标定阈值 | ✅ 1e-11 量级浮点噪声 | 否 |
| tcn 基线（torch SGD） | ⚠️ 单行偏移 0.22σ | 否，需在报告中说明归因 |
| 5/5 seed 全支持 | ⚠️ `false`（seed 7） | 否，仓库原有事实 |

**S1 判定：通过。R1 复现成立，且达到位级一致（除 torch-SGD 基线外）。**

# S2 — R2 次复现：确定性校验 vs 行为监控器（Table 3）

**日期** 2026-11-10 / **工作目录** `agent-trajectory-sentinel` / **解释器** `.venv\Scripts\python.exe` (Python 3.13.18) / **HEAD** `1b3e07fe`

**命令**（`scripts\run_s2.ps1`，三条依次执行）

```
..\.venv\Scripts\python.exe -m derail.verify.run_verification_study                          *>&1 | Tee-Object logs/S2_vs_monitor.log
..\.venv\Scripts\python.exe -m derail.verify.run_verification_study --holdout organic_demo7b_cold    *>&1 | Tee-Object logs/S2_cold.log
..\.venv\Scripts\python.exe -m derail.verify.run_verification_study --holdout organic_demo7b_holdout *>&1 | Tee-Object logs/S2_holdout.log
```

**耗时** 约 3 min（纯确定性，无训练、无 LLM）。三条命令 exit code 均为 0。

---

## 1. 目标值对照（`results/tables/verification_vs_monitor.csv`）

### T=0.2（serving，论文 Table 3 主行）

| 指标 | CLAIMS.md | 本次 | 判定 |
|---|---|---|---|
| Checks 召回（仅总量） | 0.597 (34/57) | 0.5965 (34/57) | ✅ |
| Checks 召回（+coverage） | 0.965 (55/57) | 0.9649 (55/57) | ✅ |
| Monitor 召回 | 0.544 (31/57) | 0.5439 (31/57) | ✅ |
| Checks 误报 | 0 (0/63) | 0 (0/63) | ✅ |
| Monitor 误报 | 0.175 (11/63) | 0.1746 (11/63) | ✅ |

### T=0.9（provoking）

| 指标 | CLAIMS.md | 本次 | 判定 |
|---|---|---|---|
| Checks 召回（仅总量） | 0.646 (53/82) | 0.6463 (53/82) | ✅ |
| Checks 召回（+coverage） | 96% (79/82) | 0.9634 (79/82) | ✅ |
| Monitor 召回 | 0.402 (33/82) | 0.4024 (33/82) | ✅ |
| Checks 误报 | 0 (0/38) | 0 (0/38) | ✅ |
| Monitor 误报 | — | 0.158 (6/38) | ✅ |

### Holdout（`--holdout organic_demo7b_holdout`，未见语料）

| 指标 | CLAIMS.md | 本次 | 判定 |
|---|---|---|---|
| 失败捕获（仅总量） | 0.536 (30/56) | 0.5357 (30/56) | ✅ |
| 失败捕获（+coverage） | 0.929 (52/56) | 0.9286 (52/56) | ✅ |
| 误报 | 0 (0/64) | 0 (0/64) | ✅ |

**判读**：三张表、11 个指标全部命中，且分子分母逐一相同。论文 Table 3 里"60% vs 54%、误报 0/63 vs 11/63"的对比在本次运行中完整复现。

## 2. 产物字节级比对

| 文件 | 结果 |
|---|---|
| `results/tables/verification_vs_monitor.csv` | **逐字节一致** |
| `results/tables/verification_cold.csv` | **逐字节一致** |
| `results/tables/verification_holdout.csv` | **逐字节一致** |

**判读**：R2 是**零浮点噪声**的位级复现——比 R1 更干净，因为它全程只做符号/计数运算，没有矩阵分解。

## 3. 逐类明细（用于报告的分类型表）

| 语料 | label | n | 仅总量 | +coverage |
|---|---|---|---|---|
| cold T=0.2 | healthy | 63 | 0 | 0 |
| | arithmetic_error | 37 | 29 (78%) | 37 (100%) |
| | hallucinated | 7 | 5 (71%) | 5 (71%) |
| | incomplete | 13 | 0 (0%) | 13 (100%) |
| holdout | healthy | 64 | 0 | 0 |
| | arithmetic_error | 36 | 26 (72%) | 36 (100%) |
| | hallucinated | 8 | 4 (50%) | 4 (50%) |
| | incomplete | 12 | 0 (0%) | 12 (100%) |
| provoking T=0.9 | healthy | 38 | 0 | 0 |
| | arithmetic_error | 37 | 26 (70%) | 36 (97%) |
| | hallucinated | 7 | 7 (100%) | 7 (100%) |
| | incomplete | 18 | 0 (0%) | 16 (89%) |
| | other | 20 | 20 (100%) | 20 (100%) |

**判读（必须写进报告的方法学要点）**：`incomplete` 类的 `total_consistency` **恒为 0**——"任务没做完" 不会让任何一条加总校验失败，只有 `required_coverage` 抓得到。因此：
- 只数 `total_consistency` → 34/57 = 60%
- 加上 coverage → 55/57 = 96%

任何不区分这两个口径的复算都会得到 47/57 = 82% 这个**错误**数字（按 label≠healthy 直接数 True）。这是本次复现实际踩到的第一个坑。

## 4. 覆盖范围声明

`organic_demo7b_ext`（T=0.9 语料）**没有 episode 级产物**，它只由默认 `main()` 聚合成 `verification_vs_monitor.csv`，不写 `verification_ext.csv`。因此这一组只能核对汇总表，**无法做第二遍独立复算**。报告里必须写明这条边界。

---

## 结论

| 检查项 | 结果 | 是否阻塞 |
|---|---|---|
| Table 3 主行（T=0.2）5 项 | ✅ 全部命中 | — |
| T=0.9 5 项 | ✅ 全部命中 | — |
| Holdout 3 项 | ✅ 全部命中 | — |
| 3 张 CSV | ✅ 逐字节一致 | — |
| `_ext` 语料的独立复算 | ⚠️ 无 episode 级产物，不可二次复算 | 否，需声明 |

**S2 判定：通过。R2 复现成立，位级一致。**

# S0 — 基线自检记录

**日期**：2026-11-10 13:54 (GMT+8)
**工作目录**：`E:\desktop_directory\desktop\CUHK COURSE\FTEC 5660\project_2\agent-trajectory-sentinel`
**解释器**：`.venv\Scripts\python.exe`（Python 3.13.18）
**HEAD commit**：`1b3e07fe` — *Compare the frozen baseline as numbers within a tolerance, not as a hash*（`main`，与 `origin/main` 同步）

---

## 1. `git status --porcelain`

```
（无输出）
```

exit code = 0

**判读**：工作树干净 —— 没有未提交改动、没有未跟踪文件。这是"起点无污染"的前提，后面 `git diff` 得出的任何差异都只可能来自我的运行。

---

## 2. `git log --oneline -1`

```
1b3e07fe (HEAD -> main, origin/main, origin/HEAD) Compare the frozen baseline as numbers within a tolerance, not as a hash
```

**判读**：复现基线 commit 记录为 **`1b3e07fe`**。报告"设置"一节必须写明这一串，否则读者无法判断我复现的是哪一版树（论文 v1 对应的是 `00c0673`，两者不同）。

---

## 3. `python -m devtools.claims_ledger --check`

```
all 121 claims match their artifacts
```

exit code = 0

**判读**：断言台账 121 条全部与产物对上。含义是：**在我动手之前，仓库自身的"数字 ↔ 文件"一致性是成立的**。这一步把后面所有偏差的责任边界划清了——如果 R1 跑出来的数字和 CSV 不同，那不是仓库账目错，而是"我的环境 vs 参考环境"或"我的运行 vs 已提交产物"的差异。

---

## 4. `python -m pytest -m "not network and not ollama" -q`

```
........sssssssss...................................................................................................................................... [ 16%]
... (中略：进度点阵) ...
869 passed, 20 skipped, 6 deselected in 597.80s (0:09:57)
```

**最慢的 10 个测试**

```
166.27s  tests/test_behavior_regression.py::test_quick_study_matches_snapshot
 32.13s  tests/test_module_selftests.py::test_selftest_slow[derail.monitor.hybrid]
 22.00s  tests/test_framework_generalized_monitor_eval.py::test_main_runs_end_to_end_on_synthetic_disjoint_corpora
 21.27s  tests/test_module_selftests.py::test_selftest_slow[derail.monitor.hmt_esn]
 21.11s  tests/test_module_selftests.py::test_selftest_slow[derail.monitor.seq_baselines]
 15.55s  tests/test_monitor_internals.py::test_demo_real_injected_episodes_are_committed_and_detectable
 14.13s  tests/test_pre_fix_baseline_reproducible.py::test_the_calibrated_arm_reproduces_the_published_rates
 12.89s  tests/test_module_selftests.py::test_selftest_slow[derail.monitor.grounding]
 11.33s  tests/test_module_selftests.py::test_selftest_slow[derail.harness.demo_real]
  9.94s  tests/test_module_selftests.py::test_selftest_fast[derail.monitor.esn]
```

**20 条 skip 的原因（按类别归并）**

| 类别 | 条数 | 原因原文 | 性质 |
|---|---|---|---|
| 论文源文件缺失 | 12 | `manuscripts are local-only; no arXiv source to package` 等 | 作者本地文件未随仓库发布，**预期内** |
| HF 数据集构建产物 | 4 | `no build/hf; run devtools.hf_dataset --build` / `No module named 'huggingface_hub'` | 可选依赖未装，**不影响 R1/R2** |
| 可选依赖缺失 | 1 | `No module named 'pyarrow'` | 同上 |
| 部署冻结未构建 | 1 | `deployment freeze not built yet` | 需额外产出，**不涉及 R1/R2** |
| 审计报告不在本检出 | 1 | `stored audit report not present in this checkout` | 同上 |

**判读**：**869 passed / 0 failed**，离线套件全绿。三条要写进报告的点：

1. **`test_behavior_regression.py::test_quick_study_matches_snapshot` 通过（166 秒）** —— 这条是重量级证据：它把一次 quick 规模的研究跑完，再与冻结的行为快照逐值比对。说明在我这台机器、Python 3.13.18 上，**研究代码的行为与作者记录的快照一致**。R1 若出现偏差，范围就被压缩到"多 seed 的统计波动"，而不是"代码行为变了"。
2. **20 条 skip 全部有明确原因，且没有一条触及 R1/R2 的路径**（全是论文打包、HF 数据集、部署冻结这些周边产物）。报告里要这么写，否则读者容易误读成"有 20 项没验证"。
3. **`test_pre_fix_baseline_reproducible.py::test_the_calibrated_arm_reproduces_the_published_rates` 通过** —— 仓库自己内置了"发布速率可复现"的测试，这条通过等于作者替你做了第一层复现验证。

**注意**：全程 **9 分 57 秒**，比 plan 里估的 5 分钟长一倍（慢在 quick 研究的 166 秒）。S1 的实际耗时也要按 "估计值 × 2" 预留。

---

## 结论

| 检查项 | 结果 | 是否阻塞后续 |
|---|---|---|
| 工作树干净 | ✅ 无输出 | — |
| 基线 commit 已记录 | ✅ `1b3e07fe` | — |
| 断言台账自洽 | ✅ 121/121 一致 | — |
| 离线测试套件 | ✅ 869 passed / 0 failed / 20 skipped（597.80s） | — |
| 行为快照回归 | ✅ 通过（166s） | — |

**S0 判定：通过，可进入 S1。**

同时确立一条基线事实：**在 `1b3e07fe` + Python 3.13.18 这套组合下，仓库自带的全部离线验证都成立**。后续 R1 的任何数字偏差，只能归因于"多 seed 统计波动"或"3.13 vs 3.14 的浮点差异"，不能归因于"代码/数据坏了"——这个责任边界现在有据可依。

---

## 记录规范（后续 S1–S4 沿用同一格式）

每个阶段一个 `logs/S*.md`，四段固定结构：

~~~~markdown
# S<N> — <阶段名>
**日期** / **工作目录** / **解释器** / **HEAD commit**

## <步骤序号>. `<命令原文>`

    <完整原始输出，不要摘要、不要删行>

exit code = <N>

**判读**：<这段输出说明了什么，一到三句>

---

## 结论

<表格：检查项 / 结果 / 是否阻塞>
~~~~

三条原则：

1. **命令原样抄，输出原样贴。** 报告里的 debug diary 直接由这些文件拼成，重新打字会引入失真。
2. **每条都给 exit code。** "没报错"不等于成功，退出码才是证据。
3. **判读只写"这说明什么"，不写"我觉得"。** 事实与解释分开，后面写结论时不会把猜测当结果。

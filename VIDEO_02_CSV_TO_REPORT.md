# 短视频 02：从 CSV 到数据质量报告（约 60–90 秒）

## 视频定位

第一条教学视频。重点不是展示复杂模型，而是解释 SignalSweep 的底层工作流：先让数据问题可观测，再交给 Agent 决定下一步动作。

## 标题候选

1. 我用 Python 把一份 CSV 自动变成数据质量报告
2. 做 AI Agent 之前，先把数据问题找出来
3. 一个数据质量 Agent 的最小可行版本

## 口播稿

> 做数据 Agent，第一步不是马上调用大模型，而是先让数据问题变得清楚。
>
> 这是 SignalSweep 的第一版。输入是一份普通的 CSV 订单数据。
>
> 我先读取表头和数据类型，统计总行数、缺失值和重复记录；然后检查没有变化的常量列，再用一个简单的统计规则找异常值。
>
> 运行这条命令，SignalSweep 会自动生成三个结果：问题统计、清洗后的 CSV，以及一份 Markdown 报告。
>
> 现在这一版还是确定性的 Python 流程，结果可重复、方便测试。下一步，我会用 Gemini 和 Google ADK 让 Agent 根据问题类型决定：清洗、生成报告，还是提醒用户处理。
>
> 这就是我参加 Google All Things Agentic Hackathon 的第一个可运行版本。

## 镜头表

| 时间 | 画面 | 屏幕文字 |
|---|---|---|
| 0–5 秒 | 展示一份有问题的 CSV | 做 Agent 前，先看清数据问题 |
| 5–15 秒 | 编辑器打开 `sample_data/orders.csv` | 输入：普通 CSV |
| 15–30 秒 | 快速展示 `tools.py` 中的检查函数 | 缺失值｜重复记录｜常量列｜异常值 |
| 30–42 秒 | 终端执行 CLI 命令 | 一条命令跑完整个流程 |
| 42–58 秒 | 展示终端输出和 `.artifacts/` | 3 个输出结果 |
| 58–72 秒 | 打开 Markdown 报告 | 问题可解释、结果可复现 |
| 72–90 秒 | 展示 Agent/Cloud Run 规划图或项目目录 | 下一步：Gemini + ADK + Cloud Run |

## 录屏命令

在 `signalsweep` 目录执行：

```bash
PYTHONPATH=src python3 -m signalsweep.cli sample_data/orders.csv --output-dir .artifacts
```

录屏时依次展示：

```text
Rows: 12
Issues: 3
Anomalies: 1
```

然后打开：

```text
.artifacts/report.md
.artifacts/cleaned_orders.csv
```

## 拍摄重点

- 先展示输入和输出，再解释代码，观众更容易跟上。
- 代码画面只展示关键函数名，不要长时间滚动完整文件。
- 明确说“这一版还没有接入大模型”，反而能体现工程上的分层设计。
- 把“确定性工具 → Agent 决策 → Cloud Run 部署”作为连续系列主线。

## 发布文案

```text
做 AI Agent 的第一步，不一定是调用大模型。
我先用 Python 做了一个可重复的数据质量流水线：读取 CSV，发现缺失值、重复记录和异常值，再自动生成清洗文件和 Markdown 报告。
下一步接入 Gemini、Google ADK 和 Cloud Run。#AllThingsAgenticHackathon #Python #AIAgent #DataQuality
```

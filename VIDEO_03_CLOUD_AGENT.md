# 短视频 03：把 SignalSweep 接上 Cloud Run Gemini Agent（约 60–90 秒）

## 视频目标

证明 SignalSweep 不只是本地脚本：它已经在 Google Cloud 上部署了私有
Cloud Run Agent，并能从本地页面发起一次真实的 Gemini + ADK 调用。

## 拍摄前准备

```bash
cd "/Users/Admin/Documents/ChatGPT/项目/signalsweep"
source .venv/bin/activate
gcloud auth login
streamlit run app.py
```

准备 `sample_data/orders.csv`，并确认 Streamlit 侧栏的“同时调用云端 Gemini
Agent”开关可以看到。录屏时不要展示邮箱、令牌、兑换码或完整项目 ID。

## 口播稿

> 前面我先用 Python 做了一个确定性的数据质量工作流。现在我把它接到
> Google Cloud 上的 Gemini Agent。
>
> 这是一个私有的 Cloud Run 服务，使用 Google ADK 暴露 Agent 接口。页面
> 默认仍然先执行本地工具；打开这个开关后，上传的 CSV 会额外发送给云端
> Agent。
>
> Agent 必须调用 `taskmaster_workflow_tool`，而不是只返回一段泛泛的建议。
> 运行后，我可以同时看到本地的质量检查结果，以及云端 Agent 的模型、工具
> 调用和摘要。
>
> 这样做的好处是：数据检查可重复、结果可追踪，Gemini 负责 Agent 层的
> 编排和解释；云端暂时不可用时，本地演示也不会中断。

## 镜头表

| 时间 | 画面 | 屏幕文字 |
|---|---|---|
| 0–8 秒 | 项目首页和 `orders.csv` | SignalSweep：可追踪的数据质量 Agent |
| 8–20 秒 | Streamlit 侧栏打开云端开关 | Optional Cloud Gemini Agent |
| 20–35 秒 | 上传 CSV，点击运行 | Local tools + Cloud Run Agent |
| 35–50 秒 | 展示质量问题、异常和 action route | Profile → Check → Detect → Route |
| 50–65 秒 | 展示 Cloud Gemini Agent 摘要 | `taskmaster_workflow_tool` 已调用 |
| 65–80 秒 | 打开 Cloud Run 服务页 | Ready · private · max 1 instance |
| 80–90 秒 | 回到完整报告和下载按钮 | Traceable, conservative, human-reviewable |

## 最关键的录屏证据

- Streamlit 页面成功完成一次运行
- Cloud Gemini Agent 区域显示模型和 `taskmaster_workflow_tool`
- Cloud Run 控制台显示 `signalsweep-agent` 为 Ready
- 结尾展示报告和 `cleaned.csv` 下载按钮

## 发布文案

```text
SignalSweep 现在已经接上 Google Cloud 上的私有 Gemini Agent。
本地 Python 工具负责可重复的数据质量检查，Cloud Run + ADK 负责 Agent 编排和解释；
云端不可用时，本地演示仍然可以继续。#AllThingsAgenticHackathon #GoogleCloud #Python #AIAgent
```

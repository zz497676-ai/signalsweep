# SignalSweep 会话交接记录

日期：2026-08-26

## 项目背景

- 比赛：Google All Things Agentic Hackathon
- 参赛赛道：Taskmaster
- 参赛方式：单人
- 技术栈：Python，后续接入 Google ADK / Gemini / Cloud Run
- 项目名称：SignalSweep
- 项目目标：上传一份混乱 CSV，由 Agent 规划数据质量工作流，执行检查、异常检测、动作路由、报告生成和安全导出。

## 当前已经完成

### 本地 Python 工作流

- CSV 结构分析和数据概览
- 缺失值、重复行、低信号列检查
- 可解释的数值异常检测
- Taskmaster 动作路由
- 生成保守的 normalized CSV
- 生成 Markdown 质量报告
- 输出 append-only workflow trace
- 发现重要问题时暂停到人工审核，不自动修改业务值

### HTTP 服务

- `GET /healthz`
- `POST /run`
- `GET /jobs/{event_id}`
- `POST /review`
- `event_id` 支持幂等重试
- 同一个 `event_id` 如果对应不同输入，会返回冲突，而不是错误复用结果
- 审核完成后只保留输入指纹，不保留原始 CSV

### Streamlit 页面

- 上传 CSV 并运行 Agent Workflow
- 页面会在当前会话保存运行结果和 `event_id`
- `needs_review` 状态会显示人工审核区域
- 支持填写审核说明
- 支持批准或拒绝本次运行
- 可以选择批准删除完全重复行
- 审核后的结果、报告和下载文件会同步更新

## 关键文件

- `app.py`：Streamlit 演示页面
- `src/signalsweep/pipeline.py`：核心数据工作流
- `src/signalsweep/service.py`：HTTP 服务、幂等、审核逻辑
- `src/signalsweep/agent.py`：Google ADK Agent 接口
- `src/signalsweep/cli.py`：命令行入口
- `sample_data/orders.csv`：演示数据
- `tests/`：测试
- `README.md`：运行和部署说明

## 验证结果

- `python3 -m compileall -q src tests app.py`：通过
- 基础 Python 环境：19 项测试通过，1 项因未安装 ADK 跳过
- ADK 虚拟环境：19 项测试全部通过
- Docker 镜像构建和 HTTP smoke test 已通过
- 用户已反馈本地 SignalSweep 成功启动

## Cloud Run 部署状态

- Google Cloud 项目：用于本次比赛的 Cloud 项目（项目 ID 不在公开记录中保留）
- Billing：已启用，免费试用额度截图显示剩余 `$300`
- 区域：`us-central1`
- 服务名：`signalsweep-agent`
- 服务 URL：<https://signalsweep-agent-5omgubz3cq-uc.a.run.app>
- 当前状态：Cloud Run `Ready`，最新 revision 承载 100% 流量
- 访问策略：未开启匿名访问，需要 Google Cloud 登录权限
- 运行服务账号：专用运行服务账号（邮箱不在公开记录中保留）
- Gemini 模型：`gemini-3.5-flash`
- Gemini location：`global`
- Cloud Run 已切换到本地 Streamlit 可选调用：默认 URL 已写入客户端，也可用
  `SIGNALSWEEP_AGENT_URL` 覆盖
- ADK `/health`：返回 `{"status":"ok"}`
- ADK `/list-apps`：返回 `["signalsweep"]`
- ADK 会话创建：已通过
- Gemini Agent 调用：已通过，返回 `SignalSweep online`

## 2026-08-27 额度与成本保护

- 黑客松 `$150` Google Cloud credits 已成功兑换并显示为可用，余额 100%。
- Billing 页面当前总费用为 `$0.00`；控制台显示该赠金约 29 天后到期，应以赠金详情页的准确日期为准。
- Cloud Run 服务级别自动缩放已设置为：最小 0 个实例、最大 1 个实例。
- 已用认证请求复查 `/health`，返回 `{"status":"ok"}`。
- 额度截图建议保存在本地，录视频时不要展示兑换码、邮箱、令牌或完整项目 ID。

## 本地页面连接云端

- 新增 `src/signalsweep/cloud_agent.py`
- 页面侧栏新增“同时调用云端 Gemini Agent”开关
- 使用本机 `gcloud auth print-identity-token` 获取短期身份令牌，不写入文件
- 用户账号不支持 `--audiences` 时，客户端会自动回退到普通身份令牌
- 云端调用失败时保留本地确定性结果，不影响演示
- 新增 `tests/test_cloud_agent.py`，覆盖会话创建、令牌回退、请求体和脱敏 trace 摘要

最近一次真实端到端联调已通过：本地客户端成功创建 ADK 会话，Cloud Run 返回
`gemini-3.5-flash`，并调用 `taskmaster_workflow_tool` 处理示例 CSV。

部署过程中已为构建服务账号补充最小权限：临时源码桶对象读取权限，以及
`cloud-run-source-deploy` 仓库的 Artifact Registry 写入权限。

部署脚本已补充启用 `aiplatform.googleapis.com`、使用专用运行服务账号，
并将 Gemini 请求位置设为 `global`。

## 用户下一步操作

在已经启动的 Streamlit 页面中：

1. 在终端进入项目目录并登录：`gcloud auth login`
2. 启动页面：`streamlit run app.py`
3. 上传 `sample_data/orders.csv`
4. 如需真实调用云端，在侧栏勾选 **同时调用云端 Gemini Agent**
5. 点击 **Run Agent Workflow**
6. 查看本地结果和 Cloud Gemini Agent 摘要
7. 如果状态是 `needs_review`，填写审核说明并批准或拒绝
8. 下载 `cleaned.csv` 和 `report.md`

## 下一个对话建议从这里开始

优先做黑客松演示闭环：

1. 确认页面的本地结果和云端 Agent 摘要，并记录一张演示截图
2. 优化首页文案和演示流程
3. 准备 90 秒产品演示脚本
4. 准备 3 分钟技术讲解和架构图
5. 为黑客松提交准备 README、演示视频和部署说明

当前仍以本地、可复现的 Python 工作流作为事实来源；Cloud Run Agent 是可选的 Gemini
展示层，云端不可用时不会阻断本地演示。

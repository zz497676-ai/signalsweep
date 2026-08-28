# SignalSweep

SignalSweep is a solo Python project for the **Taskmaster** track of the Google
All Things Agentic Hackathon. It turns a messy CSV into a traceable
data-quality workflow: profile the file, check quality, detect anomalies, route
the next action, create a report, and export a conservative normalized copy.

The core workflow is deliberately local and deterministic: the Python tools do
the real work and remain the source of truth. An optional Gemini + ADK layer is
deployed on a private Cloud Run service for the competition demo, but the app
still works locally when cloud credentials are unavailable.

## Local setup

```bash
cd signalsweep
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
streamlit run app.py
```

Then upload `sample_data/orders.csv` and click **Run Agent Workflow**. The page
keeps the result in the current session; if the workflow pauses, you can enter
an audit note and approve or reject it directly in the UI. Removing exact
duplicate rows is the only optional automatic action exposed by the review
control.

要让页面同时调用已部署的私有 Cloud Run Agent，先确认本机已登录 gcloud：

```bash
gcloud auth login
```

然后在页面侧栏勾选 **同时调用云端 Gemini Agent**。默认 URL 指向当前部署的
服务，也可以通过 `SIGNALSWEEP_AGENT_URL` 覆盖。云端调用失败时，本地确定性
工作流仍会正常显示；上传的 CSV 只有在勾选该选项后才会发送到 Cloud Run。

For a dependency-light smoke test:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m signalsweep.cli sample_data/orders.csv --output-dir .artifacts --show-trace
```

The CLI writes three artifacts: `cleaned.csv`, `report.md`, and `run.json`.
The JSON file contains the structured Taskmaster action decisions and append-only
workflow trace, ready to be stored in Firestore in the next milestone.

## Event-driven Python service

Run the dependency-light HTTP entry point locally:

```bash
PYTHONPATH=src python -m signalsweep.service
```

Check health:

```bash
curl http://localhost:8080/healthz
```

Trigger a workflow with a JSON event:

```bash
curl -X POST http://localhost:8080/run \
  -H 'Content-Type: application/json' \
  --data '{"event_id":"demo-001","dataset_name":"orders.csv","csv_text":"date,amount\n2026-08-01,10\n2026-08-02,12\n"}'
```

`POST /run` returns the same structured result as the CLI: workflow status,
action decisions, event trace, report, and normalized CSV. The service does not
silently repair business values; material findings pause at human review.

异步触发方可以用 `event_id` 查询最新结果：

```bash
curl http://localhost:8080/jobs/demo-001
```

If the response is `needs_review` and an `event_id` was supplied, resume the
workflow with an explicit decision:

```bash
curl -X POST http://localhost:8080/review \
  -H 'Content-Type: application/json' \
  --data '{"event_id":"demo-001","decision":"approve_normalized_copy","approved_actions":["remove_exact_duplicates"],"note":"已人工检查，批准去除完全重复行。"}'
```

Supported decisions are `approve_normalized_copy` and `reject_run`. The local
service keeps these jobs in memory for now. The only automatic repair available
after approval is `remove_exact_duplicates`; missing values and anomalies still
require an explicit business decision. The same response shape can move to
Firestore when the Cloud Run deployment is added.

For restart-safe local testing, use the SQLite backend:

```bash
SIGNALSWEEP_STATE_BACKEND=sqlite \
SIGNALSWEEP_STATE_PATH=.artifacts/jobs.sqlite3 \
PYTHONPATH=src python -m signalsweep.service
```

The service stores the paused run and removes the original CSV input after the
review is completed. A supplied `event_id` is an idempotency key: replaying the
same request returns the stored result without running the workflow again, while
reusing the ID for different CSV content returns a conflict. After review, the
service keeps only a non-reversible request fingerprint, not the original CSV.
Cloud Run should use a managed state backend for durable cross-instance state;
the `JobStore` interface keeps that migration isolated.

## Cloud Run container

The repository includes a minimal `Dockerfile` for the dependency-light HTTP
service. Build and deploy it from the `signalsweep` directory:

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/signalsweep
gcloud run deploy signalsweep \
  --image gcr.io/PROJECT_ID/signalsweep \
  --region REGION \
  --port 8080
```

After deployment, use the service URL with the same `/healthz`, `/run`, and
`/review` endpoints. Keep authentication enabled while developing; only make
the service public when the demo URL and uploaded data are safe to expose.

## ADK agent runtime

The `src/signalsweep` package also contains an ADK-compatible `root_agent` and
the `taskmaster_workflow_tool`. After installing the ADK dependency, run the
development UI from the directory that contains the package:

```bash
cd src
pip install -r signalsweep/requirements.txt
adk web --trigger_sources=pubsub,eventarc signalsweep
```

本地只想调试聊天界面时，也可以省略 `--trigger_sources`。启用触发源后，
ADK 会为事件驱动调用注册对应的 trigger endpoints，正好对应 Taskmaster
赛道的“事件到达后自动执行工作流”场景。

For the competition deployment path, use the package directory as the ADK
agent path:

```bash
cd src
adk deploy cloud_run \
  --project=PROJECT_ID \
  --region=REGION \
  --service_name=signalsweep-agent \
  signalsweep
```

或者直接运行仓库里的部署脚本。脚本会先检查 gcloud 登录、Billing 和
必需 API；Billing 未启用时会安全退出，不会开始构建：

```bash
GOOGLE_CLOUD_PROJECT=PROJECT_ID \
GOOGLE_CLOUD_LOCATION=REGION \
bash scripts/deploy_adk_cloud_run.sh
```

脚本默认使用 `signalsweep-runtime` 作为 Cloud Run 运行服务账号，并通过
Vertex AI 的 `global` location 调用 Gemini。首次部署前，需要在项目中创建
该服务账号并只授予它 `roles/aiplatform.user`；这样 Agent 可以调用 Gemini，
但不需要把项目 Owner 权限交给 Cloud Run：

```bash
gcloud iam service-accounts create signalsweep-runtime \
  --display-name="SignalSweep Cloud Run runtime"
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:signalsweep-runtime@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

Set the Gemini/Google Cloud environment variables required by your chosen
authentication method before deploying. For the current private deployment,
the Streamlit client uses the local user's `gcloud` identity and the sidebar
switch is off by default. The deterministic Python tools remain the source of
truth; the ADK layer decides when to call them and explains the resulting
trace.

For cost control during a solo demo, keep Cloud Run at zero minimum instances
and a small maximum instance count. The current service uses a service-level
maximum of one instance.

## MVP architecture

The submission-ready architecture diagram is also available as
[`ARCHITECTURE.md`](ARCHITECTURE.md) and [`architecture_diagram.png`](architecture_diagram.png).

```text
Upload / event trigger
    |
    v
SignalSweep Taskmaster workflow  --->  Python data tools
    |                         - profile_dataset
    |                         - run_quality_checks
    |                         - detect_anomalies
    |                         - route_next_actions
    |                         - export_cleaned_csv
    v
Action decision + event trace ---> Firestore job state (next milestone)
    ^
    |
Gemini 3.5 Flash + Google ADK (agent hook)
```

## Hackathon fit

- **Track:** Taskmaster
- **Required model:** Gemini 3.5 or newer through Gemini API or Vertex AI
- **Agent framework:** Google ADK for Python
- **Google Cloud service:** Cloud Run first; Firestore for job state next
- **Hero workflow:** upload messy data → agent plans → tools execute → route action → report
- **Safety behavior:** material findings pause for human review; no destructive repair is automatic

## Scope guardrails

The first demo will not add authentication, multi-agent orchestration, or
external SaaS integrations. It will show one reliable workflow with visible
tool execution, failure handling, and reproducible output.

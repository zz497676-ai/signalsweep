# SignalSweep — Hackathon Submission Draft

## Project

- **Track:** Taskmaster
- **Project name:** SignalSweep
- **Team:** Solo builder
- **Primary language:** Python
- **Repository:** https://github.com/zz497676-ai/signalsweep

## One-line description

SignalSweep is a traceable data-quality agent that turns a messy CSV into evidence-backed findings, prioritized next actions, and a human-controlled review decision.

## Short description

Most data-quality tools stop at a list of errors. SignalSweep turns the full workflow into an observable agent loop. A user uploads a CSV, and the app profiles the dataset, checks quality, detects unusual values, routes the next actions, produces a normalized copy and quality report, and pauses when a business-impacting decision needs human approval.

The local Python workflow is deterministic and easy to inspect. An optional private Google Cloud layer calls a Gemini agent on Cloud Run through Google ADK. The cloud agent is required to invoke the Taskmaster workflow tool, while the local workflow remains the source of truth for the displayed result. Every step is recorded in a trace so a reviewer can see what happened and why.

## What makes it agentic

1. It receives a high-level task: make this CSV trustworthy.
2. It selects and executes a multi-step workflow instead of returning a one-shot answer.
3. It uses a Taskmaster tool to profile, check, detect, route, export, and report.
4. It chooses between execution and human review based on findings.
5. It pauses before a potentially consequential duplicate-removal action.
6. It exposes the plan, tool call, step trace, findings, and final decision.

## Google Cloud usage

- **Cloud Run:** hosts the private agent service.
- **Vertex AI / Gemini:** powers the cloud reasoning layer.
- **Google ADK:** exposes the agent and Taskmaster workflow tool.
- **Cloud Console:** provides deployment and runtime evidence for the demo.

The deployed service is private and uses authenticated requests. The demo can prove deployment with the Cloud Run console and the in-app cloud trace without requiring a public anonymous endpoint.

## Safety and human control

SignalSweep never silently changes business data. It creates a normalized copy and report, then pauses with `needs_review` when material issues are found. Removing exact duplicate rows is a separate explicit action and requires a human note and approval. If the cloud call fails, the local deterministic result is retained.

## Reproducible demo

1. Start the app from the `signalsweep` directory:

   ```bash
   source .venv/bin/activate
   streamlit run app.py
   ```

2. Open `http://localhost:8501`.
3. Upload `sample_data/orders.csv`.
4. Enable **同时调用云端 Gemini Agent**.
5. Click **Run Agent Workflow**.
6. Show the summary: 12 rows, 3 quality issues, 1 anomaly, and `needs_review`.
7. Expand **查看云端 Agent trace 摘要** and **查看完整 workflow trace**.
8. Show the Cloud Run console as deployment proof.
9. Stop at the human-review gate; do not approve an action during the core demo unless the reviewer explicitly wants to see that branch.

## 90-second video outline

- **0–10s:** Problem — CSV issues are easy to find but hard to route safely.
- **10–25s:** Upload the sample CSV and show the Taskmaster workflow.
- **25–45s:** Show the quality findings and anomaly detection.
- **45–65s:** Show the cloud Gemini trace and the `taskmaster_workflow_tool` call.
- **65–80s:** Show the action route and the human-review pause.
- **80–90s:** Show Cloud Run deployment evidence and close with the safety principle.

## Final submission checklist

- [ ] Paste the final project description into the hackathon form.
- [ ] Add the repository URL.
- [ ] Add the demo video URL.
- [ ] Include a screenshot or short screen recording of Cloud Run deployment.
- [ ] Include a screenshot showing the Gemini model/tool trace.
- [ ] Verify that no API keys, identity tokens, coupon codes, or personal account details appear in the video or repository.
- [ ] Submit before the stated deadline.

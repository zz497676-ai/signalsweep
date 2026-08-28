"""Streamlit demo for SignalSweep's local MVP."""

from __future__ import annotations

import uuid

import streamlit as st

from signalsweep.agent import root_agent
from signalsweep.cloud_agent import (
    CloudAgentClient,
    CloudAgentError,
    configured_agent_url,
    summarize_cloud_response,
)
from signalsweep.service import review_request, run_request

st.set_page_config(page_title="SignalSweep", page_icon="🧭", layout="wide")

st.title("🧭 SignalSweep")
st.caption("Taskmaster · autonomous data-quality workflow")

with st.sidebar:
    st.subheader("Agent status")
    if root_agent is None:
        st.info("Local tools are ready. Install Google ADK to enable the Gemini agent hook.")
    else:
        st.success("Google ADK agent hook loaded.")
    st.markdown("**Workflow**")
    st.markdown(
        "1. Profile\n2. Check quality\n3. Detect anomalies\n"
        "4. Route next action\n5. Export + report\n6. Review or complete"
    )

st.session_state.setdefault("workflow_result", None)
st.session_state.setdefault("workflow_event_id", None)
st.session_state.setdefault("review_note", "")
st.session_state.setdefault("approve_duplicates", False)
st.session_state.setdefault("use_cloud_agent", False)
st.session_state.setdefault("cloud_agent_url", configured_agent_url())

uploaded = st.file_uploader("上传一份 CSV", type=["csv"])

with st.sidebar:
    st.subheader("Cloud Gemini Agent")
    st.checkbox(
        "同时调用云端 Gemini Agent",
        key="use_cloud_agent",
        help="勾选后，上传的 CSV 会发送到私有 Cloud Run Agent，并消耗少量 Gemini 额度。",
    )
    st.text_input("Cloud Run URL", key="cloud_agent_url")
    st.caption("云端服务当前要求 Google Cloud 登录，匿名访问未开启。")

if uploaded is None:
    st.info("试试 sample_data/orders.csv，观察 Agent 如何完成一条完整数据工作流。")
else:
    st.caption(f"当前文件：{uploaded.name}")
    if st.button("▶ Run Agent Workflow", type="primary"):
        try:
            csv_text = uploaded.getvalue().decode("utf-8-sig")
            event_id = f"ui-{uuid.uuid4().hex}"
            with st.status("SignalSweep 正在执行工作流…", expanded=True) as status:
                st.write("Planning: 先检查结构，再执行质量检查和异常检测。")
                response = run_request(
                    {
                        "event_id": event_id,
                        "dataset_name": uploaded.name,
                        "csv_text": csv_text,
                    }
                )
                for step in response["plan"]:
                    st.write(f"✓ {step}")
                cloud_summary = None
                if st.session_state["use_cloud_agent"]:
                    st.write("Cloud Gemini: 正在调用远端 ADK Agent…")
                    try:
                        cloud_response = CloudAgentClient(
                            base_url=st.session_state["cloud_agent_url"],
                        ).run_csv(csv_text, uploaded.name)
                    except (CloudAgentError, ValueError) as exc:
                        cloud_summary = {
                            "status": "error",
                            "message": str(exc),
                        }
                        st.warning(f"云端 Agent 暂时不可用，本地结果仍然有效：{exc}")
                    else:
                        cloud_summary = summarize_cloud_response(cloud_response)
                        st.write(
                            "✓ Cloud Gemini 已返回 "
                            f"{cloud_summary['event_count']} 个 Agent 事件。"
                        )
                if cloud_summary is not None:
                    response["cloud_agent"] = cloud_summary
                status.update(label="Workflow complete", state="complete")
        except (UnicodeDecodeError, ValueError) as exc:
            st.error(f"无法处理这份 CSV：{exc}")
        else:
            st.session_state["workflow_result"] = response
            st.session_state["workflow_event_id"] = event_id
            st.session_state["review_note"] = ""
            st.session_state["approve_duplicates"] = False
            st.rerun()

result = st.session_state["workflow_result"]

if result is not None:
    profile = result["profile"]
    workflow_status = result["workflow_status"]
    dataset_name = result["dataset_name"]
    base_name = dataset_name.rsplit(".", 1)[0] if "." in dataset_name else dataset_name

    st.subheader("结果摘要")
    metric_columns = st.columns(4)
    metric_columns[0].metric("Rows", profile["row_count"])
    metric_columns[1].metric("Columns", len(profile["columns"]))
    metric_columns[2].metric("Quality issues", len(result["issues"]))
    metric_columns[3].metric("Anomalies", len(result["anomalies"]))

    if workflow_status == "needs_review":
        st.warning("Taskmaster 已暂停在人工复核节点：不会自动删除或修改业务数据。")
    elif workflow_status == "approved":
        st.success("人工审核已批准，工作流已完成。")
    elif workflow_status == "rejected":
        st.error("人工审核已拒绝本次运行。")
    else:
        st.success("Taskmaster 已完成路由：当前数据可以进入下一步处理。")

    if result.get("review"):
        review = result["review"]
        st.info(
            f"审核决定：{review['decision']}；说明：{review['note']}"
            + (
                f"；批准动作：{', '.join(review['approved_actions'])}"
                if review["approved_actions"]
                else ""
            )
        )

    if workflow_status == "needs_review":
        st.subheader("人工审核")
        st.write("请先检查上面的质量问题和异常，再明确批准或拒绝本次运行。")
        st.checkbox(
            "批准删除完全重复行（仅去除完全相同的记录）",
            key="approve_duplicates",
        )
        st.text_area("审核说明（必填）", key="review_note", height=100)
        approve_column, reject_column = st.columns(2)
        with approve_column:
            approve_clicked = st.button("批准并继续", type="primary", key="approve_review")
        with reject_column:
            reject_clicked = st.button("拒绝本次运行", key="reject_review")

        if approve_clicked or reject_clicked:
            note = st.session_state["review_note"].strip()
            if not note:
                st.error("请先填写审核说明。")
            else:
                decision = "approve_normalized_copy" if approve_clicked else "reject_run"
                approved_actions = (
                    ["remove_exact_duplicates"]
                    if approve_clicked and st.session_state["approve_duplicates"]
                    else []
                )
                try:
                    reviewed = review_request(
                        {
                            "event_id": st.session_state["workflow_event_id"],
                            "decision": decision,
                            "note": note,
                            "approved_actions": approved_actions,
                        }
                    )
                except (KeyError, ValueError) as exc:
                    st.error(f"审核操作失败：{exc}")
                else:
                    st.session_state["workflow_result"] = reviewed
                    if result.get("cloud_agent") is not None:
                        st.session_state["workflow_result"]["cloud_agent"] = result[
                            "cloud_agent"
                        ]
                    # Do not mutate widget-backed state after the review widgets
                    # have been instantiated. A later workflow run resets these
                    # values before the widgets are rendered again.
                    st.rerun()

    cloud_agent = result.get("cloud_agent")
    if cloud_agent:
        st.subheader("Cloud Gemini Agent")
        if cloud_agent["status"] == "error":
            st.warning(cloud_agent["message"])
        else:
            tool_calls = ", ".join(cloud_agent["tool_calls"]) or "未记录工具调用"
            st.success(
                f"云端 Agent 已运行：模型 {cloud_agent['model_version']}，"
                f"工具调用：{tool_calls}。"
            )
            if cloud_agent["assistant_text"]:
                st.write(cloud_agent["assistant_text"])
            with st.expander("查看云端 Agent trace 摘要"):
                st.json(
                    {
                        "model_version": cloud_agent["model_version"],
                        "event_count": cloud_agent["event_count"],
                        "tool_calls": cloud_agent["tool_calls"],
                        "tool_results": cloud_agent["tool_results"],
                    }
                )

    st.subheader("Taskmaster action route")
    st.dataframe(
        result["actions"],
        width="stretch",
        hide_index=True,
    )

    with st.expander("查看完整 workflow trace"):
        st.dataframe(
            result["events"],
            width="stretch",
            hide_index=True,
        )

    left, right = st.columns(2)
    with left:
        st.subheader("质量问题")
        if result["issues"]:
            st.dataframe(result["issues"], width="stretch", hide_index=True)
        else:
            st.success("没有发现质量问题。")
    with right:
        st.subheader("潜在异常")
        if result["anomalies"]:
            st.dataframe(result["anomalies"], width="stretch", hide_index=True)
        else:
            st.success("没有发现可解释的数值异常。")

    with st.expander("查看数据概览"):
        st.write(f"数值列：{', '.join(profile['numeric_columns']) or '无'}")
        st.write(f"重复行：{profile['duplicate_rows']}")
        st.dataframe(profile["sample_rows"], width="stretch", hide_index=True)

    st.subheader("Agent report")
    st.markdown(result["report_markdown"])
    st.download_button(
        "下载 cleaned.csv",
        data=result["cleaned_csv"],
        file_name=f"{base_name}_cleaned.csv",
        mime="text/csv",
    )
    st.download_button(
        "下载 report.md",
        data=result["report_markdown"],
        file_name=f"{base_name}_report.md",
        mime="text/markdown",
    )

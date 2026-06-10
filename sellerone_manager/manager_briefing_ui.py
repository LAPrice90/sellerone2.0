from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from .manager_briefing import ManagerCard, build_manager_briefing
except ImportError:  # Streamlit may run this file as a script.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from sellerone_manager.manager_briefing import ManagerCard, build_manager_briefing


STATUS_COLOURS = {
    "calm": "#15803d",
    "warning": "#b45309",
    "blocked": "#dc2626",
    "parked": "#6b7280",
    "working": "#2563eb",
    "waiting proof": "#7c3aed",
    "not started": "#64748b",
}


def _escape(value: object) -> str:
    return html.escape(str(value or "").strip())


def _briefing_css() -> str:
    return """
<style>
html, body, .stApp, [data-testid="stAppViewContainer"] {
  background: #f7fafc !important;
  color: #172033 !important;
}
[data-testid="stHeader"] {
  background: rgba(247, 250, 252, 0.88) !important;
  backdrop-filter: blur(10px);
}
[data-testid="stSidebar"], [data-testid="stSidebarContent"] {
  background: #ffffff !important;
  color: #172033 !important;
}
.block-container {
  max-width: 1420px;
  padding-top: 2rem;
  padding-bottom: 3rem;
}
.mb-hero {
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  padding: 20px 22px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
  margin-bottom: 16px;
}
.mb-eyebrow {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.mb-title {
  font-size: 32px;
  line-height: 1.1;
  font-weight: 820;
  color: #0f172a;
  margin: 0 0 8px 0;
}
.mb-subtitle {
  color: #475569;
  font-size: 15px;
  max-width: 980px;
  margin: 0;
}
.mb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 14px;
  margin: 18px 0;
}
.mb-card {
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #ffffff;
  padding: 14px;
  box-shadow: 0 2px 9px rgba(15, 23, 42, 0.05);
  min-height: 185px;
}
.mb-card-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}
.mb-flow {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-weight: 850;
  font-size: 16px;
}
.mb-status {
  border-radius: 999px;
  color: #ffffff;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  padding: 7px 9px;
  white-space: nowrap;
}
.mb-role {
  color: #64748b;
  font-size: 12px;
  font-weight: 720;
  margin-top: 10px;
}
.mb-progress-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 11px 0 10px 0;
}
.mb-progress-shell {
  background: #e5eaf1;
  height: 12px;
  border-radius: 999px;
  overflow: hidden;
  flex: 1 1 auto;
}
.mb-progress-fill {
  height: 12px;
  border-radius: 999px;
}
.mb-progress-number {
  color: #0f172a;
  font-size: 13px;
  font-weight: 820;
  width: 38px;
  text-align: right;
}
.mb-card-text {
  color: #334155;
  font-size: 13px;
  line-height: 1.35;
  margin: 0 0 10px 0;
}
.mb-job-counts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.mb-chip {
  border-radius: 999px;
  background: #eef2f7;
  color: #334155;
  font-size: 11px;
  font-weight: 750;
  padding: 6px 8px;
}
.mb-panel {
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #ffffff;
  padding: 16px;
  box-shadow: 0 2px 9px rgba(15, 23, 42, 0.05);
}
.mb-panel-title {
  color: #0f172a;
  font-size: 21px;
  font-weight: 820;
  margin: 0 0 4px 0;
}
.mb-panel-subtitle {
  color: #64748b;
  font-size: 13px;
  margin: 0 0 14px 0;
}
.mb-job {
  border-top: 1px solid #e5eaf1;
  padding: 11px 0;
}
.mb-job:first-of-type {
  border-top: 0;
}
.mb-job-title {
  color: #172033;
  font-size: 14px;
  font-weight: 780;
  margin: 0 0 5px 0;
}
.mb-job-meta {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 5px;
}
.mb-alert {
  border-left: 4px solid #dc2626;
  background: #fff7f7;
  color: #7f1d1d;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 13px;
  margin-bottom: 12px;
}
@media (max-width: 700px) {
  .mb-title { font-size: 25px; }
  .mb-grid { grid-template-columns: 1fr; }
}
</style>
"""


def _status_colour(status: str) -> str:
    return STATUS_COLOURS.get(status, "#64748b")


def _card_html(manager: ManagerCard) -> str:
    status_colour = _status_colour(manager.status)
    progress = max(0, min(100, int(manager.progress_pct)))
    return f"""
<div class="mb-card">
  <div class="mb-card-head">
    <div class="mb-flow" style="background:{_escape(manager.colour)}">{_escape(manager.flow)}</div>
    <div class="mb-status" style="background:{status_colour}">{_escape(manager.status.title())}</div>
  </div>
  <div class="mb-role">{_escape(manager.subtitle)}</div>
  <div class="mb-progress-row">
    <div class="mb-progress-shell"><div class="mb-progress-fill" style="width:{progress}%;background:{_escape(manager.colour)}"></div></div>
    <div class="mb-progress-number">{progress}%</div>
  </div>
  <p class="mb-card-text">{_escape(manager.current_story)}</p>
  <div class="mb-job-counts">
    <span class="mb-chip">{manager.active_job_count} active</span>
    <span class="mb-chip">{manager.blocked_job_count} blocked</span>
    <span class="mb-chip">{manager.parked_job_count} parked</span>
  </div>
</div>
"""


def _manager_panel_html(manager: ManagerCard, *, show_details: bool) -> str:
    decision = ""
    if manager.luke_action_required:
        decision = f"<div class='mb-alert'>Luke decision visible: {_escape(manager.luke_action)}</div>"
    jobs = []
    for job in manager.jobs:
        body = _escape(job.note or job.proof_required) if show_details else _escape(job.title)
        label = "Luke gate" if job.luke_action_required else job.status.replace("_", " ").title()
        jobs.append(
            f"""
<div class="mb-job">
  <div class="mb-job-title">{_escape(job.job_ref)} - {_escape(job.title)}</div>
  <div class="mb-job-meta">{_escape(label)} / {_escape(job.priority)}</div>
  <div class="mb-card-text">{body}</div>
</div>
"""
        )
    if not jobs:
        jobs.append("<div class='mb-job'><div class='mb-card-text'>No visible active jobs for this manager.</div></div>")
    return f"""
<div class="mb-panel">
  <div class="mb-panel-title">{_escape(manager.flow)} - {_escape(manager.subtitle)}</div>
  <p class="mb-panel-subtitle">Next move: {_escape(manager.next_move)}</p>
  {decision}
  {''.join(jobs)}
</div>
"""


def render_manager_briefing_ui(root: Path | None = None) -> None:
    import streamlit as st

    st.set_page_config(page_title="SellerOne Manager Briefing", layout="wide")
    st.markdown(_briefing_css(), unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### Briefing controls")
        include_proved = st.checkbox("Show proved history", value=False)
        show_details = st.checkbox("Show technical details", value=False)
        selected_flow = st.selectbox("Manager", ["Overview", "A", "B", "E", "H", "F", "O", "M"], index=0)

    briefing = build_manager_briefing(root=root, include_proved_history=include_proved)
    st.markdown(
        f"""
<div class="mb-hero">
  <div class="mb-eyebrow">Private Luke briefing / {_escape(briefing.observed_utc)}</div>
  <h1 class="mb-title">Today&apos;s Control Brief</h1>
  <p class="mb-subtitle">{_escape(briefing.restocking_summary)}</p>
</div>
""",
        unsafe_allow_html=True,
    )

    st.progress(briefing.restocking_readiness_pct / 100, text=f"Restocking readiness: {briefing.restocking_readiness_pct}%")

    if selected_flow == "Overview":
        cards_html = "".join(_card_html(manager) for manager in briefing.managers)
        st.markdown(f"<div class='mb-grid'>{cards_html}</div>", unsafe_allow_html=True)
    else:
        selected = next(manager for manager in briefing.managers if manager.flow == selected_flow)
        st.markdown(_card_html(selected), unsafe_allow_html=True)
        st.markdown(_manager_panel_html(selected, show_details=show_details), unsafe_allow_html=True)


if __name__ == "__main__":
    render_manager_briefing_ui()

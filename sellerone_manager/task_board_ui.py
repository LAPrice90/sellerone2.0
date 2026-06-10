from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from .task_board import FLOW_COLOURS, FLOW_ORDER, TaskCard, lane_names, load_task_board, status_options
except ImportError:  # Streamlit runs this file as a script.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from sellerone_manager.task_board import FLOW_COLOURS, FLOW_ORDER, TaskCard, lane_names, load_task_board, status_options



def _escape(value: object) -> str:
    return html.escape(str(value or "").strip())


def _task_board_css() -> str:
    return """
<style>
html, body, .stApp, [data-testid="stAppViewContainer"] {
  background: #f8fbff !important;
  color: #202124 !important;
}
html {
  overflow-y: hidden !important;
}
body {
  overflow-y: hidden !important;
}
[data-testid="stAppViewContainer"] {
  overflow: hidden !important;
}
[data-testid="stMain"],
section.main {
  overflow-y: scroll !important;
  scrollbar-gutter: stable;
  scrollbar-width: auto;
  scrollbar-color: #1a73e8 #dbe8ff;
}
*::-webkit-scrollbar {
  width: 16px;
  height: 16px;
}
*::-webkit-scrollbar-track {
  background: #dbe8ff;
  border-left: 1px solid #c7d8f6;
}
*::-webkit-scrollbar-thumb {
  background: #1a73e8;
  border: 3px solid #dbe8ff;
  border-radius: 999px;
}
*::-webkit-scrollbar-thumb:hover {
  background: #1557b0;
}
[data-testid="stHeader"] {
  background: rgba(248, 251, 255, 0.88) !important;
  backdrop-filter: blur(10px);
}
[data-testid="stSidebar"], [data-testid="stSidebarContent"] {
  background: #ffffff !important;
  color: #202124 !important;
}
[data-testid="stSidebar"] * {
  color: #202124 !important;
}
div[data-baseweb="select"] > div {
  background: #ffffff !important;
  border-color: #dfe6f3 !important;
  border-radius: 8px !important;
  box-shadow: 0 1px 2px rgba(60, 64, 67, 0.08);
}
div[data-baseweb="select"],
div[data-baseweb="select"] div,
div[data-baseweb="select"] input {
  background-color: #ffffff !important;
  color: #202124 !important;
}
div[data-baseweb="select"] input::placeholder {
  color: #5f6368 !important;
  opacity: 1 !important;
}
div[data-baseweb="select"] svg {
  color: #5f6368 !important;
  fill: #5f6368 !important;
}
div[data-baseweb="popover"],
div[data-baseweb="menu"],
div[role="listbox"],
ul[role="listbox"] {
  background: #ffffff !important;
  color: #202124 !important;
  border: 1px solid #dfe6f3 !important;
  border-radius: 8px !important;
  box-shadow: 0 8px 24px rgba(60, 64, 67, 0.14) !important;
}
div[data-baseweb="option"],
li[role="option"],
div[role="option"] {
  background: #ffffff !important;
  color: #202124 !important;
}
div[data-baseweb="option"] *,
li[role="option"] *,
div[role="option"] * {
  background: transparent !important;
  color: #202124 !important;
}
div[data-baseweb="option"]:hover,
li[role="option"]:hover,
div[role="option"]:hover,
div[aria-selected="true"] {
  background: #eef3fe !important;
}
span[data-baseweb="tag"] {
  background: #eef3fe !important;
  color: #174ea6 !important;
}
label[data-baseweb="checkbox"] > span:first-child {
  background: #ffffff !important;
  border: 1px solid #dadce0 !important;
  border-radius: 4px !important;
}
label[data-baseweb="checkbox"]:has(input[aria-checked="true"]) > span:first-child {
  background: #1a73e8 !important;
  border-color: #1a73e8 !important;
}
.tb-search-form {
  margin: 0 0 16px 0;
  padding: 10px;
  border: 1px solid #e7eefb;
  border-radius: 8px;
  background: #f8fbff;
}
.tb-search-form label {
  display: block;
  font-size: 12px;
  font-weight: 720;
  color: #5f6368 !important;
  margin: 0 0 6px 0;
}
.tb-search-row {
  display: flex;
  gap: 6px;
  align-items: center;
}
.tb-search-row input[type="search"] {
  -webkit-appearance: none;
  appearance: none;
  color-scheme: light;
  min-width: 0;
  flex: 1 1 auto;
  border: 1px solid #dfe6f3 !important;
  border-radius: 8px;
  background: #ffffff !important;
  color: #3c4043 !important;
  caret-color: #1a73e8;
  font-size: 13px;
  padding: 8px 10px;
  outline: none;
  box-shadow: 0 1px 2px rgba(60, 64, 67, 0.06);
}
.tb-search-row input[type="search"]::-webkit-search-decoration,
.tb-search-row input[type="search"]::-webkit-search-cancel-button,
.tb-search-row input[type="search"]::-webkit-search-results-button,
.tb-search-row input[type="search"]::-webkit-search-results-decoration {
  -webkit-appearance: none;
}
.tb-search-row input[type="search"]:focus {
  border-color: #1a73e8 !important;
  box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.14);
}
.tb-search-row button {
  border: 1px solid #d2e3fc;
  border-radius: 8px;
  background: #e8f0fe;
  color: #174ea6 !important;
  font-size: 13px;
  font-weight: 740;
  padding: 8px 10px;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(60, 64, 67, 0.06);
}
.tb-search-row button:hover {
  background: #d2e3fc;
}
.tb-search-clear {
  display: inline-block;
  color: #1a73e8 !important;
  font-size: 12px;
  font-weight: 700;
  margin-top: 6px;
  text-decoration: none;
}
.block-container {
  max-width: 1480px;
  padding-top: 2.25rem;
  padding-bottom: 3rem;
}
.tb-page {
  color: #202124;
}
.tb-hero {
  border: 1px solid #dfe6f3;
  border-radius: 8px;
  padding: 18px 20px;
  background: linear-gradient(90deg, #ffffff 0%, #f5f9ff 56%, #fff8e8 100%);
  box-shadow: 0 1px 2px rgba(60, 64, 67, 0.08);
  margin-bottom: 16px;
}
.tb-shell-title {
  font-size: 30px;
  line-height: 1.15;
  font-weight: 760;
  color: #202124;
  margin: 0 0 5px 0;
}
.tb-shell-subtitle {
  color: #5f6368;
  font-size: 14px;
  margin: 0;
}
.tb-metric-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 12px;
  margin: 14px 0 18px 0;
}
.tb-metric {
  border: 1px solid #dfe6f3;
  border-radius: 8px;
  padding: 12px 14px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(60, 64, 67, 0.08);
}
.tb-metric-label {
  color: #5f6368;
  font-size: 12px;
  font-weight: 650;
}
.tb-metric-value {
  color: #202124;
  font-size: 24px;
  font-weight: 760;
  margin-top: 4px;
}
.tb-board-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
  align-items: start;
}
.tb-lane {
  border: 1px solid #dfe6f3;
  border-radius: 8px;
  background: #ffffff;
  min-height: 220px;
  box-shadow: 0 1px 2px rgba(60, 64, 67, 0.08);
  overflow: hidden;
}
.tb-lane-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 12px 10px 12px;
  border-bottom: 1px solid #edf2fb;
  background: #fbfdff;
}
.tb-lane-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #202124;
  font-size: 14px;
  font-weight: 760;
}
.tb-lane-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  flex: 0 0 auto;
}
.tb-lane-count {
  color: #5f6368;
  background: #eef3fe;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 700;
}
.tb-lane-body {
  padding: 10px;
}
.tb-card {
  position: relative;
  border: 1px solid #e4e9f2;
  border-left: 5px solid var(--flow-colour, #5f6368);
  border-radius: 8px;
  background: #ffffff;
  padding: 12px;
  margin: 0 0 10px 0;
  box-shadow: 0 1px 2px rgba(60, 64, 67, 0.08);
}
.tb-card:last-child {
  margin-bottom: 0;
}
.tb-card-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}
.tb-flow-badge {
  width: 30px;
  height: 30px;
  border-radius: 999px;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 13px;
  flex: 0 0 auto;
}
.tb-priority {
  color: #5f6368;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}
.tb-job-ref {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  border-radius: 999px;
  background: #e8f0fe;
  color: #174ea6;
  font-size: 12px;
  font-weight: 820;
  letter-spacing: 0;
  padding: 5px 9px;
  margin: 0 0 8px 0;
  overflow-wrap: anywhere;
}
.tb-card-title {
  color: #202124;
  font-size: 15px;
  font-weight: 760;
  line-height: 1.3;
  margin: 0 0 8px 0;
  overflow-wrap: anywhere;
}
.tb-card-note {
  color: #3c4043;
  font-size: 12px;
  line-height: 1.42;
  margin: 0 0 9px 0;
}
.tb-proof-line {
  border-radius: 8px;
  background: #f8fbff;
  border: 1px solid #e7eefb;
  padding: 8px;
  color: #3c4043;
  font-size: 12px;
  line-height: 1.35;
  margin: 9px 0;
}
.tb-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.tb-chip {
  border-radius: 999px;
  padding: 4px 8px;
  background: #eef3fe;
  color: #174ea6;
  font-size: 11px;
  font-weight: 700;
}
.tb-chip-warn {
  background: #fef7e0;
  color: #b06000;
}
.tb-chip-block {
  background: #fce8e6;
  color: #b3261e;
}
.tb-chip-safe {
  background: #e6f4ea;
  color: #137333;
}
.tb-empty {
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  padding: 18px 12px;
  color: #5f6368;
  background: #fbfdff;
  font-size: 13px;
  line-height: 1.4;
}
.tb-luke-strip {
  border: 1px solid #f4c7c3;
  border-radius: 8px;
  background: #fce8e6;
  padding: 11px 13px;
  margin: -4px 0 16px 0;
  color: #3c4043;
  font-size: 13px;
  line-height: 1.4;
}
.tb-luke-strip strong {
  color: #b3261e;
}
.tb-luke-ref {
  display: inline-flex;
  border-radius: 999px;
  background: #ffffff;
  color: #b3261e;
  font-weight: 780;
  padding: 3px 8px;
  margin: 2px 4px 2px 0;
}
.tb-details {
  margin-top: 10px;
  border-top: 1px solid #edf2fb;
  padding-top: 8px;
}
.tb-details summary {
  color: #1a73e8;
  cursor: pointer;
  font-size: 12px;
  font-weight: 750;
}
.tb-detail-row {
  color: #3c4043;
  font-size: 12px;
  line-height: 1.38;
  margin-top: 7px;
}
.tb-detail-label {
  color: #5f6368;
  font-weight: 760;
}
@media (max-width: 900px) {
  .block-container { padding-left: 1rem; padding-right: 1rem; }
  .tb-metric-row { grid-template-columns: repeat(2, minmax(130px, 1fr)); }
  .tb-board-grid { grid-template-columns: 1fr; }
  .tb-shell-title { font-size: 25px; }
}
</style>
"""


LANE_ACCENTS = {
    "Not Started": "#9aa0a6",
    "In Progress": "#1a73e8",
    "Waiting Proof": "#fbbc04",
    "Proof Failed": "#ea4335",
    "Blocked": "#a142f4",
    "Parked": "#00a389",
    "Proven": "#34a853",
}


def _humanise(value: object) -> str:
    text = str(value or "").strip()
    text = text.replace("`", "")
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\bpython\s+m\s+sellerone\s+manager\.app\s+hourly\s+mot\s+mot\s+flow\s+([A-Z])\b", r"\1 MOT", text)
    text = re.sub(r"\bpython\s+-m\s+sellerone_manager\.app\s+--hourly-mot\s+--mot-flow\s+([A-Z])\b", r"\1 MOT", text)
    text = re.sub(
        r"\b([A-Z])\s+MOT:\s+\1\s+",
        lambda match: f"{match.group(1).upper()} MOT: ",
        text,
        flags=re.IGNORECASE,
    )
    text = " ".join(text.split())
    replacements = {
        "MOT": "MOT",
        "FPM": "FPM",
        "BBP": "BBP",
        "API": "API",
        "ROI": "ROI",
        "SKU": "SKU",
        "DB": "DB",
        "PO": "PO",
    }
    words = []
    for word in text.split(" "):
        upper = word.upper().strip(":")
        if upper in replacements:
            suffix = ":" if word.endswith(":") else ""
            words.append(replacements[upper] + suffix)
        else:
            words.append(word)
    return " ".join(words)


def _display_title(value: object) -> str:
    text = _humanise(value)
    text = re.sub(
        r"\b([A-Z]) MOT:\s+\1\s+",
        lambda match: f"{match.group(1).upper()} MOT: ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bneeds Luke decision\b", "needs Luke decision", text, flags=re.IGNORECASE)
    text = re.sub(r"\bneeds repair\b", "needs repair", text, flags=re.IGNORECASE)
    return text


def _proof_summary(card: TaskCard) -> str:
    proof = _humanise(card.proof_required)
    if not proof and card.retest_command:
        proof = f"Retest with {_humanise(card.retest_command)}."
    if card.flow:
        proof = re.sub(rf"\bconfirm\s+{re.escape(card.flow)}\s+", "confirm ", proof, flags=re.IGNORECASE)
    if "Retest with" in proof and "confirm" in proof:
        proof = proof.replace("Retest with", "Retest using")
    return proof or "Proof path not recorded yet."


def _shorten(value: object, limit: int) -> str:
    text = _humanise(value)
    if len(text) <= limit:
        return text
    clipped = text[: max(0, limit - 3)].rsplit(" ", 1)[0].strip()
    return f"{clipped}..." if clipped else text[:limit]


def _detail_row(label: str, value: object) -> str:
    text = _escape(_humanise(value) or "Not recorded")
    return f"<div class='tb-detail-row'><span class='tb-detail-label'>{_escape(label)}:</span> {text}</div>"


def _query_param_text(value: object) -> str:
    if isinstance(value, list):
        return str(value[0] if value else "").strip()
    return str(value or "").strip()


def _search_form_html(search_text: str) -> str:
    clear_link = "<a class='tb-search-clear' href='/'>Clear search</a>" if search_text else ""
    return f"""
<form class="tb-search-form" method="get" action="/">
  <label for="tb-search-input">Search job ref, title, task id, flow, or notes</label>
  <div class="tb-search-row">
    <input id="tb-search-input" name="search" type="search" value="{_escape(search_text)}" placeholder="F-EMAIL-SOURCE" />
    <button type="submit">Search</button>
  </div>
  {clear_link}
</form>
"""


def _raw_detail_row(label: str, value: object) -> str:
    text = _escape(str(value or "").strip() or "Not recorded")
    return f"<div class='tb-detail-row'><span class='tb-detail-label'>{_escape(label)}:</span> {text}</div>"


def _card_html(card: TaskCard) -> str:
    colour = FLOW_COLOURS.get(card.flow, FLOW_COLOURS["M"])
    if card.luke_action_required:
        protected_class = "tb-chip-block"
    elif card.protected_label == "Safe Codex task":
        protected_class = "tb-chip-safe"
    else:
        protected_class = "tb-chip-warn"
    note = _shorten(card.notes or card.proof_required or "No short note recorded yet.", 210)
    proof = _shorten(_proof_summary(card), 170)
    status = _humanise(card.status)
    priority = _humanise(card.priority or "normal")
    return f"""
<div class="tb-card" style="--flow-colour:{_escape(colour)}">
  <div class="tb-card-topline">
    <div class="tb-flow-badge" style="background:{_escape(colour)}">{_escape(card.flow)}</div>
    <div class="tb-priority">{_escape(priority)}</div>
  </div>
  <div class="tb-job-ref">Job ref: {_escape(card.job_ref or card.task_id)}</div>
  <div class="tb-card-title">{_escape(_display_title(card.title))}</div>
  <div class="tb-card-note">{_escape(note)}</div>
  <div class="tb-proof-line"><strong>Proof:</strong> {_escape(proof)}</div>
  <div class="tb-chip-row">
    <span class="tb-chip">{_escape(status)}</span>
    <span class="tb-chip {protected_class}">{_escape(card.protected_label)}</span>
  </div>
  <details class="tb-details">
    <summary>Open job details</summary>
    {_raw_detail_row("Task id", card.task_id)}
    {_detail_row("Retest", card.retest_command)}
    {_detail_row("Allowed", card.allowed_scope)}
    {_detail_row("Forbidden", card.forbidden_actions)}
    {_detail_row("Packet", card.packet_path)}
  </details>
</div>
"""


def _metric_html(label: str, value: int) -> str:
    return f"""
<div class="tb-metric">
  <div class="tb-metric-label">{_escape(label)}</div>
  <div class="tb-metric-value">{value}</div>
</div>
"""


def _needs_luke_html(cards: list[TaskCard]) -> str:
    blocked = [card for card in cards if card.luke_action_required or card.status == "blocked_needs_luke"]
    if not blocked:
        return ""
    refs = " ".join(
        f"<span class='tb-luke-ref'>{_escape(card.job_ref or card.task_id)}</span>" for card in blocked[:12]
    )
    more = ""
    if len(blocked) > 12:
        more = f" and {len(blocked) - 12} more"
    return f"""
<div class="tb-luke-strip">
  <strong>Needs Luke:</strong> {refs}{_escape(more)}
</div>
"""


def _lane_html(lane: str, cards: list[TaskCard]) -> str:
    accent = LANE_ACCENTS.get(lane, "#5f6368")
    body = "\n".join(_card_html(card) for card in cards)
    if not body:
        body = "<div class='tb-empty'>Nothing in this lane.</div>"
    return f"""
<section class="tb-lane">
  <div class="tb-lane-head">
    <div class="tb-lane-title"><span class="tb-lane-dot" style="background:{_escape(accent)}"></span>{_escape(lane)}</div>
    <div class="tb-lane-count">{len(cards)}</div>
  </div>
  <div class="tb-lane-body">{body}</div>
</section>
"""


def render_task_board(root: Path | None = None) -> None:
    import streamlit as st

    root_path = root or ROOT
    st.set_page_config(page_title="Manager Task Board", layout="wide")
    st.markdown(_task_board_css(), unsafe_allow_html=True)
    st.markdown(
        """
<div class="tb-page">
  <div class="tb-hero">
    <div class="tb-shell-title">Manager Task Board</div>
    <div class="tb-shell-subtitle">Read-only coding jobs from manager-approved task packets and MOT worklist evidence.</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        search_text = _query_param_text(st.query_params.get("search", ""))
        st.markdown(_search_form_html(search_text), unsafe_allow_html=True)
        active_only = st.checkbox("Active jobs only", value=True)
        protected_only = st.checkbox("Protected gates only", value=False)
        selected_flows = st.multiselect("Cycle", FLOW_ORDER, default=[])
        selected_statuses = st.multiselect("Status", status_options(active_only=active_only), default=[])

    board = load_task_board(
        root=root_path,
        active_only=active_only,
        flows=selected_flows,
        statuses=selected_statuses,
        protected_only=protected_only,
        search=search_text,
    )
    blocked_count = board.lane_counts.get("Blocked", 0)
    waiting_count = board.lane_counts.get("Waiting Proof", 0)
    in_progress_count = board.lane_counts.get("In Progress", 0)
    parked_count = board.lane_counts.get("Parked", 0)
    st.markdown(
        "<div class='tb-page'><div class='tb-metric-row'>"
        + _metric_html("Visible jobs", board.total_cards)
        + _metric_html("In progress", in_progress_count)
        + _metric_html("Waiting proof", waiting_count)
        + _metric_html("Blocked or parked", blocked_count + parked_count)
        + "</div></div>",
        unsafe_allow_html=True,
    )

    needs_luke_html = _needs_luke_html(list(board.cards))
    if needs_luke_html:
        st.markdown(f"<div class='tb-page'>{needs_luke_html}</div>", unsafe_allow_html=True)

    cards_by_lane = {lane: [card for card in board.cards if card.lane == lane] for lane in lane_names(active_only=active_only)}
    board_html = "\n".join(_lane_html(lane, cards) for lane, cards in cards_by_lane.items())
    st.markdown(
        f"""
<div class="tb-page">
  <div class="tb-board-grid">
    {board_html}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    render_task_board()

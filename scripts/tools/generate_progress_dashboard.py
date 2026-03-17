import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONTROL = ROOT / "project_control"

TASK_LIBRARY_PATH = PROJECT_CONTROL / "TASK_LIBRARY.json"
CHECKLIST_PROGRESS_PATH = PROJECT_CONTROL / "CHECKLIST_PROGRESS.json"
SYSTEM_PROGRESS_PATH = PROJECT_CONTROL / "SYSTEM_PROGRESS.json"
CONTROL_TOWER_PATH = PROJECT_CONTROL / "SYSTEM_CONTROL_TOWER.html"


STATUS_VALUES = {
    "Not Started": 0.0,
    "Planned": 0.0,
    "In Progress": 0.5,
    "Done": 1.0,
    "Blocked": 0.25,
}

STATUS_ALIASES = {
    "Needs Stabilising": "Blocked",
    "Needs Stabilizing": "Blocked",
    "Mixed": "In Progress",
}

STATUS_ORDER = ["Done", "In Progress", "Planned", "Not Started", "Blocked"]
SPLIT_ZONE_SYSTEMS = {
    "data_intelligence": ["A_cycle", "B_cycle", "E_cycle", "H_cycle"],
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_status(raw_status: str) -> str:
    status = (raw_status or "").strip()
    status = STATUS_ALIASES.get(status, status)
    if status not in STATUS_VALUES:
        raise ValueError(f"Unsupported status: {raw_status}")
    return status


def score_items(items: List[Dict[str, Any]]) -> int:
    if not items:
        return 0
    weighted_sum = 0.0
    weight_total = 0.0
    for item in items:
        weight = float(item.get("weight", 1.0))
        weighted_sum += weight * STATUS_VALUES[item["status"]]
        weight_total += weight
    if weight_total <= 0:
        return 0
    return round(100 * weighted_sum / weight_total)


def summarize_status(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(item["status"] for item in items)
    return {
        "Done": counts.get("Done", 0),
        "In Progress": counts.get("In Progress", 0),
        "Planned": counts.get("Planned", 0),
        "Not Started": counts.get("Not Started", 0),
        "Blocked": counts.get("Blocked", 0),
    }


def infer_zone_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "Planned"
    counts = summarize_status(items)
    total = len(items)
    if counts["Done"] == total:
        return "Done"
    if counts["Blocked"] > 0 and counts["In Progress"] == 0 and counts["Done"] == 0:
        return "Blocked"
    if counts["In Progress"] > 0 or counts["Blocked"] > 0 or counts["Done"] > 0:
        return "In Progress"
    return "Planned"


def reliability_bar(label: str, score: Any) -> Dict[str, Any]:
    if label == "Provisional":
        if isinstance(score, (int, float)):
            val = max(0, min(100, int(score)))
            css = "bar-green" if val >= 81 else "bar-yellow" if val >= 61 else "bar-orange" if val >= 31 else "bar-red"
            return {"width": val, "class": css, "display": f"Provisional ({val})"}
        return {"width": 60, "class": "bar-yellow", "display": "Provisional"}
    if isinstance(score, (int, float)):
        val = max(0, min(100, int(score)))
        css = "bar-green" if val >= 81 else "bar-yellow" if val >= 61 else "bar-orange" if val >= 31 else "bar-red"
        return {"width": val, "class": css, "display": f"{val}%"}
    if label == "Mixed":
        return {"width": 45, "class": "bar-orange", "display": "Mixed"}
    return {"width": 100, "class": "bar-bluegrey", "display": label}


def completion_bar(score: int) -> str:
    if score <= 30:
        return "bar-red"
    if score <= 60:
        return "bar-orange"
    if score <= 80:
        return "bar-yellow"
    return "bar-green"


def chip_class(status: str) -> str:
    return {
        "Done": "status-done",
        "In Progress": "status-progress",
        "Planned": "status-planned",
        "Not Started": "status-planned",
        "Blocked": "status-blocked",
        "Needs Stabilising": "status-blocked",
        "Needs Stabilizing": "status-blocked",
    }.get(status, "status-planned")


def tag_class(status: str) -> str:
    return {
        "Done": "done",
        "In Progress": "inprogress",
        "Planned": "planned",
        "Not Started": "planned",
        "Blocked": "blocked",
        "Needs Stabilising": "blocked",
        "Needs Stabilizing": "blocked",
    }.get(status, "planned")


def render_progress_card(entity: Dict[str, Any], title: str, purpose: str, note: str) -> str:
    counts = entity["subsection_counts"]
    rel = entity["reliability"]
    rel_bar = reliability_bar(rel.get("label", "To Baseline"), rel.get("score"))
    comp_score = int(entity["completion_score"])
    comp_bar = completion_bar(comp_score)
    items_html = []
    for item in entity["subsections"]:
        items_html.append(
            f'<li><span class="sub-name">{item["title"]}</span>'
            f'<span class="tag {tag_class(item["status"])}">{item["status"]}</span></li>'
        )
    if rel.get("label") == "Provisional" and rel.get("score") is not None:
        rel_value = f'Provisional ({int(rel["score"])})'
    else:
        rel_value = rel.get("score") if rel.get("score") is not None else rel.get("label")
    return (
        f"""
      <article class="card">
        <div class="head">
          <div>
            <h2 class="zone-title">{title}</h2>
            <p class="purpose">{purpose}</p>
          </div>
          <span class="status-chip {chip_class(entity["status"])}">{entity["status"]}</span>
        </div>

        <div class="metrics">
          <div class="metric"><p class="label">Completion Score</p><p class="value">{comp_score}</p></div>
          <div class="metric"><p class="label">Reliability Score</p><p class="value">{rel_value}</p></div>
        </div>
        <p class="focus"><strong>Main Focus:</strong> {entity["main_focus"]}</p>

        <div class="bars">
          <div class="bar-group">
            <div class="bar-head"><span>Completion</span><span>{comp_score}%</span></div>
            <div class="bar {comp_bar}"><span style="width:{comp_score}%"></span></div>
          </div>
          <div class="bar-group">
            <div class="bar-head"><span>Reliability</span><span>{rel_bar["display"]}</span></div>
            <div class="bar {rel_bar["class"]}"><span style="width:{rel_bar["width"]}%"></span></div>
          </div>
        </div>

        <h3 class="sub-header">Subsections</h3>
        <p class="summary-line">Done: {counts["Done"]} | In Progress: {counts["In Progress"]} | Planned: {counts["Planned"] + counts["Not Started"]} | Blocked: {counts["Blocked"]}</p>
        <ul class="checks">
          {''.join(items_html)}
        </ul>
        <p class="zone-note">{note}</p>
      </article>
        """.strip()
    )


def build_control_tower_html(progress: Dict[str, Any], zone_order: List[str], zone_meta: Dict[str, Any]) -> str:
    sections = []
    for zone_id in zone_order:
        zone = progress["zones"][zone_id]
        split_systems = SPLIT_ZONE_SYSTEMS.get(zone_id, [])
        if split_systems:
            system_cards = []
            for system_id in split_systems:
                system = progress["systems"].get(system_id)
                if not system:
                    continue
                system_cards.append(
                    render_progress_card(
                        entity=system,
                        title=system["system_name"],
                        purpose=system["purpose"],
                        note=system["notes"],
                    )
                )
            sections.append(
                f"""
      <section class="zone-group">
        <div class="zone-banner">
          <h2>{zone["zone_name"]}</h2>
          <p>{zone["purpose"]}</p>
          <p><strong>Zone Focus:</strong> {zone["main_focus"]}</p>
        </div>
        <div class="grid">
          {' '.join(system_cards)}
        </div>
      </section>
                """.strip()
            )
            continue

        sections.append(
            render_progress_card(
                entity=zone,
                title=zone["zone_name"],
                purpose=zone["purpose"],
                note=zone["notes"],
            )
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SellerOne Control Tower</title>
  <style>
    :root {{
      --bg: #f4f7fb;
      --card: #ffffff;
      --text: #1f2937;
      --muted: #475569;
      --border: #d7deea;
      --bar-bg: #e5e7eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Segoe UI", Tahoma, Arial, sans-serif;
    }}
    .wrap {{
      max-width: 1460px;
      margin: 0 auto;
      padding: 24px 18px 28px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 34px;
      line-height: 1.2;
    }}
    .top-note {{
      margin: 0 0 16px;
      background: #e9eff8;
      border: 1px solid #c7d5ea;
      border-radius: 10px;
      padding: 12px 14px;
      color: #334155;
      font-size: 14px;
      line-height: 1.45;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid transparent;
      white-space: nowrap;
    }}
    .planned {{ background: #f3f4f6; color: #374151; border-color: #d1d5db; }}
    .inprogress {{ background: #dbeafe; color: #1e40af; border-color: #93c5fd; }}
    .done {{ background: #dcfce7; color: #14532d; border-color: #86efac; }}
    .blocked {{ background: #fee2e2; color: #7f1d1d; border-color: #fca5a5; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(330px, 1fr));
      gap: 14px;
    }}
    .zone-group {{
      grid-column: 1 / -1;
    }}
    .zone-banner {{
      background: #e8f0fb;
      border: 1px solid #c9d8ed;
      border-radius: 12px;
      padding: 10px 12px;
      margin: 2px 0 10px;
    }}
    .zone-banner h2 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      color: #0f172a;
    }}
    .zone-banner p {{
      margin: 4px 0 0;
      font-size: 14px;
      color: #334155;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px 14px 12px;
      box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
    }}
    .head {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
      margin-bottom: 8px;
    }}
    .zone-title {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
    }}
    .purpose {{
      margin: 4px 0 0;
      font-size: 14px;
      color: var(--muted);
    }}
    .status-chip {{
      font-size: 12px;
      font-weight: 800;
      border-radius: 999px;
      padding: 6px 10px;
      border: 1px solid transparent;
      white-space: nowrap;
    }}
    .status-planned {{ background: #f3f4f6; color: #374151; border-color: #d1d5db; }}
    .status-progress {{ background: #dbeafe; color: #1e40af; border-color: #93c5fd; }}
    .status-done {{ background: #dcfce7; color: #14532d; border-color: #86efac; }}
    .status-blocked {{ background: #fee2e2; color: #7f1d1d; border-color: #fca5a5; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(2, minmax(160px, 1fr));
      gap: 10px;
      margin-bottom: 10px;
    }}
    .metric {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 9px 10px;
    }}
    .metric .label {{
      margin: 0;
      font-size: 12px;
      color: #475569;
      font-weight: 700;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }}
    .metric .value {{
      margin: 3px 0 0;
      font-size: 20px;
      font-weight: 800;
      line-height: 1.2;
    }}
    .focus {{
      margin: 0 0 10px;
      font-size: 14px;
      color: #334155;
    }}
    .focus strong {{ color: #0f172a; }}
    .bars {{ margin-bottom: 10px; }}
    .bar-group {{ margin-bottom: 8px; }}
    .bar-head {{
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      font-weight: 700;
      color: #475569;
      margin-bottom: 3px;
    }}
    .bar {{
      height: 16px;
      border-radius: 10px;
      background: var(--bar-bg);
      overflow: hidden;
      border: 1px solid #cbd5e1;
    }}
    .bar > span {{
      display: block;
      height: 100%;
      border-radius: 9px;
    }}
    .bar-red > span {{ background: #ef4444; }}
    .bar-orange > span {{ background: #f59e0b; }}
    .bar-yellow > span {{ background: #eab308; }}
    .bar-green > span {{ background: #22c55e; }}
    .bar-bluegrey > span {{
      background: repeating-linear-gradient(-45deg, #94a3b8, #94a3b8 8px, #cbd5e1 8px, #cbd5e1 16px);
    }}
    .sub-header {{
      margin: 8px 0 6px;
      font-size: 13px;
      color: #334155;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }}
    .summary-line {{
      font-size: 12px;
      color: #64748b;
      margin: 0 0 8px;
      font-weight: 700;
    }}
    ul.checks {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 6px;
    }}
    ul.checks li {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: center;
      border: 1px solid #e2e8f0;
      background: #fbfdff;
      border-radius: 8px;
      padding: 8px 9px;
      font-size: 14px;
    }}
    .sub-name {{ color: #1f2937; }}
    .tag {{
      font-size: 11px;
      font-weight: 800;
      border-radius: 999px;
      padding: 4px 8px;
      border: 1px solid transparent;
      white-space: nowrap;
    }}
    .zone-note {{
      margin: 8px 0 0;
      font-size: 12px;
      color: #64748b;
    }}
    .footer {{
      margin-top: 16px;
      font-size: 13px;
      color: #475569;
      background: #eef2f7;
      border: 1px solid #d7deea;
      border-radius: 10px;
      padding: 10px 12px;
    }}
    .footer code {{
      background: #e2e8f0;
      border-radius: 4px;
      padding: 1px 5px;
      font-family: Consolas, "Courier New", monospace;
    }}
    @media (max-width: 1120px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>SellerOne Control Tower</h1>
    <p class="top-note">
      This is the main management view for day-to-day tracking.
      Use <code>SYSTEM_FLOWCHART.html</code> for the conceptual map.
      Completion is now checklist-derived from <code>TASK_LIBRARY.json</code> and <code>CHECKLIST_PROGRESS.json</code>.
      Reliability remains evidence-based and separate from completion scoring.
    </p>

    <div class="legend">
      <span class="pill planned">Grey = Planned</span>
      <span class="pill inprogress">Blue = In Progress</span>
      <span class="pill done">Green = Done</span>
      <span class="pill blocked">Red = Blocked / Needs Stabilising</span>
    </div>

    <section class="grid">
      {' '.join(sections)}
    </section>

    <div class="footer">
      Related views and source docs:
      <code>SYSTEM_FLOWCHART.html</code> |
      <code>ROADMAP_SYSTEM_MAP.md</code> |
      <code>ZONE_INDEX.md</code> |
      <code>EXPECTATIONS/</code>
      <br>
      Generated at: <code>{progress["generated_utc"]}</code>
    </div>
  </div>
</body>
</html>
"""
    return html


def main() -> None:
    library = json.loads(TASK_LIBRARY_PATH.read_text(encoding="utf-8"))
    generated_utc = now_utc()
    zone_order = library["zone_order"]
    zones_meta = library["zones"]
    systems_meta = library.get("systems", {})
    tasks = library["tasks"]

    checklist_items = []
    zone_items = defaultdict(list)
    system_items = defaultdict(list)

    for task in tasks:
        status = normalize_status(task["status"])
        item = {
            "id": task["id"],
            "zone": task["zone"],
            "system": task["system"],
            "item_name": task["title"],
            "status": status,
            "weight": float(task.get("weight", 1.0)),
            "task_type": task.get("task_type", "task"),
            "evidence_note": task.get("notes", ""),
            "last_reviewed_utc": task.get("last_reviewed_utc", ""),
            "reviewer": task.get("reviewer", ""),
            "source_ref": task.get("source_ref", ""),
            "status_value": STATUS_VALUES[status],
        }
        checklist_items.append(item)
        zone_items[item["zone"]].append(item)
        system_items[item["system"]].append(item)

    checklist_doc = {
        "version": library.get("version", "v1"),
        "generated_utc": generated_utc,
        "source_task_library": str(TASK_LIBRARY_PATH.relative_to(ROOT)).replace("\\", "/"),
        "status_model": {
            "Not Started": 0.0,
            "Planned": 0.0,
            "In Progress": 0.5,
            "Blocked": 0.25,
            "Done": 1.0,
        },
        "items": checklist_items,
    }
    CHECKLIST_PROGRESS_PATH.write_text(json.dumps(checklist_doc, indent=2), encoding="utf-8")

    zones_rollup: Dict[str, Any] = {}
    for zone_id in zone_order:
        items = zone_items.get(zone_id, [])
        meta = zones_meta[zone_id]
        score = score_items(items)
        counts = summarize_status(items)
        zones_rollup[zone_id] = {
            "zone_id": zone_id,
            "zone_name": meta["name"],
            "purpose": meta["purpose"],
            "completion_score": score,
            "status": infer_zone_status(items),
            "main_focus": meta["main_focus"],
            "notes": meta["notes"],
            "reliability": meta["reliability"],
            "subsection_counts": counts,
            "subsections": [
                {
                    "id": item["id"],
                    "system": item["system"],
                    "title": item["item_name"],
                    "status": item["status"],
                    "weight": item["weight"],
                    "source_ref": item["source_ref"],
                }
                for item in items
            ],
        }

    systems_rollup: Dict[str, Any] = {}
    for system_id, items in system_items.items():
        meta = systems_meta.get(system_id, {})
        zone_id = meta.get("zone", items[0]["zone"] if items else "unknown")
        counts = summarize_status(items)
        system_status = infer_zone_status(items)
        # H is intentionally shown as an unstable top-level runtime while boundary truth handling is still blocked.
        if system_id == "H_cycle" and counts.get("Blocked", 0) > 0:
            system_status = "Needs Stabilising"

        systems_rollup[system_id] = {
            "system_id": system_id,
            "zone_id": zone_id,
            "system_name": meta.get("name", system_id),
            "purpose": meta.get("purpose", ""),
            "completion_score": score_items(items),
            "status": system_status,
            "main_focus": meta.get("main_focus", zones_meta.get(zone_id, {}).get("main_focus", "")),
            "notes": meta.get("notes", ""),
            "reliability": meta.get("reliability", zones_meta.get(zone_id, {}).get("reliability", {"label": "To Baseline", "score": None})),
            "subsection_counts": counts,
            "subsections": [
                {
                    "id": item["id"],
                    "title": item["item_name"],
                    "status": item["status"],
                    "weight": item["weight"],
                    "source_ref": item["source_ref"],
                }
                for item in items
            ],
            "item_counts": counts,
        }

    system_progress = {
        "version": library.get("version", "v1"),
        "generated_utc": generated_utc,
        "source": {
            "task_library": str(TASK_LIBRARY_PATH.relative_to(ROOT)).replace("\\", "/"),
            "checklist_progress": str(CHECKLIST_PROGRESS_PATH.relative_to(ROOT)).replace("\\", "/"),
            "generator": str(Path(__file__).relative_to(ROOT)).replace("\\", "/"),
        },
        "zones": zones_rollup,
        "systems": systems_rollup,
    }
    SYSTEM_PROGRESS_PATH.write_text(json.dumps(system_progress, indent=2), encoding="utf-8")

    html = build_control_tower_html(system_progress, zone_order, zones_meta)
    CONTROL_TOWER_PATH.write_text(html, encoding="utf-8")

    print("Generated:")
    print(f"- {CHECKLIST_PROGRESS_PATH.relative_to(ROOT)}")
    print(f"- {SYSTEM_PROGRESS_PATH.relative_to(ROOT)}")
    print(f"- {CONTROL_TOWER_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

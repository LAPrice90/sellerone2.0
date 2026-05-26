from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

TEMPLATE_FILES = {
    "PROJECT_BRIEF_TEMPLATE.md": "PROJECT_BRIEF.md",
    "INCIDENT_BRIEF_TEMPLATE.md": "INCIDENT_BRIEF.md",
    "PLAN_TEMPLATE.md": "PLAN.md",
    "CODING_PLAN_TEMPLATE.md": "CODING_PLAN.md",
    "PLAN_STATUS_TEMPLATE.md": "PLAN_STATUS.md",
    "EXECUTION_BATCH_TEMPLATE.md": "EXECUTION_BATCH_001.md",
    "DEBUG_BATCH_TEMPLATE.md": "DEBUG_BATCH_001.md",
    "EXECUTION_REPLY_TEMPLATE.md": "EXECUTION_BATCH_001_REPLY.md",
    "DATA_CONTRACTS_TEMPLATE.md": "DATA_CONTRACTS.md",
    "RUNBOOK_TEMPLATE.md": "RUNBOOK.md",
}


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


def create_plan_workspace(slug: str, root: Path = ROOT) -> Path:
    cleaned_slug = slugify(slug)
    if not cleaned_slug:
        raise ValueError("Slug must contain at least one letter or number.")

    templates_dir = root / "plans" / "templates"
    active_dir = root / "plans" / "active"
    plan_dir = active_dir / cleaned_slug

    if plan_dir.exists():
        raise FileExistsError(f"Plan folder already exists: {plan_dir}")

    active_dir.mkdir(parents=True, exist_ok=True)
    plan_dir.mkdir(parents=True, exist_ok=False)

    for template_name, output_name in TEMPLATE_FILES.items():
        template_path = templates_dir / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Missing template: {template_path}")
        shutil.copyfile(template_path, plan_dir / output_name)

    return plan_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a standard plan workspace under plans/active/."
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="Plan folder name. Plain words are fine; the script will slugify it.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan_dir = create_plan_workspace(slug=args.slug, root=ROOT)
    print(f"created_plan={plan_dir.relative_to(ROOT)}")
    print(f"files_created={len(TEMPLATE_FILES)}")


if __name__ == "__main__":
    main()

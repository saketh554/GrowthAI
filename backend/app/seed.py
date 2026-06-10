from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Employee


@dataclass(frozen=True)
class EmployeeSeed:
    employee_id: str
    name: str
    grade: int
    title: str
    department: str
    manager_id: str
    home_base: str


def _parse_employee_seed(path: Path) -> EmployeeSeed:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EmployeeSeed(
        employee_id=payload["employee_id"],
        name=payload["name"],
        grade=int(payload["grade"]),
        title=payload["title"],
        department=payload["department"],
        manager_id=payload["manager_id"],
        home_base=payload["home_base"],
    )


def seed_employees(session: Session, submissions_dir: str) -> int:
    base = Path(submissions_dir)
    if not base.exists():
        fallback = Path("./submissions")
        base = fallback if fallback.exists() else base

    if not base.exists():
        return 0

    inserted = 0
    for info_path in sorted(base.glob("*/employee_info.json")):
        seed = _parse_employee_seed(info_path)
        existing = session.scalar(select(Employee).where(Employee.id == seed.employee_id))
        if existing is not None:
            continue

        session.add(
            Employee(
                id=seed.employee_id,
                name=seed.name,
                grade=seed.grade,
                title=seed.title,
                department=seed.department,
                manager_id=seed.manager_id,
                home_base=seed.home_base,
            )
        )
        inserted += 1

    return inserted

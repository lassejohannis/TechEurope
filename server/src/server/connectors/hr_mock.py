"""HR connector — reads employees.json + resume_information.csv."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterator

from server.connectors.base import BaseConnector, SourceRecord


class HRConnector(BaseConnector):
    source_type = "hr_record"

    def fetch(self, path: Path) -> Iterator[dict]:
        if path.is_dir():
            emp_file = path / "Employees" / "employees.json"
            if emp_file.exists():
                yield from self._load_employees(emp_file)
            resume_file = path / "Resume" / "resume_information.csv"
            if resume_file.exists():
                yield from self._load_resumes(resume_file)
        elif path.suffix == ".json":
            yield from self._load_employees(path)
        elif path.suffix == ".csv":
            yield from self._load_resumes(path)

    def _load_employees(self, path: Path) -> Iterator[dict]:
        with open(path) as f:
            for emp in json.load(f):
                yield {"_record_subtype": "employee", "_source_file": str(path), **emp}

    def _load_resumes(self, path: Path) -> Iterator[dict]:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                yield {"_record_subtype": "resume", "_source_file": str(path), **row}

    def normalize(self, raw: dict) -> SourceRecord:
        subtype = raw.pop("_record_subtype", "employee")
        source_file = raw.pop("_source_file", "hr")

        if subtype == "employee":
            native_id = raw.get("emp_id", "")
            payload = {
                "emp_id": raw.get("emp_id"),
                "name": raw.get("Name"),
                "email": raw.get("email"),
                "category": raw.get("category"),
                "level": raw.get("Level"),
                "salary": raw.get("Salary"),
                "doj": raw.get("DOJ"),
                "dol": raw.get("DOL"),
                "skills": raw.get("skills"),
                "reportees": raw.get("reportees", []),
                "performance_rating": raw.get("Performance Rating"),
            }
        else:  # resume
            native_id = raw.get("resume_id", raw.get("emp_id", ""))
            payload = {
                "resume_id": raw.get("resume_id"),
                "emp_id": raw.get("emp_id"),
                "name": raw.get("name"),
                "email": raw.get("email"),
                "category": raw.get("category"),
                "content": raw.get("content", "")[:4000],  # cap for jsonb
                "created_date": raw.get("created_date"),
            }

        content_hash = SourceRecord.hash_payload(payload)
        return SourceRecord(
            id=SourceRecord.make_id(f"hr_{subtype}", content_hash),
            source_type=self.source_type,
            source_uri=source_file,
            source_native_id=native_id,
            payload=payload,
            content_hash=content_hash,
            metadata={"method": "connector_ingest", "subtype": subtype},
        )

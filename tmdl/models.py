"""Dataclasses representing parsed TMDL entities.

TMDL (Tabular Model Definition Language) is the tab-indented, text-based
format Power BI / Analysis Services uses to describe a semantic model
(one file per table/role/culture under a `definition/` folder).

These models are intentionally "loose": every block keeps its raw text
range (start_line/end_line) so the writer module can perform precise,
surgical edits without needing a full round-trip re-serializer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Column:
    name: str
    data_type: Optional[str] = None
    format_string: Optional[str] = None
    source_column: Optional[str] = None
    summarize_by: Optional[str] = None
    is_hidden: bool = False
    is_key: bool = False
    data_category: Optional[str] = None
    sort_by_column: Optional[str] = None
    display_folder: Optional[str] = None
    description: Optional[str] = None
    lineage_tag: Optional[str] = None
    expression: Optional[str] = None  # set for calculated columns: `column X = <DAX>`
    annotations: dict = field(default_factory=dict)
    start_line: int = -1
    end_line: int = -1

    @property
    def is_calculated(self) -> bool:
        return self.expression is not None


@dataclass
class Measure:
    name: str
    expression: str
    format_string: Optional[str] = None
    display_folder: Optional[str] = None
    description: Optional[str] = None
    is_hidden: bool = False
    lineage_tag: Optional[str] = None
    annotations: dict = field(default_factory=dict)
    has_kpi: bool = False
    kpi_raw_lines: list = field(default_factory=list)  # preserved verbatim, not re-parsed
    start_line: int = -1
    end_line: int = -1


@dataclass
class Partition:
    name: str
    mode: Optional[str] = None
    source_kind: Optional[str] = None  # 'm', 'calculated', 'query'
    source_text: str = ""
    start_line: int = -1
    end_line: int = -1


@dataclass
class Hierarchy:
    name: str
    levels: list = field(default_factory=list)
    start_line: int = -1
    end_line: int = -1


@dataclass
class Table:
    name: str
    lineage_tag: Optional[str] = None
    description: Optional[str] = None
    is_hidden: bool = False
    display_folder: Optional[str] = None
    columns: list = field(default_factory=list)   # list[Column]
    measures: list = field(default_factory=list)  # list[Measure]
    partitions: list = field(default_factory=list)  # list[Partition]
    hierarchies: list = field(default_factory=list)  # list[Hierarchy]
    annotations: dict = field(default_factory=dict)
    source_path: Optional[str] = None
    raw_lines: list = field(default_factory=list)  # full file, split by line

    def find_column(self, name: str) -> Optional[Column]:
        for c in self.columns:
            if c.name.lower() == name.lower():
                return c
        return None

    def find_measure(self, name: str) -> Optional[Measure]:
        for m in self.measures:
            if m.name.lower() == name.lower():
                return m
        return None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "is_hidden": self.is_hidden,
            "columns": [
                {
                    "name": c.name,
                    "data_type": c.data_type,
                    "source_column": c.source_column,
                    "format_string": c.format_string,
                    "is_hidden": c.is_hidden,
                    "is_key": c.is_key,
                    "is_calculated": c.is_calculated,
                    "expression": c.expression,
                    "data_category": c.data_category,
                    "sort_by_column": c.sort_by_column,
                    "description": c.description,
                }
                for c in self.columns
            ],
            "measures": [
                {
                    "name": m.name,
                    "expression": m.expression,
                    "format_string": m.format_string,
                    "is_hidden": m.is_hidden,
                    "description": m.description,
                    "has_kpi": m.has_kpi,
                }
                for m in self.measures
            ],
            "hierarchies": [
                {"name": h.name, "levels": h.levels} for h in self.hierarchies
            ],
            "partitions": [
                {"name": p.name, "mode": p.mode, "source_kind": p.source_kind}
                for p in self.partitions
            ],
        }

"""A pragmatic, dependency-free parser for TMDL table definition files.

TMDL is tab-indented. Every nesting level adds exactly one leading tab
character. This parser walks the file line by line, tracking indentation
depth, and builds `Table` / `Column` / `Measure` / `Partition` objects
(see models.py). It intentionally does not attempt a lossless full-grammar
parse (TMDL's real grammar is larger — roles, cultures, relationships,
perspectives live in sibling files) but it is robust for the
table-definition files that hold columns, measures and partitions, which
is what's needed to answer questions about the model and to safely edit
DAX measures / descriptions / annotations.
"""

from __future__ import annotations

import glob
import os
from typing import List, Optional, Tuple

from .models import Column, Hierarchy, Measure, Partition, Table

_PROP_PREFIXES = ("formatString:", "lineageTag:", "displayFolder:", "isHidden", "annotation ", "///", "changedProperty", "kpi")

_COLUMN_PROP_PREFIXES = (
    "dataType:", "formatString:", "lineageTag:", "displayFolder:", "isHidden",
    "annotation ", "///", "sourceColumn:", "summarizeBy:", "dataCategory:",
    "sortByColumn:", "isKey", "isNameInferred", "isDataTypeInferred",
    "isAvailableInMdx", "variation ", "changedProperty",
)


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip("\t"))


def _unquote(name: str) -> str:
    name = name.strip()
    if len(name) >= 2 and name[0] == "'" and name[-1] == "'":
        return name[1:-1]
    return name


def _parse_annotation(stripped_line: str) -> Tuple[str, str]:
    body = stripped_line[len("annotation "):]
    key, _, value = body.partition("=")
    return key.strip(), value.strip()


def _find_block_end(lines: List[str], start: int, header_indent: int) -> int:
    """Return the index of the first line whose indent is <= header_indent
    (i.e. the line *after* the block), scanning forward from `start`."""
    i = start
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.strip() == "":
            i += 1
            continue
        if _indent_of(line) <= header_indent:
            return i
        i += 1
    return i


def _parse_column(lines: List[str], i: int, header_indent: int) -> Tuple[Column, int]:
    """Handles both regular columns (`column Name`) and calculated columns
    (`column Name = <DAX expression>`, possibly spanning multiple lines)."""
    header = lines[i].strip()
    rest = header[len("column "):]
    if "=" in rest:
        name_part, _, expr_part = rest.partition("=")
        name = _unquote(name_part.strip())
        first_expr: Optional[str] = expr_part.strip()
    else:
        name = _unquote(rest.strip())
        first_expr = None

    col = Column(name=name, start_line=i)
    end = _find_block_end(lines, i + 1, header_indent)
    j = i + 1
    expr_lines: List[str] = [first_expr] if first_expr else []
    still_expr = first_expr is not None

    while j < end:
        line = lines[j]
        if line.strip() == "":
            if still_expr:
                expr_lines.append("")
            j += 1
            continue
        ind = _indent_of(line)
        s = line.strip()
        if still_expr and ind == header_indent + 1 and s.startswith(_COLUMN_PROP_PREFIXES):
            still_expr = False
        if still_expr:
            expr_lines.append(line[header_indent + 1:] if len(line) > header_indent + 1 else s)
            j += 1
            continue

        if s.startswith("dataType:"):
            col.data_type = s.split(":", 1)[1].strip()
        elif s.startswith("formatString:"):
            col.format_string = s.split(":", 1)[1].strip()
        elif s.startswith("sourceColumn:"):
            col.source_column = s.split(":", 1)[1].strip()
        elif s.startswith("summarizeBy:"):
            col.summarize_by = s.split(":", 1)[1].strip()
        elif s.startswith("lineageTag:"):
            col.lineage_tag = s.split(":", 1)[1].strip()
        elif s.startswith("displayFolder:"):
            col.display_folder = s.split(":", 1)[1].strip()
        elif s.startswith("dataCategory:"):
            col.data_category = s.split(":", 1)[1].strip()
        elif s.startswith("sortByColumn:"):
            col.sort_by_column = s.split(":", 1)[1].strip()
        elif s.startswith("isKey"):
            col.is_key = True
        elif s.startswith("isHidden"):
            col.is_hidden = True
        elif s.startswith("annotation "):
            k, v = _parse_annotation(s)
            col.annotations[k] = v
        elif s.startswith("///"):
            d = s[3:].strip()
            col.description = (col.description + " " + d).strip() if col.description else d
        # variation / changedProperty / isNameInferred / isDataTypeInferred /
        # isAvailableInMdx: recognized (so they don't get mis-parsed as
        # expression continuation) but not individually modeled.
        j += 1

    if expr_lines:
        col.expression = "\n".join(expr_lines).strip("\n").strip()
    col.end_line = end - 1
    return col, end


def _parse_measure(lines: List[str], i: int, header_indent: int) -> Tuple[Measure, int]:
    header = lines[i].strip()
    rest = header[len("measure "):]
    name_part, _, expr_part = rest.partition("=")
    name = _unquote(name_part.strip())
    expr_lines = []
    first = expr_part.strip()
    if first:
        expr_lines.append(first)
    end = _find_block_end(lines, i + 1, header_indent)
    meas = Measure(name=name, expression="", start_line=i)
    j = i + 1
    still_expr = True
    while j < end:
        line = lines[j]
        if line.strip() == "":
            if still_expr:
                expr_lines.append("")
            j += 1
            continue
        ind = _indent_of(line)
        s = line.strip()
        if still_expr and ind == header_indent + 1 and s.startswith(_PROP_PREFIXES):
            still_expr = False
        if still_expr:
            expr_lines.append(line[header_indent + 1:] if len(line) > header_indent + 1 else s)
        else:
            if ind == header_indent + 1 and s.startswith("kpi"):
                kpi_end = _find_block_end(lines, j + 1, header_indent + 1)
                meas.has_kpi = True
                meas.kpi_raw_lines = lines[j:kpi_end]
                j = kpi_end
                continue
            if s.startswith("formatString:"):
                meas.format_string = s.split(":", 1)[1].strip()
            elif s.startswith("lineageTag:"):
                meas.lineage_tag = s.split(":", 1)[1].strip()
            elif s.startswith("displayFolder:"):
                meas.display_folder = s.split(":", 1)[1].strip()
            elif s.startswith("isHidden"):
                meas.is_hidden = True
            elif s.startswith("annotation "):
                k, v = _parse_annotation(s)
                meas.annotations[k] = v
            elif s.startswith("///"):
                d = s[3:].strip()
                meas.description = (meas.description + " " + d).strip() if meas.description else d
        j += 1
    meas.expression = "\n".join(expr_lines).strip("\n").strip()
    meas.end_line = end - 1
    return meas, end


def _parse_partition(lines: List[str], i: int, header_indent: int) -> Tuple[Partition, int]:
    header = lines[i].strip()
    rest = header[len("partition "):]
    name_part, _, kind_part = rest.partition("=")
    part = Partition(name=_unquote(name_part.strip()), source_kind=kind_part.strip(), start_line=i)
    end = _find_block_end(lines, i + 1, header_indent)
    j = i + 1
    source_lines: List[str] = []
    in_source = False
    while j < end:
        line = lines[j]
        if line.strip() == "":
            if in_source:
                source_lines.append("")
            j += 1
            continue
        ind = _indent_of(line)
        s = line.strip()
        if ind == header_indent + 1:
            if s.startswith("mode:"):
                part.mode = s.split(":", 1)[1].strip()
                in_source = False
            elif s.startswith("source"):
                in_source = True
                _, _, inline_val = s.partition("=")
                if inline_val.strip():
                    source_lines.append(inline_val.strip())
            else:
                in_source = False
        else:
            if in_source:
                cut = header_indent + 2
                source_lines.append(line[cut:] if len(line) > cut else s)
        j += 1
    part.source_text = "\n".join(source_lines).strip("\n")
    part.end_line = end - 1
    return part, end


def _parse_hierarchy(lines: List[str], i: int, header_indent: int) -> Tuple[Hierarchy, int]:
    header = lines[i].strip()
    name = _unquote(header[len("hierarchy "):])
    hier = Hierarchy(name=name, start_line=i)
    end = _find_block_end(lines, i + 1, header_indent)
    j = i + 1
    while j < end:
        s = lines[j].strip()
        if s.startswith("level "):
            hier.levels.append(_unquote(s[len("level "):].partition("=")[0].strip()))
        j += 1
    hier.end_line = end - 1
    return hier, end


def parse_tmdl_text(text: str, source_path: Optional[str] = None) -> Table:
    lines = text.splitlines()
    n = len(lines)
    table = Table(name="", raw_lines=lines, source_path=source_path)

    i = 0
    while i < n:
        stripped = lines[i].strip()
        if stripped.startswith("table "):
            table.name = _unquote(stripped[len("table "):])
            i += 1
            break
        i += 1

    pending_description: List[str] = []
    while i < n:
        line = lines[i]
        if line.strip() == "":
            i += 1
            continue
        indent = _indent_of(line)
        stripped = line.strip()
        if indent == 0:
            break
        if indent != 1:
            i += 1
            continue

        if stripped.startswith("///"):
            pending_description.append(stripped[3:].strip())
            i += 1
            continue
        if stripped.startswith("column "):
            col, i = _parse_column(lines, i, indent)
            if pending_description:
                col.description = " ".join(pending_description)
                pending_description = []
            table.columns.append(col)
            continue
        if stripped.startswith("measure "):
            meas, i = _parse_measure(lines, i, indent)
            if pending_description:
                meas.description = " ".join(pending_description)
                pending_description = []
            table.measures.append(meas)
            continue
        if stripped.startswith("partition "):
            part, i = _parse_partition(lines, i, indent)
            table.partitions.append(part)
            continue
        if stripped.startswith("hierarchy "):
            hier, i = _parse_hierarchy(lines, i, indent)
            table.hierarchies.append(hier)
            continue
        if stripped.startswith("annotation "):
            k, v = _parse_annotation(stripped)
            table.annotations[k] = v
            pending_description = []
            i += 1
            continue
        if stripped.startswith("lineageTag:"):
            table.lineage_tag = stripped.split(":", 1)[1].strip()
            i += 1
            continue
        if stripped.startswith("isHidden"):
            table.is_hidden = True
            i += 1
            continue
        if stripped.startswith("displayFolder:"):
            table.display_folder = stripped.split(":", 1)[1].strip()
            i += 1
            continue
        pending_description = []
        i += 1

    return table


def parse_tmdl_file(path: str) -> Table:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return parse_tmdl_text(text, source_path=path)


def list_tmdl_table_files(definition_dir: str) -> List[str]:
    """definition_dir is the model's `definition/` folder (contains tables/)."""
    pattern = os.path.join(definition_dir, "tables", "*.tmdl")
    return sorted(glob.glob(pattern))


def parse_definition_folder(definition_dir: str) -> List[Table]:
    tables = []
    for path in list_tmdl_table_files(definition_dir):
        try:
            tables.append(parse_tmdl_file(path))
        except Exception as exc:  # keep going even if one file is malformed
            t = Table(name=os.path.basename(path), source_path=path)
            t.annotations["_parse_error"] = str(exc)
            tables.append(t)
    return tables
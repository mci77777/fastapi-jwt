#!/usr/bin/env python3
"""
Supabase 命名与引用审计（仓库内扫描 + 生成 docs 报告）

目标：
- 明确“后端归属表”与“App 端归属表”的边界（以 docs/schemas/SUPABASE_SCHEMA_OWNERSHIP_AND_NAMING.md 为准）
- 扫描仓库内对 Supabase 表的引用（REST / SQL DDL / 文档）
- 检测命名是否符合 snake_case，并输出报告到 docs/_audit/

注意：
- 本脚本不改动 Supabase 数据库，仅做静态扫描与报告生成。
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Set, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT_SQL_DIR = PROJECT_ROOT / "scripts" / "deployment" / "sql"


DEFAULT_BACKEND_OWNED_TABLES: Set[str] = {
    "conversations",
    "messages",
    "ai_model",
    "ai_prompt",
    "user_anon",
    "anon_sessions",
    "anon_messages",
    "anon_rate_limits",
}

DEFAULT_DESTRUCTIVE_PUBLIC_TABLES_REQUIRING_MANUAL_CONFIRM: Set[str] = {
    "message_embedding",
    "session_summary",
}


def load_ownership_map() -> dict:
    """
    从 docs/schemas/supabase_ownership_map.json 加载可配置表归属。
    不存在时回退到脚本内默认值。
    """

    path = PROJECT_ROOT / "docs" / "schemas" / "supabase_ownership_map.json"
    if not path.exists():
        return {
            "backend_owned_tables": sorted(DEFAULT_BACKEND_OWNED_TABLES),
            "high_risk_public_tables_deleted_in_legacy_cleanup": sorted(DEFAULT_DESTRUCTIVE_PUBLIC_TABLES_REQUIRING_MANUAL_CONFIRM),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "backend_owned_tables": sorted(DEFAULT_BACKEND_OWNED_TABLES),
            "high_risk_public_tables_deleted_in_legacy_cleanup": sorted(DEFAULT_DESTRUCTIVE_PUBLIC_TABLES_REQUIRING_MANUAL_CONFIRM),
        }
    return data if isinstance(data, dict) else {
        "backend_owned_tables": sorted(DEFAULT_BACKEND_OWNED_TABLES),
        "high_risk_public_tables_deleted_in_legacy_cleanup": sorted(DEFAULT_DESTRUCTIVE_PUBLIC_TABLES_REQUIRING_MANUAL_CONFIRM),
    }


SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class Finding:
    kind: str
    file: str
    identifier: str
    message: str


def iter_files() -> Iterable[Path]:
    """
    仅扫描“源码/脚本/文档”的可控范围，避免 node_modules/dist 等噪声导致耗时过长。
    """

    include_dirs = [
        PROJECT_ROOT / "app",
        PROJECT_ROOT / "scripts",
        PROJECT_ROOT / "web" / "src",
        PROJECT_ROOT / "e2e",
        PROJECT_ROOT / "docs",
    ]
    exts = {".py", ".js", ".ts", ".vue", ".md", ".sql"}
    excluded_dir_names = {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".cache",
    }

    for base in include_dirs:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in exts:
                continue
            if any(part in excluded_dir_names for part in path.parts):
                continue
            yield path


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_rest_tables(content: str) -> Set[str]:
    # 匹配 /rest/v1/<table>，排除带引号的 query string 影响
    return set(re.findall(r"/rest/v1/([a-zA-Z0-9_]+)", content))


def extract_sql_ops(content: str) -> List[Tuple[str, str]]:
    """
    非严格 SQL 解析：提取 (op, name)，用于区分 DROP/ALTER/CREATE。
    op: create_table | alter_table | drop_table | create_view | drop_view | create_policy
    """

    ops: List[Tuple[str, str]] = []
    patterns = [
        ("create_table", r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_.]+)"),
        ("alter_table", r"\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?([a-zA-Z0-9_.]+)"),
        ("drop_table", r"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([a-zA-Z0-9_.]+)"),
        ("create_view", r"\bCREATE\s+VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_.]+)"),
        ("drop_view", r"\bDROP\s+VIEW\s+(?:IF\s+EXISTS\s+)?([a-zA-Z0-9_.]+)"),
        ("create_policy", r"\bCREATE\s+POLICY\s+\"?[^\n]+\"?\s+ON\s+([a-zA-Z0-9_.]+)"),
    ]
    for op, pat in patterns:
        for raw in re.findall(pat, content, flags=re.IGNORECASE):
            name = raw.strip().strip('"')
            # 过滤明显的误匹配（例如抓到 IF/ONLY 等）
            if name.lower() in {"if", "only"}:
                continue
            ops.append((op, name))
    return ops


def normalize_table_name(name: str) -> Tuple[str, str]:
    """
    返回 (schema, table)。
    允许 name 为 table / schema.table。
    """
    if "." in name:
        schema, table = name.split(".", 1)
        return schema.lower(), table.lower()
    return "public", name.lower()


def is_snake_case(name: str) -> bool:
    return bool(SNAKE_CASE_RE.match(name))


def scan() -> Tuple[List[Finding], dict]:
    ownership = load_ownership_map()
    backend_owned_tables = {str(x).lower() for x in (ownership.get("backend_owned_tables") or DEFAULT_BACKEND_OWNED_TABLES)}
    destructive_public_tables_requiring_manual_confirm = {
        str(x).lower()
        for x in (
            ownership.get("high_risk_public_tables_deleted_in_legacy_cleanup")
            or DEFAULT_DESTRUCTIVE_PUBLIC_TABLES_REQUIRING_MANUAL_CONFIRM
        )
    }
    findings: List[Finding] = []
    referenced_tables: Set[str] = set()
    ddl_touched_tables: Set[str] = set()
    ddl_drop_tables: Set[str] = set()

    per_file_refs: List[dict] = []

    for path in iter_files():
        content = read_text(path)

        rest_tables = extract_rest_tables(content)
        sql_ops: List[Tuple[str, str]] = []
        # 仅对部署 SQL 目录做 DDL 扫描，避免 docs/*.sql 等大文件造成噪声
        if path.suffix.lower() == ".sql":
            try:
                is_deploy_sql = path.resolve().is_relative_to(DEPLOYMENT_SQL_DIR.resolve())
            except Exception:
                is_deploy_sql = str(path).replace("\\", "/").startswith(str(DEPLOYMENT_SQL_DIR).replace("\\", "/"))
            if is_deploy_sql:
                sql_ops = extract_sql_ops(content)

        file_refs: Set[str] = set()
        for t in rest_tables:
            referenced_tables.add(t.lower())
            file_refs.add(t.lower())
        for op, raw in sql_ops:
            schema, table = normalize_table_name(raw)
            full = f"{schema}.{table}"
            ddl_touched_tables.add(full)
            referenced_tables.add(table)
            file_refs.add(table)
            if op == "drop_table":
                ddl_drop_tables.add(full)

        if file_refs:
            per_file_refs.append({"file": rel(path), "tables": sorted(file_refs)})

    # 命名检查：所有被引用的 table 名（忽略 schema）
    for t in sorted(referenced_tables):
        if not is_snake_case(t):
            findings.append(
                Finding(
                    kind="naming/table",
                    file="(repo-scan)",
                    identifier=t,
                    message="表名不符合 snake_case（建议仅对后端归属表强制执行）",
                )
            )

    # DDL 风险检查：仅对 DROP TABLE 做强提示（破坏性）；其他 DDL 只做清单展示
    for full in sorted(ddl_drop_tables):
        schema, table = full.split(".", 1)
        if schema != "public":
            continue
        if table in backend_owned_tables:
            continue

        # 仅标记风险，不做 hard fail
        severity = "high" if table in destructive_public_tables_requiring_manual_confirm else "medium"
        findings.append(
            Finding(
                kind=f"ddl/public_non_backend/{severity}",
                file="(sql-scan)",
                identifier=full,
                message="SQL 触达 public 非后端归属表；需人工确认 App 端不依赖/允许变更",
            )
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ownership_map_path": "docs/schemas/supabase_ownership_map.json",
        "backend_owned_tables": sorted(backend_owned_tables),
        "referenced_tables_in_repo": sorted(referenced_tables),
        "ddl_touched_tables": sorted(ddl_touched_tables),
        "ddl_drop_tables": sorted(ddl_drop_tables),
        "findings_count": len(findings),
        "findings": [f.__dict__ for f in findings],
        "per_file_references": per_file_refs,
    }
    return findings, summary


def render_markdown(summary: dict) -> str:
    lines: List[str] = []
    lines.append("# Supabase 命名与引用审计报告")
    lines.append("")
    lines.append(f"- 生成时间(UTC)：`{summary['generated_at']}`")
    lines.append(f"- 后端归属表（SSOT）：`{', '.join(summary['backend_owned_tables'])}`")
    lines.append(f"- 扫描到的表引用数量：`{len(summary['referenced_tables_in_repo'])}`")
    lines.append(f"- 发现项数量：`{summary['findings_count']}`")
    lines.append("")

    lines.append("## 发现项（Findings）")
    if not summary["findings"]:
        lines.append("")
        lines.append("- 无")
    else:
        lines.append("")
        for item in summary["findings"]:
            lines.append(f"- `{item['kind']}` `{item['identifier']}`：{item['message']}")

    lines.append("")
    lines.append("## 仓库内引用的 Supabase 表（去重）")
    lines.append("")
    for t in summary["referenced_tables_in_repo"]:
        lines.append(f"- `{t}`")

    lines.append("")
    lines.append("## DDL 触达的表（schema.table）")
    lines.append("")
    for t in summary["ddl_touched_tables"]:
        lines.append(f"- `{t}`")

    lines.append("")
    lines.append("## DDL DROP TABLE（破坏性）")
    lines.append("")
    for t in summary.get("ddl_drop_tables") or []:
        lines.append(f"- `{t}`")

    lines.append("")
    lines.append("## 单文件引用明细（节选）")
    lines.append("")
    for item in summary["per_file_references"][:40]:
        lines.append(f"- `{item['file']}`：{', '.join(item['tables'])}")
    if len(summary["per_file_references"]) > 40:
        lines.append(f"- ...（共 {len(summary['per_file_references'])} 个文件有引用）")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-md",
        default=str(PROJECT_ROOT / "docs" / "_audit" / "supabase_naming_report.md"),
        help="Markdown 报告输出路径",
    )
    parser.add_argument(
        "--out-json",
        default=str(PROJECT_ROOT / "docs" / "_audit" / "supabase_naming_report.json"),
        help="JSON 报告输出路径",
    )
    parser.add_argument(
        "--fail-on-violations",
        action="store_true",
        help="发现项不为空时返回非 0",
    )
    args = parser.parse_args()

    findings, summary = scan()

    out_md = Path(args.out_md)
    out_json = Path(args.out_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    out_md.write_text(render_markdown(summary), encoding="utf-8")
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.fail_on_violations and findings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

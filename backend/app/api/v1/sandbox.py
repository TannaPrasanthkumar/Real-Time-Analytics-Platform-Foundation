from datetime import datetime
import re
import time
import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.deps import get_db, RequireRole
from app.models.user import UserRole
from app.schemas.sandbox import (
    SandboxQueryRequest,
    SandboxQueryResponse,
    SchemaColumn,
    SchemaTable,
    SchemaResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Database Query Sandbox"])


def validate_read_only_query(sql: str) -> None:
    """Rigorous regex-based SQL validator blocking any write/destructive instructions.
    
    Checks leading keywords, ignores single-line and multi-line comments,
    and checks strict word boundaries on forbidden operations.
    """
    # 1. Strip comments cleanly to prevent SQL evasion techniques
    clean_sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)  # strip inline double dash comments
    clean_sql = re.sub(r"/\*.*?\*/", "", clean_sql, flags=re.DOTALL)  # strip multi-line slash-star comments
    clean_sql = clean_sql.strip()

    if not clean_sql:
        raise ValueError("Query string is empty.")

    # 2. Enforce read-only instruction starting structures
    # Permitted starting operators: SELECT, WITH, EXPLAIN
    match = re.match(r"^\s*(SELECT|WITH|EXPLAIN)\b", clean_sql, re.IGNORECASE)
    if not match:
        raise ValueError("Security violation: Only SELECT, WITH, or EXPLAIN statements are permitted.")

    # 3. Compile a robust list of forbidden modification instructions
    forbidden_keywords = [
        "insert", "update", "delete", "drop", "alter", "truncate", "create", 
        "replace", "grant", "revoke", "session", "transaction", "set", "execute", 
        "vacuum", "analyze"
    ]

    # Inspect the clean statement using word boundaries (\b) to avoid false hits (e.g. "datasource" or "created_at")
    for keyword in forbidden_keywords:
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, clean_sql, re.IGNORECASE):
            # Special exception: allow "explain analyze" but block generic standalone "analyze"
            if keyword == "analyze" and re.search(r"\bexplain\b", clean_sql, re.IGNORECASE):
                continue
            raise ValueError(
                f"Security violation: Forbidden database operation '{keyword.upper()}' detected."
            )


@router.get(
    "/organizations/{org_id}/sandbox/schema",
    response_model=SchemaResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def get_database_schema(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> SchemaResponse:
    """Exposes dynamic database column structures and metadata definitions.
    
    Reflects the information_schema columns in real-time, filtering out internal
    alembic records and physical database partitions to keep the schema list readable.
    """
    query = text(
        """
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name NOT LIKE 'alembic%' 
          AND table_name NOT LIKE 'events_y%'
        ORDER BY table_name, ordinal_position;
        """
    )
    
    res = await db.execute(query)
    rows = res.fetchall()

    # Aggregate columns by table
    table_map: Dict[str, List[SchemaColumn]] = {}
    for r in rows:
        tbl_name = str(r.table_name)
        col = SchemaColumn(name=str(r.column_name), data_type=str(r.data_type))
        if tbl_name not in table_map:
            table_map[tbl_name] = []
        table_map[tbl_name].append(col)

    schema_tables = [
        SchemaTable(table_name=name, columns=cols)
        for name, cols in sorted(table_map.items())
    ]
    return SchemaResponse(tables=schema_tables)


@router.post(
    "/organizations/{org_id}/sandbox/query",
    response_model=SandboxQueryResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def execute_sandbox_query(
    org_id: uuid.UUID,
    req: SandboxQueryRequest,
    db: AsyncSession = Depends(get_db)
) -> SandboxQueryResponse:
    """Executes a custom SELECT SQL query on PostgreSQL safely inside a rollback-only transaction.
    
    Runs with SET TRANSACTION READ ONLY, strips modifications, and automatically throws a rollback
    to guarantee zero side-effects on persistent tables. Supports detailed EXPLAIN query plans.
    """
    start_time = time.perf_counter()

    # 1. Run rigorous client-side string validators
    try:
        validate_read_only_query(req.sql)
    except ValueError as ve:
        logger.warning("Blocked sandbox query request due to security bounds", sql=req.sql, error=str(ve))
        return SandboxQueryResponse(
            success=False,
            error=str(ve),
            execution_time_ms=0.0
        )

    columns: List[str] = []
    rows: List[Dict[str, Any]] = []
    explain_plan: Any = None
    error_msg: str = None

    try:
        # Start a nested sub-transaction block (Savepoint) for rollback isolation
        async with db.begin_nested() as nested_tx:
            # Enforce read-only constraint at database transaction layer
            await db.execute(text("SET TRANSACTION READ ONLY"))
            
            if req.explain:
                # Wrap the query inside a rich JSON-formatted execution analyzer
                explain_query = f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) {req.sql}"
                result = await db.execute(text(explain_query))
                explain_plan = result.scalar()  # Contains the raw planning array list
            else:
                # Execute the normal read-only query
                result = await db.execute(text(req.sql))
                columns = list(result.keys())
                
                # Fetch row outputs and safely serialize standard binary/custom types to JSON strings
                for row in result.fetchall():
                    row_dict = {}
                    for col, val in zip(columns, row):
                        if isinstance(val, (datetime, uuid.UUID)):
                            row_dict[col] = str(val)
                        elif isinstance(val, (dict, list)):
                            row_dict[col] = val
                        elif val is None or isinstance(val, (int, float, str, bool)):
                            row_dict[col] = val
                        else:
                            row_dict[col] = str(val)
                    rows.append(row_dict)
            
            # Explicitly force rollback to clean up all engine locks and ensure absolute database state immutability
            await nested_tx.rollback()
            
    except Exception as e:
        error_msg = str(e)
        logger.error(
            "SQL Sandbox execution failure encountered",
            query=req.sql,
            error=error_msg,
            org_id=str(org_id),
        )

    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000.0

    return SandboxQueryResponse(
        success=error_msg is None,
        columns=columns,
        rows=rows,
        execution_time_ms=duration_ms,
        explain_plan=explain_plan,
        error=error_msg
    )

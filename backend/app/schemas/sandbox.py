from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SandboxQueryRequest(BaseModel):
    """Pydantic model representing a custom query request in the SQL sandbox."""
    sql: str = Field(..., description="Raw SELECT or read-only SQL query string")
    explain: bool = Field(default=False, description="Request execution plan analysis if True")


class SandboxQueryResponse(BaseModel):
    """Pydantic model returning custom query result sets and performance analytics."""
    success: bool = Field(..., description="Indicates whether query succeeded")
    columns: List[str] = Field(default_factory=list, description="List of column names returned")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="Spreadsheet rows mapped as key-value column pairs")
    execution_time_ms: float = Field(..., description="Execution latency duration in milliseconds")
    explain_plan: Optional[List[Dict[str, Any]]] = Field(default=None, description="PostgreSQL query execution plan from EXPLAIN")
    error: Optional[str] = Field(default=None, description="Detailed error message if execution failed")


class SchemaColumn(BaseModel):
    """Pydantic representation of a single database column structure."""
    name: str = Field(..., description="Column name")
    data_type: str = Field(..., description="PostgreSQL column data type")


class SchemaTable(BaseModel):
    """Pydantic representation of a single database table structural layout."""
    table_name: str = Field(..., description="Table name")
    columns: List[SchemaColumn] = Field(..., description="List of columns under the table")


class SchemaResponse(BaseModel):
    """Pydantic representation of discovered table layouts for the side panel explorer."""
    tables: List[SchemaTable] = Field(..., description="Dynamic list of database tables and fields")

import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Add local path to import application configuration
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings


async def test_database_connection() -> None:
    """Verifies settings mapping, loads async engines, and runs a diagnostic query."""
    print("==============================================================")
    print("Database Telemetry Diagnostic Tool")
    print("==============================================================")
    print(f"Project Target:  {settings.PROJECT_NAME}")
    print(f"Environment:     {settings.ENVIRONMENT}")
    print(f"Database Target: {settings.DATABASE_URL.split('@')[-1]}")  # Redact secrets
    print("==============================================================")
    print("[1/3] Loading Pydantic Settings ... SUCCESS")
    
    try:
        print("[2/3] Constructing Async SQLAlchemy Engine ...")
        engine = create_async_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True
        )
        print("      Engine constructed successfully.")
        
        print("[3/3] Establishing socket connection and executing query ...")
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 'PostgreSQL asyncpg driver connection operational!'"))
            row = result.fetchone()
            print(f"      DATABASE RESPONSE: {row[0]}")
            
        print("==============================================================")
        print("🎉 SUCCESS: Async Database Layer verified successfully!")
        print("==============================================================")
        await engine.dispose()
        
    except Exception as e:
        print("\n==============================================================")
        print("❌ FAILURE: Unable to establish database connection.")
        print(f"Error Details: {str(e)}")
        print("==============================================================")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_database_connection())

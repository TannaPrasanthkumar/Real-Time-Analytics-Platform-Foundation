import sys
import os
import uuid
import asyncio
from datetime import datetime, timezone
from sqlalchemy import delete

# Add local path to import configuration modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.logging import configure_logging, correlation_id_ctx
import app.models.base
from app.db.session import async_session, engine
from app.models.organization import Organization
from app.models.event import Event
from app.worker.tasks.diagnostics import verify_worker_health
from app.worker.tasks.ingestion import ingest_event_batch


async def run_worker_tests():
    """Unit-style test verifying task registrations, trace headers, and synchronous run state."""
    configure_logging()
    
    print("==============================================================")
    print("Celery Background Worker Telemetry Verification (Async DB)")
    print("==============================================================")
    
    # 1. Generate active trace ID
    trace_id = str(uuid.uuid4())
    token = correlation_id_ctx.set(trace_id)
    print(f"Propagating Correlation Trace ID: {trace_id}")
    
    try:
        # 2. Test verify_worker_health Task execution
        print("\n[1/3] Triggering Worker Diagnostics Health Task ...")
        # Run standard local apply context (simulates worker thread consumption)
        result = verify_worker_health.apply()
        
        print(f"      Execution State:  {result.state}")
        print(f"      Result Payload:   {result.result}")
        assert result.state == "SUCCESS"
        assert result.result["status"] == "operational"
        
        # 3. Create active organization to pass foreign key constraint checks
        print("\n[2/3] Seeding temporary testing Organization in database...")
        org_id = uuid.uuid4()
        async with async_session() as session:
            await session.execute(delete(Organization).where(Organization.slug == "worker-test-org"))
            # Make sure we also delete any events matching this org if they somehow exist
            await session.execute(delete(Event).where(Event.organization_id == org_id))
            
            org = Organization(
                id=org_id,
                name="Worker Test Org",
                slug="worker-test-org"
            )
            session.add(org)
            await session.commit()
        print(f"      Organization Seeded. ID: {org_id}")

        # 4. Test Ingestion batch task execution
        print("\n[3/3] Triggering Ingestion Batch Processor Task ...")
        mock_events = [
            {
                "id": str(uuid.uuid4()),
                "organization_id": str(org_id),
                "data_source_id": None,
                "event_name": "user.login",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {"device": "mobile", "ip": "127.0.0.1"}
            },
            {
                "id": str(uuid.uuid4()),
                "organization_id": str(org_id),
                "data_source_id": None,
                "event_name": "page.view",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {"url": "/dashboard"}
            }
        ]
        
        ingest_result = ingest_event_batch.apply(args=[mock_events])
        
        print(f"      Execution State:  {ingest_result.state}")
        print(f"      Result Payload:   {ingest_result.result}")
        assert ingest_result.state == "SUCCESS"
        assert ingest_result.result["processed_records"] == 2
        
        # 5. Test Database partition maintenance daemon task execution
        print("\n[4/4] Triggering Database Partition Maintenance Daemon Task ...")
        from app.worker.tasks.db_maintenance import preprovision_partitions
        maint_result = preprovision_partitions.apply()
        print(f"      Execution State:  {maint_result.state}")
        print(f"      Result Payload:   {maint_result.result}")
        assert maint_result.state == "SUCCESS"
        assert maint_result.result["success"] is True
        
        # Clean up database
        print("\nCleaning up temporary testing Organization and Events...")
        async with async_session() as session:
            await session.execute(delete(Event).where(Event.organization_id == org_id))
            await session.execute(delete(Organization).where(Organization.id == org_id))
            await session.commit()
        print("      Cleanup complete.")

        print("==============================================================")
        print("🎉 SUCCESS: Worker Tasks & Database ingestion verified!")
        print("==============================================================")
        
    except Exception as e:
        print("\n==============================================================")
        print("❌ FAILURE during integration testing.")
        print(f"Error Details: {str(e)}")
        print("==============================================================")
        sys.exit(1)
    finally:
        correlation_id_ctx.reset(token)
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_worker_tests())


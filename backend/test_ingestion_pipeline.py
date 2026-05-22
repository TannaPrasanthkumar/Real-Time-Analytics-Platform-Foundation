import asyncio
import sys
import os
import httpx
import uuid
import hashlib
from datetime import datetime, timezone
from sqlalchemy import delete, select

# Add local path to import application modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import app.models.base
from app.db.session import async_session, engine
from app.models.user import User, UserOrganization, UserRole
from app.models.organization import Organization
from app.models.data_source import DataSource
from app.models.api_key import APIKey
from app.models.event import Event
from app.worker.celery_app import celery_app
from app.main import app

# Set Celery to Eager mode so tasks are executed synchronously in the test process
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

TEST_EMAIL = "ingest-test@example.com"
TEST_ORG_SLUG = "ingest-test-org"


async def clean_database() -> None:
    """Pre-cleans any testing data to ensure deterministic execution."""
    print("      Cleaning database testing records...")
    async with async_session() as session:
        # Resolve test organization id
        res = await session.execute(select(Organization).where(Organization.slug == TEST_ORG_SLUG))
        org = res.scalar_one_or_none()
        
        if org:
            # Cascading deletion manually to avoid database locking or timing issues
            await session.execute(delete(Event).where(Event.organization_id == org.id))
            await session.execute(delete(APIKey).where(APIKey.organization_id == org.id))
            await session.execute(delete(DataSource).where(DataSource.organization_id == org.id))
            await session.execute(delete(UserOrganization).where(UserOrganization.organization_id == org.id))
            await session.execute(delete(Organization).where(Organization.id == org.id))
            
        await session.execute(delete(User).where(User.email == TEST_EMAIL))
        await session.commit()
    print("      Database cleaned successfully.")


async def run_e2e_ingestion_pipeline():
    """Runs a complete end-to-end integration and security test suite on Phase 3 pipelines."""
    print("==============================================================")
    print("🚀 Running E2E Data Ingestion & Sources Integration Suite")
    print("==============================================================")

    # 1. Clean the database
    print("[1/9] Initializing clean state...")
    await clean_database()

    # Create local client hitting the application in eager celery mode
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        try:
            # 2. Signup Test User
            print("[2/9] Registering test organization and analyst profile...")
            signup_payload = {
                "email": TEST_EMAIL,
                "password": "SecurePassword123",
                "full_name": "Ingest Analyst",
                "organization_name": "Ingest Test Org"
            }
            res = await client.post("/api/v1/auth/signup", json=signup_payload)
            assert res.status_code == 201, f"Signup failed: {res.text}"
            
            signup_data = res.json()
            access_token = signup_data["access_token"]
            org_id_str = signup_data["default_organization_id"]
            org_id = uuid.UUID(org_id_str)
            
            auth_headers = {"Authorization": f"Bearer {access_token}"}
            print(f"      Auth token issued. Organization ID: {org_id}")

            # 3. Create Data Sources (API, CSV, Webhook)
            print("[3/9] Creating multiple ingestion Data Sources...")
            
            # API Data Source
            res = await client.post(
                f"/api/v1/organizations/{org_id}/data-sources",
                json={"name": "Production API Source", "type": "api", "config": {}},
                headers=auth_headers
            )
            assert res.status_code == 201, res.text
            api_source_id = uuid.UUID(res.json()["id"])
            
            # CSV Data Source
            res = await client.post(
                f"/api/v1/organizations/{org_id}/data-sources",
                json={"name": "Bulk CSV Ingest", "type": "csv", "config": {}},
                headers=auth_headers
            )
            assert res.status_code == 201, res.text
            csv_source_id = uuid.UUID(res.json()["id"])

            # Webhook Data Source
            res = await client.post(
                f"/api/v1/organizations/{org_id}/data-sources",
                json={"name": "GitHub Event Webhook", "type": "webhook", "config": {"event_name_path": "event", "timestamp_path": "timestamp"}},
                headers=auth_headers
            )
            assert res.status_code == 201, res.text
            webhook_source_id = uuid.UUID(res.json()["id"])
            
            print("      Data Sources created successfully (API, CSV, Webhook).")

            # 4. Generate API Key
            print("[4/9] Provisioning ingestion API Key...")
            res = await client.post(
                f"/api/v1/organizations/{org_id}/api-keys",
                json={"name": "Live Ingest Key"},
                headers=auth_headers
            )
            assert res.status_code == 201, res.text
            key_data = res.json()
            raw_api_key = key_data["raw_key"]
            api_key_id = uuid.UUID(key_data["id"])
            prefix = key_data["prefix"]
            
            ingest_headers = {"X-API-Key": raw_api_key}
            print(f"      API Key provisioned. Prefix: {prefix}")

            # 5. Test Single and Batch Event Ingestion
            print("[5/9] Testing API-driven single event ingestion...")
            single_payload = {
                "event_name": "user.login",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {"ip": "127.0.0.1", "device": "desktop"},
                "data_source_id": str(api_source_id)
            }
            res = await client.post("/api/v1/ingest", json=single_payload, headers=ingest_headers)
            assert res.status_code == 202, res.text
            assert res.json()["success"] is True
            print("      Single event ingestion request accepted.")

            print("      Testing API-driven batch event ingestion...")
            batch_payload = [
                {
                    "event_name": "button.click",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": {"button_id": "submit-btn"},
                    "data_source_id": str(api_source_id)
                },
                {
                    "event_name": "page.view",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": {"url": "/home"},
                    "data_source_id": str(api_source_id)
                }
            ]
            res = await client.post("/api/v1/ingest/batch", json=batch_payload, headers=ingest_headers)
            assert res.status_code == 202, res.text
            assert res.json()["success"] is True
            print("      Batch event ingestion request accepted.")

            # 6. Test Webhook Ingestion Receiver
            print("[6/9] Testing webhook payload mapping receiver...")
            webhook_payload = {
                "event": "push",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ref": "refs/heads/main",
                "repository": {"name": "SaaS-Analytics"}
            }
            res = await client.post(f"/api/v1/ingest/webhooks/{webhook_source_id}", json=webhook_payload)
            assert res.status_code == 202, res.text
            assert res.json()["success"] is True
            print("      Webhook payload mapping request accepted.")

            # 7. Test CSV Upload Parsing
            print("[7/9] Testing CSV file parsing and ingestion...")
            csv_content = (
                "event_name,timestamp,user_id,plan\n"
                "csv.import.first,2026-05-21T12:00:00+00:00,user_99,enterprise\n"
                "csv.import.second,2026-05-21T12:05:00+00:00,user_100,free\n"
            )
            files = {"file": ("events.csv", csv_content, "text/csv")}
            res = await client.post(
                f"/api/v1/organizations/{org_id}/data-sources/{csv_source_id}/upload-csv",
                files=files,
                headers=auth_headers
            )
            assert res.status_code == 200, res.text
            assert res.json()["success"] is True
            assert res.json()["parsed_records"] == 2
            print("      CSV file upload, parsing, and ingestion succeeded.")

            # 8. Test Redis Rate Limiter
            print("[8/9] Testing Redis-backed sliding window rate limiting...")
            # We seed the rate limit key in Redis directly to simulate breach (avoiding firing 1000 requests)
            import redis.asyncio as aioredis
            from app.core.config import settings
            
            redis_client = aioredis.from_url(settings.REDIS_URL, socket_timeout=2.0)
            try:
                minute_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
                redis_key = f"rate_limit:{prefix}:{minute_str}"
                
                # Artificially set limit breach count to 1005 (limit is 1000)
                await redis_client.set(redis_key, 1005)
                
                # Make another request which should be rejected
                lim_res = await client.post("/api/v1/ingest", json=single_payload, headers=ingest_headers)
                assert lim_res.status_code == 429, f"Expected 429 Rate Limited, got {lim_res.status_code}"
                
                # Support both standard FastAPI detail responses and custom wrapped business message exceptions
                res_body = lim_res.json()
                error_msg = None
                if "error" in res_body and isinstance(res_body["error"], dict):
                    error_msg = res_body["error"].get("message")
                if not error_msg:
                    error_msg = res_body.get("message") or res_body.get("detail")
                
                assert error_msg is not None, f"Response body does not contain message/detail: {res_body}"
                assert "Rate limit" in error_msg or "rate limit" in error_msg.lower(), f"Expected rate limit message, got: {error_msg}"
                print("      SUCCESS: Redis-backed rate limiter blocked request with 429.")
                
                # Clean up rate limit key to restore access
                await redis_client.delete(redis_key)
                
                # Make another request which should pass now
                lim_res_pass = await client.post("/api/v1/ingest", json=single_payload, headers=ingest_headers)
                assert lim_res_pass.status_code == 202
                print("      SUCCESS: Rate limit counter successfully cleared and restored.")
            finally:
                await redis_client.close()

            # 9. Query & Verify Historical Event Partition Distribution
            print("[9/9] Fetching and verifying historical event range distribution...")
            # Fetch organization events via historical query API
            res = await client.get(f"/api/v1/organizations/{org_id}/events", headers=auth_headers)
            assert res.status_code == 200, res.text
            events = res.json()
            
            # Print historical event details
            print(f"      Total Committed Events Retreived: {len(events)}")
            for event in events:
                print(f"      - Event: {event['event_name']} | Timestamp: {event['timestamp']} | Payload: {event['payload']}")
                
            # Assert correct event counts are committed
            # We expect: 1 (single) + 2 (batch) + 1 (webhook) + 2 (CSV) + 1 (rate-limit-restore) = 7 events total!
            assert len(events) == 7, f"Expected 7 events, got {len(events)}"
            
            # Let's perform a direct range partition validation against the database
            print("      Checking database range partition counts...")
            async with async_session() as session:
                from sqlalchemy import text
                db_res = await session.execute(
                    text("SELECT tableoid::regclass::text, count(*) FROM events GROUP BY tableoid;")
                )
                rows = db_res.fetchall()
                print("      PostgreSQL Partition Distribution:")
                for row in rows:
                    print(f"        - Partition Table: {row[0]} | Record Count: {row[1]}")
                    assert "events_y2026" in row[0], f"Events should be in monthly range partitions, got: {row[0]}"
            
            print("==============================================================")
            print("🎉 ALL TESTS PASSED: Time-series database partition pipeline is 100% correct!")
            print("==============================================================")

        except Exception as e:
            print("\n==============================================================")
            print("❌ FAILURE during ingestion pipeline integration testing.")
            print(f"Error Details: {str(e)}")
            print("==============================================================")
            sys.exit(1)
        finally:
            # Clean up testing data
            print("Cleaning up database test structures...")
            await clean_database()
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_e2e_ingestion_pipeline())

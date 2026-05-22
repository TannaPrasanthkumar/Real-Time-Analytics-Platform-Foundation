import asyncio
import sys
import os
import httpx
import uuid
from datetime import datetime, timedelta, timezone
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

TEST_EMAIL = "analytics-test@example.com"
TEST_ORG_SLUG = "analytics-test-org"

CROSS_EMAIL = "cross-tenant@example.com"
CROSS_ORG_SLUG = "cross-test-org"


async def clean_database() -> None:
    """Pre-cleans any testing data to ensure deterministic execution."""
    print("      Cleaning database testing records...")
    async with async_session() as session:
        for slug in [TEST_ORG_SLUG, CROSS_ORG_SLUG]:
            res = await session.execute(select(Organization).where(Organization.slug == slug))
            org = res.scalar_one_or_none()
            if org:
                await session.execute(delete(Event).where(Event.organization_id == org.id))
                await session.execute(delete(APIKey).where(APIKey.organization_id == org.id))
                await session.execute(delete(DataSource).where(DataSource.organization_id == org.id))
                await session.execute(delete(UserOrganization).where(UserOrganization.organization_id == org.id))
                await session.execute(delete(Organization).where(Organization.id == org.id))
                
        for email in [TEST_EMAIL, CROSS_EMAIL]:
            await session.execute(delete(User).where(User.email == email))
            
        await session.commit()
    print("      Database cleaned successfully.")


async def run_analytics_verification_suite():
    """Runs a complete analytics engine mathematical correctness and performance cache verification suite."""
    print("==============================================================")
    print("🚀 Starting SaaS Analytics Engine & Caching Verification Suite")
    print("==============================================================")

    # 1. Clean the database
    print("[1/6] Initializing clean state...")
    await clean_database()

    # Create local client hitting the application in eager celery mode
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        try:
            # 2. Signup Test Users & Provision Tenants
            print("[2/6] Provisioning dual-tenant environments & API access...")
            
            # Tenant A (Target Org)
            signup_a = {
                "email": TEST_EMAIL,
                "password": "SecurePassword123",
                "full_name": "Analytics Lead",
                "organization_name": "Analytics Test Org"
            }
            res = await client.post("/api/v1/auth/signup", json=signup_a)
            assert res.status_code == 201, f"Tenant A Signup failed: {res.text}"
            signup_data_a = res.json()
            access_token_a = signup_data_a["access_token"]
            org_id_a = uuid.UUID(signup_data_a["default_organization_id"])
            auth_headers_a = {"Authorization": f"Bearer {access_token_a}"}

            # Tenant B (Cross Org)
            signup_b = {
                "email": CROSS_EMAIL,
                "password": "SecurePassword123",
                "full_name": "Cross Tenant User",
                "organization_name": "Cross Test Org"
            }
            res = await client.post("/api/v1/auth/signup", json=signup_b)
            assert res.status_code == 201, f"Tenant B Signup failed: {res.text}"
            signup_data_b = res.json()
            access_token_b = signup_data_b["access_token"]
            org_id_b = uuid.UUID(signup_data_b["default_organization_id"])
            auth_headers_b = {"Authorization": f"Bearer {access_token_b}"}

            # Provision API Key under Tenant A
            res = await client.post(
                f"/api/v1/organizations/{org_id_a}/api-keys",
                json={"name": "Analytics API Ingest Key"},
                headers=auth_headers_a
            )
            assert res.status_code == 201, res.text
            raw_key_a = res.json()["raw_key"]
            ingest_headers_a = {"X-API-Key": raw_key_a}

            print("      Dual-tenant registration and API keys successfully verified.")

            # 3. Seed Mathematical Mock Event Streams
            print("[3/6] Seeding multi-period time-series analytics event logs...")
            now = datetime.now(timezone.utc)
            
            # Current Period: Last 24 Hours
            # Prior Period: 24 Hours to 48 Hours
            
            # --- Seeding CURRENT Period (Totals: 6 Pageviews, 3 UVs, 3 Sessions, 1 Bounce) ---
            # Session 1: duration = 600s (10 minutes), user = user_1, 3 pageviews
            events_current = [
                {
                    "event_name": "page_view",
                    "timestamp": (now - timedelta(hours=2)).isoformat(),
                    "payload": {"session_id": "sess_1", "user_id": "user_1", "browser": "Chrome", "path": "/home"}
                },
                {
                    "event_name": "page_view",
                    "timestamp": (now - timedelta(hours=2, minutes=5)).isoformat(),
                    "payload": {"session_id": "sess_1", "user_id": "user_1", "browser": "Chrome", "path": "/pricing"}
                },
                {
                    "event_name": "page_view",
                    "timestamp": (now - timedelta(hours=2, minutes=10)).isoformat(),
                    "payload": {"session_id": "sess_1", "user_id": "user_1", "browser": "Chrome", "path": "/docs"}
                },
                # Session 2: duration = 0s (Bounced!), user = user_2, 1 pageview
                {
                    "event_name": "page_view",
                    "timestamp": (now - timedelta(hours=4)).isoformat(),
                    "payload": {"session_id": "sess_2", "user_id": "user_2", "browser": "Firefox", "path": "/home"}
                },
                # Session 3: duration = 300s (5 minutes), user = user_3, 2 pageviews
                {
                    "event_name": "page_view",
                    "timestamp": (now - timedelta(hours=6)).isoformat(),
                    "payload": {"session_id": "sess_3", "user_id": "user_3", "browser": "Chrome", "path": "/pricing"}
                },
                {
                    "event_name": "page_view",
                    "timestamp": (now - timedelta(hours=6, minutes=5)).isoformat(),
                    "payload": {"session_id": "sess_3", "user_id": "user_3", "browser": "Chrome", "path": "/docs"}
                }
            ]

            # --- Seeding PRIOR Period (Totals: 3 Pageviews, 2 UVs, 2 Sessions, 1 Bounce) ---
            # Session 4: duration = 200s, user = user_4, 2 pageviews
            events_prior = [
                {
                    "event_name": "page_view",
                    "timestamp": (now - timedelta(hours=26)).isoformat(),
                    "payload": {"session_id": "sess_4", "user_id": "user_4", "browser": "Safari", "path": "/home"}
                },
                {
                    "event_name": "page_view",
                    "timestamp": (now - timedelta(hours=26, minutes=3, seconds=20)).isoformat(),
                    "payload": {"session_id": "sess_4", "user_id": "user_4", "browser": "Safari", "path": "/docs"}
                },
                # Session 5: duration = 0s (Bounced!), user = user_5, 1 pageview
                {
                    "event_name": "page_view",
                    "timestamp": (now - timedelta(hours=30)).isoformat(),
                    "payload": {"session_id": "sess_5", "user_id": "user_5", "browser": "Firefox", "path": "/home"}
                }
            ]

            # Ingest current events
            for payload in events_current:
                res = await client.post("/api/v1/ingest", json=payload, headers=ingest_headers_a)
                assert res.status_code == 202, res.text
                
            # Ingest prior events
            for payload in events_prior:
                res = await client.post("/api/v1/ingest", json=payload, headers=ingest_headers_a)
                assert res.status_code == 202, res.text

            print("      Analytical event data seeded successfully.")

            # 4. Verify Metrics Overview Calculations & PoP Deltas
            print("[4/6] Testing analytical aggregates overview and PoP percentage delta math...")
            
            # Start/End query parameters: past 24 hours
            start_param = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
            end_param = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            res = await client.get(
                f"/api/v1/organizations/{org_id_a}/analytics/overview?start_time={start_param}&end_time={end_param}&use_cache=False",
                headers=auth_headers_a
            )
            assert res.status_code == 200, res.text
            overview = res.json()
            
            # Mathematical Assertions:
            # Page views = 6
            # Unique visitors = 3
            # Bounce rate = 33.33% (1 session bounced out of 3 sessions)
            # Avg session duration = (600s + 0s + 300s) / 3 sessions = 300.0 seconds
            assert overview["page_views"] == 6, f"Expected 6 Pageviews, got {overview['page_views']}"
            assert overview["unique_visitors"] == 3, f"Expected 3 Visitors, got {overview['unique_visitors']}"
            assert round(overview["bounce_rate"], 2) == 33.33, f"Expected 33.33% bounce, got {overview['bounce_rate']}"
            assert overview["avg_session_duration"] == 300.0, f"Expected 300s duration, got {overview['avg_session_duration']}"

            # PoP changes relative to prior 24 hours:
            # Prior Page views = 3. Delta = (6 - 3) / 3 * 100% = +100%
            # Prior UVs = 2. Delta = (3 - 2) / 2 * 100% = +50%
            # Prior Bounce rate = 50.0% (1 bounced out of 2). Delta = (33.33 - 50.0) / 50.0 = -33.34%
            # Prior Avg session duration = (200s + 0s) / 2 = 100s. Delta = (300s - 100s) / 100s = +200%
            assert overview["page_views_change"] == 100.0, f"Expected +100% PV change, got {overview['page_views_change']}"
            assert overview["unique_visitors_change"] == 50.0, f"Expected +50% UV change, got {overview['unique_visitors_change']}"
            assert round(overview["bounce_rate_change"], 2) == -33.33, f"Expected -33.33% BR change, got {overview['bounce_rate_change']}"
            assert overview["avg_session_duration_change"] == 200.0, f"Expected +200% ASD change, got {overview['avg_session_duration_change']}"

            print("      SUCCESS: Analytical overview and PoP deltas are mathematically correct!")
            print(f"        - Page Views:           {overview['page_views']} (Change: {overview['page_views_change']}%)")
            print(f"        - Unique Visitors:      {overview['unique_visitors']} (Change: {overview['unique_visitors_change']}%)")
            print(f"        - Bounce Rate:          {round(overview['bounce_rate'], 2)}% (Change: {overview['bounce_rate_change']}%)")
            print(f"        - Avg Session Duration: {overview['avg_session_duration']}s (Change: {overview['avg_session_duration_change']}%)")

            # 5. Verify Timeseries Groupings, Breakdown Segments, and Caching Tier
            print("[5/6] Testing timeseries groupings, property breakdowns, and cache performance...")
            
            # Timeseries page_views grouped by hour
            res = await client.get(
                f"/api/v1/organizations/{org_id_a}/analytics/timeseries?metric=page_views&interval=hour&start_time={start_param}&end_time={end_param}&use_cache=False",
                headers=auth_headers_a
            )
            assert res.status_code == 200, res.text
            ts_res = res.json()
            assert ts_res["metric"] == "page_views"
            assert len(ts_res["points"]) > 0, "Timeseries points list empty"
            print("      SUCCESS: Hour-bucket timeseries returned successfully.")

            # Property breakdown by browser
            res = await client.get(
                f"/api/v1/organizations/{org_id_a}/analytics/breakdown?property_key=browser&start_time={start_param}&end_time={end_param}&use_cache=False",
                headers=auth_headers_a
            )
            assert res.status_code == 200, res.text
            breakdown = res.json()
            assert breakdown["property_key"] == "browser"
            # In the past 24 hours:
            # Session 1 (3 Chrome), Session 2 (1 Firefox), Session 3 (2 Chrome). Total = 5 Chrome, 1 Firefox
            items = breakdown["items"]
            assert len(items) == 2
            assert items[0]["label"] == "Chrome"
            assert items[0]["count"] == 5
            assert items[0]["percentage"] == 83.33 or round(items[0]["percentage"], 2) == 83.33
            assert items[1]["label"] == "Firefox"
            assert items[1]["count"] == 1
            assert items[1]["percentage"] == 16.67 or round(items[1]["percentage"], 2) == 16.67
            print("      SUCCESS: Property segment breakdown returned mathematically correct counts.")

            # Redis Cache Verification
            print("      Running Redis caching validation...")
            
            # 1st Query: Query with use_cache=True (should compute and set cache)
            res_c1 = await client.get(
                f"/api/v1/organizations/{org_id_a}/analytics/overview?start_time={start_param}&end_time={end_param}&use_cache=True",
                headers=auth_headers_a
            )
            assert res_c1.status_code == 200
            pv_count_1 = res_c1.json()["page_views"]
            
            # Seed another event (should increase pageviews to 7 in db)
            extra_event = {
                "event_name": "page_view",
                "timestamp": (now - timedelta(hours=1)).isoformat(),
                "payload": {"session_id": "sess_1", "user_id": "user_1", "browser": "Chrome", "path": "/pricing"}
            }
            res_ing = await client.post("/api/v1/ingest", json=extra_event, headers=ingest_headers_a)
            assert res_ing.status_code == 202

            # 2nd Query: Query with use_cache=True (should fetch cached copy representing 6 pageviews, NOT 7)
            res_c2 = await client.get(
                f"/api/v1/organizations/{org_id_a}/analytics/overview?start_time={start_param}&end_time={end_param}&use_cache=True",
                headers=auth_headers_a
            )
            assert res_c2.status_code == 200
            pv_count_2 = res_c2.json()["page_views"]
            assert pv_count_2 == pv_count_1, f"Expected cache hit returning {pv_count_1}, got {pv_count_2}"
            print("      SUCCESS: Verified Redis cache hit isolation (database updates ignored).")

            # 3rd Query: Query with use_cache=False (should bypass cache and fetch actual count of 7 pageviews)
            res_c3 = await client.get(
                f"/api/v1/organizations/{org_id_a}/analytics/overview?start_time={start_param}&end_time={end_param}&use_cache=False",
                headers=auth_headers_a
            )
            assert res_c3.status_code == 200
            pv_count_3 = res_c3.json()["page_views"]
            assert pv_count_3 == 7, f"Expected cache bypass fetching 7 pageviews, got {pv_count_3}"
            print("      SUCCESS: Verified cache bypass fetching updated aggregates.")

            # 6. Verify Tenant Isolation Boundaries & RBAC Access Lockups
            print("[6/6] Testing multi-tenant boundary isolation and RBAC security lockups...")
            
            # Tenant B (Cross Tenant) attempting to fetch Tenant A's analytics metrics overview
            res_cross = await client.get(
                f"/api/v1/organizations/{org_id_a}/analytics/overview?start_time={start_param}&end_time={end_param}",
                headers=auth_headers_b
            )
            assert res_cross.status_code == 403, f"Expected 403 Forbidden cross-tenant access, got {res_cross.status_code}"
            
            # Unauthenticated endpoint access check
            res_unauth = await client.get(
                f"/api/v1/organizations/{org_id_a}/analytics/overview?start_time={start_param}&end_time={end_param}"
            )
            assert res_unauth.status_code == 401, f"Expected 401 Unauthorized unauthenticated access, got {res_unauth.status_code}"
            
            print("      SUCCESS: Verified multi-tenant bounds and access security protections.")
            
            print("==============================================================")
            print("🎉 ALL TESTS PASSED: Analytics Engine & Caching are 100% correct!")
            print("==============================================================")

        except Exception as e:
            print("\n==============================================================")
            print("❌ FAILURE during analytics engine integration testing.")
            print(f"Error Details: {str(e)}")
            print("==============================================================")
            sys.exit(1)
        finally:
            # Clean up testing data
            print("Cleaning up database test structures...")
            await clean_database()
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_analytics_verification_suite())

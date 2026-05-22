import asyncio
import sys
import os
import httpx
import uuid
import traceback
from datetime import datetime, timezone, timedelta
from sqlalchemy import delete, select, text

# Add local path to import application modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import app.models.base
from app.db.session import async_session, engine
from app.models.user import User, UserOrganization, UserRole
from app.models.organization import Organization
from app.models.api_key import APIKey
from app.models.event import Event
from app.models.data_source import DataSource
from app.models.dashboard import Dashboard, Widget
from app.models.report import ReportSchedule, ReportHistory
from app.core.security import get_password_hash
from app.worker.tasks.report import _execute_scheduled_reports_evaluation, _execute_single_report_generation

# URLs for real running backend service in Docker Compose
BASE_URL = "http://127.0.0.1:8000/api/v1"

TEST_ORG_SLUG = "reports-test-org"
CROSS_ORG_SLUG = "reports-cross-org"

TEST_OWNER_EMAIL = "reports-owner@example.com"
TEST_ANALYST_EMAIL = "reports-analyst@example.com"
TEST_VIEWER_EMAIL = "reports-viewer@example.com"
CROSS_OWNER_EMAIL = "reports-cross-owner@example.com"


async def clean_database() -> None:
    """Pre-cleans any testing data to ensure deterministic execution."""
    print("      Cleaning database testing records...")
    async with async_session() as session:
        for slug in [TEST_ORG_SLUG, CROSS_ORG_SLUG]:
            res = await session.execute(select(Organization).where(Organization.slug == slug))
            org = res.scalar_one_or_none()
            if org:
                # Delete report histories and schedules
                await session.execute(delete(ReportHistory).where(ReportHistory.organization_id == org.id))
                await session.execute(delete(ReportSchedule).where(ReportSchedule.organization_id == org.id))
                await session.execute(delete(Widget).where(Widget.dashboard_id.in_(
                    select(Dashboard.id).where(Dashboard.organization_id == org.id)
                )))
                await session.execute(delete(Dashboard).where(Dashboard.organization_id == org.id))
                await session.execute(delete(Event).where(Event.organization_id == org.id))
                await session.execute(delete(APIKey).where(APIKey.organization_id == org.id))
                await session.execute(delete(DataSource).where(DataSource.organization_id == org.id))
                await session.execute(delete(UserOrganization).where(UserOrganization.organization_id == org.id))
                await session.execute(delete(Organization).where(Organization.id == org.id))
                
        for email in [TEST_OWNER_EMAIL, TEST_ANALYST_EMAIL, TEST_VIEWER_EMAIL, CROSS_OWNER_EMAIL]:
            res_user = await session.execute(select(User).where(User.email == email))
            user = res_user.scalar_one_or_none()
            if user:
                await session.execute(delete(UserOrganization).where(UserOrganization.user_id == user.id))
                await session.execute(delete(User).where(User.id == user.id))
                
        await session.commit()
    print("      Database cleaned successfully.")


async def seed_analyst_and_viewer(org_id: uuid.UUID) -> None:
    """Seeds analyst and viewer users inside target organization."""
    print("      Seeding Analyst and Viewer profiles in DB...")
    async with async_session() as session:
        hashed_pwd = get_password_hash("SecurePassword123")
        
        analyst = User(
            email=TEST_ANALYST_EMAIL,
            hashed_password=hashed_pwd,
            full_name="Reports Analyst",
            is_active=True,
            is_superuser=False
        )
        session.add(analyst)
        
        viewer = User(
            email=TEST_VIEWER_EMAIL,
            hashed_password=hashed_pwd,
            full_name="Reports Viewer",
            is_active=True,
            is_superuser=False
        )
        session.add(viewer)
        await session.flush()
        
        m1 = UserOrganization(
            user_id=analyst.id,
            organization_id=org_id,
            role=UserRole.ANALYST
        )
        m2 = UserOrganization(
            user_id=viewer.id,
            organization_id=org_id,
            role=UserRole.VIEWER
        )
        session.add(m1)
        session.add(m2)
        await session.commit()
    print("      Analyst and Viewer profiles seeded successfully.")


async def run_scheduled_reports_verification_suite() -> None:
    """Executes the E2E verification suite for Scheduled Reports."""
    print("==============================================================")
    print("🚀 Starting Scheduled Reports E2E Verification Suite")
    print("==============================================================")

    # 1. Clean Database
    print("[1/7] Initializing database clean state...")
    await clean_database()
    
    await asyncio.sleep(0.5)

    async with httpx.AsyncClient() as client:
        try:
            # 2. Provision Tenants & Fetch Tokens
            print("[2/7] Provisioning dual tenants and user roles...")
            
            # Signup Target Org Owner
            owner_signup = {
                "email": TEST_OWNER_EMAIL,
                "password": "SecurePassword123",
                "full_name": "Reports Owner",
                "organization_name": "Reports Test Org"
            }
            res = await client.post(f"{BASE_URL}/auth/signup", json=owner_signup)
            assert res.status_code == 201, f"Owner signup failed: {res.text}"
            owner_signup_data = res.json()
            org_id = uuid.UUID(owner_signup_data["default_organization_id"])
            owner_token = owner_signup_data["access_token"]
            
            # Signup Cross Org Owner
            cross_signup = {
                "email": CROSS_OWNER_EMAIL,
                "password": "SecurePassword123",
                "full_name": "Cross Owner",
                "organization_name": "Reports Cross Org"
            }
            res = await client.post(f"{BASE_URL}/auth/signup", json=cross_signup)
            assert res.status_code == 201, f"Cross signup failed: {res.text}"
            cross_signup_data = res.json()
            cross_org_id = uuid.UUID(cross_signup_data["default_organization_id"])
            cross_token = cross_signup_data["access_token"]

            # Seed Analyst and Viewer under target organization
            await seed_analyst_and_viewer(org_id)
            
            # Log in Analyst
            res = await client.post(f"{BASE_URL}/auth/login", json={
                "email": TEST_ANALYST_EMAIL,
                "password": "SecurePassword123"
            })
            assert res.status_code == 200, f"Analyst login failed: {res.text}"
            analyst_token = res.json()["access_token"]
            
            # Log in Viewer
            res = await client.post(f"{BASE_URL}/auth/login", json={
                "email": TEST_VIEWER_EMAIL,
                "password": "SecurePassword123"
            })
            assert res.status_code == 200, f"Viewer login failed: {res.text}"
            viewer_token = res.json()["access_token"]
            
            # Set up Auth headers
            owner_headers = {"Authorization": f"Bearer {owner_token}"}
            analyst_headers = {"Authorization": f"Bearer {analyst_token}"}
            viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
            cross_headers = {"Authorization": f"Bearer {cross_token}"}
            
            print("      Tokens and headers generated for all roles successfully.")

            # 3. Create Dashboard & Seed Analytics Data
            print("[3/7] Provisioning a custom template dashboard and metric events...")
            
            # Create a Web Analytics template dashboard for our target organization
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/dashboards/templates/web_analytics",
                headers=owner_headers
            )
            assert res.status_code == 201, f"Template provisioning failed: {res.text}"
            dashboard_data = res.json()
            dashboard_id = uuid.UUID(dashboard_data["id"])
            print(f"      Provisioned Dashboard: {dashboard_data['name']} (ID: {dashboard_id})")

            # Seed telemetry events into database to simulate active metric collection
            print("      Seeding active telemetry events...")
            async with async_session() as session:
                for i in range(1, 11):
                    # page views
                    event1 = Event(
                        id=uuid.uuid4(),
                        organization_id=org_id,
                        event_name="page_view",
                        timestamp=datetime.now(timezone.utc) - timedelta(hours=i),
                        payload={"session_id": f"sess-{i}", "browser": "Chrome" if i % 2 == 0 else "Safari", "visitor_id": f"visitor-{i}"}
                    )
                    session.add(event1)
                await session.commit()
            print("      Database seeding of metric telemetry events completed.")

            # 4. Test Report Schedules CRUD & Tenant Isolation
            print("[4/7] Testing Report Schedules CRUD operations and RBAC constraints...")
            
            # Viewer tries to create a schedule (should fail with 403)
            schedule_payload = {
                "name": "E2E Performance Digest",
                "dashboard_id": str(dashboard_id),
                "frequency": "daily",
                "recipients": ["ceo@example.com", "analyst@example.com"],
                "is_active": True
            }
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/reports/schedules",
                json=schedule_payload,
                headers=viewer_headers
            )
            assert res.status_code == 403, f"Expected 403 Forbidden for Viewer schedule creation, got {res.status_code}"

            # Analyst creates schedule (should succeed)
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/reports/schedules",
                json=schedule_payload,
                headers=analyst_headers
            )
            assert res.status_code == 201, f"Analyst schedule creation failed: {res.text}"
            schedule_data = res.json()
            schedule_id = uuid.UUID(schedule_data["id"])
            assert schedule_data["name"] == "E2E Performance Digest"
            assert schedule_data["frequency"] == "daily"
            print("      SUCCESS: Report schedule successfully created by Analyst.")

            # Viewer lists schedules (should succeed)
            res = await client.get(
                f"{BASE_URL}/organizations/{org_id}/reports/schedules",
                headers=viewer_headers
            )
            assert res.status_code == 200, f"Viewer listing schedules failed: {res.text}"
            schedules_list = res.json()
            assert len(schedules_list) >= 1
            assert any(s["id"] == str(schedule_id) for s in schedules_list)
            print("      SUCCESS: Viewer successfully listed report schedules.")

            # Cross Tenant tries to read schedule (should fail with 404 since it's tenant-scoped)
            res = await client.get(
                f"{BASE_URL}/organizations/{cross_org_id}/reports/schedules/{schedule_id}",
                headers=cross_headers
            )
            assert res.status_code == 404, f"Expected 404 Not Found for cross-tenant schedule read, got {res.status_code}"
            
            # Cross Tenant tries to update schedule (should fail with 404)
            res = await client.put(
                f"{BASE_URL}/organizations/{cross_org_id}/reports/schedules/{schedule_id}",
                json={"name": "Cross Tenant Modified Name"},
                headers=cross_headers
            )
            assert res.status_code == 404, f"Expected 404 Not Found for cross-tenant schedule update, got {res.status_code}"
            print("      SUCCESS: Cross-tenant isolation boundaries validated.")

            # Analyst updates schedule (should succeed)
            res = await client.put(
                f"{BASE_URL}/organizations/{org_id}/reports/schedules/{schedule_id}",
                json={
                    "name": "E2E Custom Weekly Digest",
                    "frequency": "weekly",
                    "recipients": ["ceo@example.com", "analyst@example.com", "stakeholder@example.com"]
                },
                headers=analyst_headers
            )
            assert res.status_code == 200, f"Analyst update schedule failed: {res.text}"
            updated_schedule = res.json()
            assert updated_schedule["name"] == "E2E Custom Weekly Digest"
            assert updated_schedule["frequency"] == "weekly"
            assert len(updated_schedule["recipients"]) == 3
            print("      SUCCESS: Report schedule successfully updated by Analyst.")

            # 5. Evaluate Scheduled Reports & Generate Snapshots
            print("[5/7] Executing scheduled report evaluations and compiling snapshots...")
            
            # Run the scanning and triggering task synchronously
            print("      Executing scheduled reports scanning scanner sweep...")
            scan_result = await _execute_scheduled_reports_evaluation()
            print(f"      Scanner results: {scan_result}")
            assert scan_result["success"] is True
            assert scan_result["active_schedules"] >= 1
            # In our local test environment, the task is fired asynchronously via Celery (.delay)
            # Since the local worker is running, it will pick it up, or we can trigger it directly
            # to verify synchronous HTML compilation behavior.
            
            print("      Executing single report generation task directly...")
            gen_result = await _execute_single_report_generation(schedule_id)
            print(f"      Generation results: {gen_result}")
            assert gen_result["success"] is True
            assert gen_result["status"] == "success"
            assert gen_result["file_path"] is not None
            assert os.path.exists(gen_result["file_path"])
            
            history_id = uuid.UUID(gen_result["history_id"])
            print("      SUCCESS: HTML snapshot compiled successfully on local disk storage.")

            # 6. Verify History Log Auditing
            print("[6/7] Verifying database history log audits...")
            
            res = await client.get(
                f"{BASE_URL}/organizations/{org_id}/reports/history",
                headers=viewer_headers
            )
            assert res.status_code == 200, f"Retrieval of histories failed: {res.text}"
            histories = res.json()
            assert len(histories) >= 1
            
            target_history = [h for h in histories if h["id"] == str(history_id)]
            assert len(target_history) == 1
            assert target_history[0]["status"] == "success"
            assert target_history[0]["report_schedule_id"] == str(schedule_id)
            print("      SUCCESS: Database audit history records created successfully.")

            # 7. Test Secure Report File Downloading Gateway
            print("[7/7] Verifying multi-tenant download archive file gateway...")
            
            # Cross Tenant tries to download file (should fail with 404 since it's tenant-locked)
            res = await client.get(
                f"{BASE_URL}/organizations/{cross_org_id}/reports/history/{history_id}/download",
                headers=cross_headers
            )
            assert res.status_code == 404, f"Expected 404 Not Found for cross-tenant download, got {res.status_code}"
            
            # Viewer downloads file (should succeed)
            res = await client.get(
                f"{BASE_URL}/organizations/{org_id}/reports/history/{history_id}/download",
                headers=viewer_headers
            )
            assert res.status_code == 200, f"Viewer report download failed: {res.text}"
            assert res.headers["content-type"].startswith("text/html")
            html_text = res.text
            assert "Antigravity Workspace" in html_text
            assert "E2E Custom Weekly Digest" in html_text or "Web Analytics Console" in html_text
            assert "Overview Analytics" in html_text
            print("      SUCCESS: Secure report file download verified successfully.")

            print("==============================================================")
            print("🎉 ALL TESTS PASSED: Scheduled Reports are 100% correct!")
            print("==============================================================")

        except Exception as e:
            print("\n==============================================================")
            print("❌ FAILURE during Scheduled Reports E2E testing.")
            print(f"Error Details: {str(e)}")
            traceback.print_exc()
            print("==============================================================")
            sys.exit(1)
        finally:
            # Clean up testing data
            print("Cleaning up database test structures...")
            await clean_database()
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_scheduled_reports_verification_suite())

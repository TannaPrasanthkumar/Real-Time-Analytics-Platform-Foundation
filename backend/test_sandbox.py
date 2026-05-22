import asyncio
import sys
import os
import httpx
import uuid
import traceback
from sqlalchemy import delete, select, text

# Add local path to import application modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import async_session, engine
from app.models.user import User, UserOrganization, UserRole
from app.models.organization import Organization
from app.models.event import Event
from app.models.data_source import DataSource
from app.models.api_key import APIKey
from app.models.dashboard import Dashboard, Widget
from app.models.report import ReportSchedule, ReportHistory
from app.core.security import get_password_hash

BASE_URL = "http://127.0.0.1:8000/api/v1"

TEST_ORG_SLUG = "sandbox-test-org"
TEST_OWNER_EMAIL = "sandbox-owner@example.com"
TEST_ANALYST_EMAIL = "sandbox-analyst@example.com"
TEST_VIEWER_EMAIL = "sandbox-viewer@example.com"


async def clean_database() -> None:
    """Pre-cleans any testing data to ensure deterministic execution."""
    print("      Cleaning database sandbox testing records...")
    async with async_session() as session:
        res = await session.execute(select(Organization).where(Organization.slug == TEST_ORG_SLUG))
        org = res.scalar_one_or_none()
        if org:
            await session.execute(delete(Event).where(Event.organization_id == org.id))
            await session.execute(delete(UserOrganization).where(UserOrganization.organization_id == org.id))
            await session.execute(delete(Organization).where(Organization.id == org.id))
                
        for email in [TEST_OWNER_EMAIL, TEST_ANALYST_EMAIL, TEST_VIEWER_EMAIL]:
            res_user = await session.execute(select(User).where(User.email == email))
            user = res_user.scalar_one_or_none()
            if user:
                await session.execute(delete(UserOrganization).where(UserOrganization.user_id == user.id))
                await session.execute(delete(User).where(User.id == user.id))
                
        await session.commit()
    print("      Database sandbox records cleaned successfully.")


async def seed_analyst_and_viewer(org_id: uuid.UUID) -> None:
    """Seeds analyst and viewer users inside target organization."""
    print("      Seeding Analyst and Viewer profiles in DB...")
    async with async_session() as session:
        hashed_pwd = get_password_hash("SecurePassword123")
        
        analyst = User(
            email=TEST_ANALYST_EMAIL,
            hashed_password=hashed_pwd,
            full_name="Sandbox Analyst",
            is_active=True,
            is_superuser=False
        )
        session.add(analyst)
        
        viewer = User(
            email=TEST_VIEWER_EMAIL,
            hashed_password=hashed_pwd,
            full_name="Sandbox Viewer",
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


async def run_sandbox_verification_suite() -> None:
    """Executes the E2E verification suite for Custom SQL Sandbox."""
    print("==============================================================")
    print("🚀 Starting SQL Sandbox E2E Verification Suite")
    print("==============================================================")

    # 1. Clean Database
    print("[1/5] Initializing database clean state...")
    await clean_database()
    await asyncio.sleep(0.5)

    async with httpx.AsyncClient() as client:
        try:
            # 2. Provision Tenant & Fetch Tokens
            print("[2/5] Provisioning tenant and user roles...")
            
            # Signup Target Org Owner
            owner_signup = {
                "email": TEST_OWNER_EMAIL,
                "password": "SecurePassword123",
                "full_name": "Sandbox Owner",
                "organization_name": "Sandbox Test Org"
            }
            res = await client.post(f"{BASE_URL}/auth/signup", json=owner_signup)
            assert res.status_code == 201, f"Owner signup failed: {res.text}"
            owner_signup_data = res.json()
            org_id = uuid.UUID(owner_signup_data["default_organization_id"])
            owner_token = owner_signup_data["access_token"]
            
            # Seed Analyst & Viewer
            await seed_analyst_and_viewer(org_id)
            
            # Authenticate Analyst
            login_data = {"email": TEST_ANALYST_EMAIL, "password": "SecurePassword123"}
            res = await client.post(f"{BASE_URL}/auth/login", json=login_data)
            assert res.status_code == 200, f"Analyst login failed: {res.text}"
            analyst_token = res.json()["access_token"]
            
            # Authenticate Viewer
            login_data = {"email": TEST_VIEWER_EMAIL, "password": "SecurePassword123"}
            res = await client.post(f"{BASE_URL}/auth/login", json=login_data)
            assert res.status_code == 200, f"Viewer login failed: {res.text}"
            viewer_token = res.json()["access_token"]

            owner_headers = {"Authorization": f"Bearer {owner_token}"}
            analyst_headers = {"Authorization": f"Bearer {analyst_token}"}
            viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
            print("      Tokens and headers generated for all roles successfully.")

            # 3. Test RBAC Access Constraints
            print("[3/5] Verifying RBAC role boundary enforcement...")
            
            # Test schema endpoint access
            res = await client.get(f"{BASE_URL}/organizations/{org_id}/sandbox/schema", headers=viewer_headers)
            assert res.status_code == 403, f"Expected 403 Forbidden for Viewer on schema, got {res.status_code}"
            
            res = await client.get(f"{BASE_URL}/organizations/{org_id}/sandbox/schema", headers=analyst_headers)
            assert res.status_code == 200, f"Analyst should access schema: {res.text}"
            schema_data = res.json()
            assert "tables" in schema_data
            
            # Test query endpoint access
            payload = {"sql": "SELECT 1;", "explain": False}
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/sandbox/query",
                json=payload,
                headers=viewer_headers
            )
            assert res.status_code == 403, f"Expected 403 Forbidden for Viewer on query, got {res.status_code}"
            
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/sandbox/query",
                json=payload,
                headers=analyst_headers
            )
            assert res.status_code == 200, f"Analyst should execute query: {res.text}"
            print("      SUCCESS: RBAC constraints verified. Analyst is authorized, Viewer is strictly blocked.")

            # 4. Verify SQL Evasion & Destructive Instruction Blocking
            print("[4/5] Testing client-side SQL parser validation and keyword blockers...")
            
            malicious_queries = [
                "INSERT INTO events (event_name) VALUES ('hack');",
                "UPDATE users SET email = 'hacked@hack.com';",
                "DELETE FROM users;",
                "DROP TABLE users;",
                "ALTER TABLE users ADD COLUMN hack_me text;",
                "TRUNCATE TABLE events;",
                "CREATE TABLE hack (id serial primary key);",
                "SELECT 1; DROP TABLE users;",  # SQL injection stack
                "dRoP TABLE users;",            # Case-insensitivity check
                "DROP      TABLE users;",       # Spacing evasion check
                "SET TRANSACTION READ WRITE;",   # Explicitly trying to bypass transaction limits
                "EXECUTE 'SELECT 1';"
            ]
            
            for index, sql in enumerate(malicious_queries):
                payload = {"sql": sql, "explain": False}
                res = await client.post(
                    f"{BASE_URL}/organizations/{org_id}/sandbox/query",
                    json=payload,
                    headers=analyst_headers
                )
                assert res.status_code == 200
                res_data = res.json()
                assert res_data["success"] is False, f"Query '{sql}' should have been blocked, but succeeded!"
                assert "Security violation" in res_data["error"] or "Forbidden database operation" in res_data["error"]
                print(f"      Blocked query {index+1}/{len(malicious_queries)} successfully: {sql}")
                
            print("      SUCCESS: All malicious and destructive SQL patterns successfully blocked.")

            # 5. Test Querying, Schema Mapping, and EXPLAIN Execution Plans
            print("[5/5] Checking query execution grid results and visual EXPLAIN plan formats...")
            
            # Simple math query
            payload = {"sql": "SELECT 1 + 1 AS addition, 'hello' AS text_val;", "explain": False}
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/sandbox/query",
                json=payload,
                headers=analyst_headers
            )
            assert res.status_code == 200
            res_data = res.json()
            assert res_data["success"] is True
            assert res_data["columns"] == ["addition", "text_val"]
            assert res_data["rows"] == [{"addition": 2, "text_val": "hello"}]
            assert res_data["execution_time_ms"] > 0
            assert res_data["explain_plan"] is None
            
            # Real table query (users table should exist)
            payload = {"sql": "SELECT email, full_name, is_active FROM users ORDER BY email LIMIT 2;", "explain": False}
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/sandbox/query",
                json=payload,
                headers=analyst_headers
            )
            assert res.status_code == 200
            res_data = res.json()
            assert res_data["success"] is True
            assert len(res_data["columns"]) == 3
            assert any(r["email"] == TEST_ANALYST_EMAIL for r in res_data["rows"])
            
            # Test EXPLAIN (with execution plan formatted as JSON)
            payload = {"sql": "SELECT email FROM users WHERE is_active = true;", "explain": True}
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/sandbox/query",
                json=payload,
                headers=analyst_headers
            )
            assert res.status_code == 200
            res_data = res.json()
            assert res_data["success"] is True
            assert res_data["explain_plan"] is not None
            assert isinstance(res_data["explain_plan"], list)
            # PostgreSQL output from EXPLAIN (FORMAT JSON) is a list containing a dict with "Plan" key
            plan_root = res_data["explain_plan"][0]
            assert "Plan" in plan_root
            assert "Node Type" in plan_root["Plan"]
            print("      SUCCESS: Grid rows parsed and PostgreSQL JSON Query Plan fetched cleanly.")

            print("==============================================================")
            print("🎉 ALL SQL SANDBOX TESTS PASSED SUCCESSFULLY!")
            print("==============================================================")

        except Exception as e:
            print("\n==============================================================")
            print("❌ FAILURE during SQL Sandbox E2E testing.")
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
    asyncio.run(run_sandbox_verification_suite())

import asyncio
import sys
import os
import httpx
from sqlalchemy import delete, select

# Add local path to import DB sessions for database checks/inserts
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import async_session, engine
from app.models.user import User, UserOrganization, UserRole
from app.models.organization import Organization
from app.models.invitation import Invitation
from app.core.security import get_password_hash

BASE_URL = "http://127.0.0.1:8000/api/v1"


async def setup_test_users(session) -> None:
    """Pre-cleans stale accounts and sets up static test profiles inside DB."""
    print("      Preparing database users...")
    
    # 1. Clean up stale test accounts
    emails = ["owner@acme.com", "analyst@acme.com", "owner@globex.com"]
    await session.execute(delete(Invitation).where(Invitation.email.in_(emails)))
    await session.execute(delete(User).where(User.email.in_(emails)))
    await session.execute(delete(Organization).where(Organization.slug.in_(["acme-corp", "globex-corp"])))
    await session.commit()
    
    # 2. Seed a second user linked to Acme Corp as an ANALYST
    # Note: owner@acme.com and owner@globex.com will register via the API signup routers
    hashed_pwd = get_password_hash("SecurePassword123")
    analyst = User(
        email="analyst@acme.com",
        hashed_password=hashed_pwd,
        full_name="Jane Analyst",
        is_active=True,
        is_superuser=False,
    )
    session.add(analyst)
    await session.commit()
    print("      Seeding and cleanup completed successfully.")


async def run_auth_rbac_test() -> None:
    """Verifies login, signup, refresh, cross-tenant isolation, and RBAC guards."""
    print("==============================================================")
    print("🔐 Starting Auth & RBAC Security Integration Verification Suite")
    print("==============================================================")

    # 1. Database user setup
    print("[1/6] Setup database and seed test accounts...")
    async with async_session() as session:
        await setup_test_users(session)

    # Allow FastAPI dev reload server to catch up if needed
    await asyncio.sleep(0.5)

    async with httpx.AsyncClient() as client:
        try:
            # 2. Signup Test for Acme Corp Owner
            print("[2/6] Testing Acme Corp Owner Sign-Up flow...")
            signup_payload = {
                "email": "owner@acme.com",
                "password": "SecurePassword123",
                "full_name": "John Acme Owner",
                "organization_name": "Acme Corp"
            }
            res = await client.post(f"{BASE_URL}/auth/signup", json=signup_payload)
            assert res.status_code == 201, f"Signup failed: {res.text}"
            
            signup_data = res.json()
            assert "access_token" in signup_data
            assert signup_data["user"]["email"] == "owner@acme.com"
            
            acme_org_id = signup_data["default_organization_id"]
            acme_owner_token = signup_data["access_token"]
            
            # Verify refresh token cookie presence
            cookies = res.cookies
            assert "refresh_token" in cookies, "Refresh token cookie not set"
            acme_refresh_cookie = cookies["refresh_token"]
            print("      Acme Corp Owner registration and tokens issued successfully.")

            # Bind Analyst to Acme Corp org_id in DB
            print("      Binding Jane Analyst to Acme Corp in DB...")
            async with async_session() as session:
                res_db = await session.execute(
                    select(User).where(User.email == "analyst@acme.com")
                )
                analyst_user = res_db.scalar_one()
                
                membership = UserOrganization(
                    user_id=analyst_user.id,
                    organization_id=uuid_from_str(acme_org_id),
                    role=UserRole.ANALYST,
                )
                session.add(membership)
                await session.commit()
            print("      Jane Analyst successfully bound to Acme Corp.")

            # 3. Signup Test for Globex Owner (Cross-tenant boundary test prep)
            print("[3/6] Testing Globex Owner Sign-Up flow (tenant 2)...")
            globex_payload = {
                "email": "owner@globex.com",
                "password": "SecurePassword123",
                "full_name": "George Globex Owner",
                "organization_name": "Globex Corp"
            }
            res = await client.post(f"{BASE_URL}/auth/signup", json=globex_payload)
            assert res.status_code == 201, f"Globex Signup failed: {res.text}"
            
            globex_data = res.json()
            globex_org_id = globex_data["default_organization_id"]
            globex_owner_token = globex_data["access_token"]
            print("      Globex Corp Owner registration successful.")

            # 4. Authentication Login Flows
            print("[4/6] Testing Login verification endpoints...")
            
            # Correct login
            login_payload = {"email": "owner@acme.com", "password": "SecurePassword123"}
            res = await client.post(f"{BASE_URL}/auth/login", json=login_payload)
            assert res.status_code == 200
            assert "access_token" in res.json()
            
            # Incorrect password
            login_payload_fail = {"email": "owner@acme.com", "password": "WrongPassword"}
            res = await client.post(f"{BASE_URL}/auth/login", json=login_payload_fail)
            assert res.status_code == 401
            
            # Login as Jane Analyst
            login_payload_analyst = {"email": "analyst@acme.com", "password": "SecurePassword123"}
            res = await client.post(f"{BASE_URL}/auth/login", json=login_payload_analyst)
            assert res.status_code == 200
            acme_analyst_token = res.json()["access_token"]
            print("      Login credentials checking is fully validated.")

            # 5. RBAC Guard and Tenant Isolation Testing
            print("[5/6] Testing RBAC guards and Multi-Tenant Isolation boundaries...")
            
            # Headers setups
            owner_headers = {"Authorization": f"Bearer {acme_owner_token}"}
            analyst_headers = {"Authorization": f"Bearer {acme_analyst_token}"}
            globex_headers = {"Authorization": f"Bearer {globex_owner_token}"}

            # A. Test Acme Owner Access (Should pass everything in Acme)
            print("      Running Owner clearance checks in Acme Corp...")
            res = await client.get(f"{BASE_URL}/test-guard/viewer/{acme_org_id}", headers=owner_headers)
            assert res.status_code == 200
            
            res = await client.get(f"{BASE_URL}/test-guard/analyst/{acme_org_id}", headers=owner_headers)
            assert res.status_code == 200
            
            res = await client.get(f"{BASE_URL}/test-guard/admin/{acme_org_id}", headers=owner_headers)
            assert res.status_code == 200
            
            res = await client.get(f"{BASE_URL}/test-guard/owner/{acme_org_id}", headers=owner_headers)
            assert res.status_code == 200
            print("      Owner passes all guards successfully.")

            # B. Test Acme Analyst Access (Should pass viewer & analyst, fail admin & owner)
            print("      Running Analyst clearance checks in Acme Corp...")
            res = await client.get(f"{BASE_URL}/test-guard/viewer/{acme_org_id}", headers=analyst_headers)
            assert res.status_code == 200
            
            res = await client.get(f"{BASE_URL}/test-guard/analyst/{acme_org_id}", headers=analyst_headers)
            assert res.status_code == 200
            
            res = await client.get(f"{BASE_URL}/test-guard/admin/{acme_org_id}", headers=analyst_headers)
            assert res.status_code == 403  # Analyst is not Admin!
            
            res = await client.get(f"{BASE_URL}/test-guard/owner/{acme_org_id}", headers=analyst_headers)
            assert res.status_code == 403  # Analyst is not Owner!
            print("      Analyst boundaries perfectly enforced (Passed: 2, Forbidden: 2).")

            # C. Test Cross-Tenant Access (Globex Owner trying to read Acme Corp data)
            print("      Running cross-tenant isolation checks...")
            res = await client.get(f"{BASE_URL}/test-guard/viewer/{acme_org_id}", headers=globex_headers)
            assert res.status_code == 403, f"Cross-tenant leak! Status: {res.status_code}"
            
            res = await client.get(f"{BASE_URL}/test-guard/owner/{acme_org_id}", headers=globex_headers)
            assert res.status_code == 403, f"Cross-tenant leak! Status: {res.status_code}"
            print("      SUCCESS: Cross-tenant data isolation verified (Globex Owner forbidden from Acme Corp).")

            # 6. Silent token refresh and logout
            print("[6/6] Testing Refresh Tokens and Logout cookie operations...")
            
            # Call refresh endpoint sending the active cookie
            client.cookies.set("refresh_token", acme_refresh_cookie)
            res = await client.post(f"{BASE_URL}/auth/refresh")
            assert res.status_code == 200, f"Token refresh failed: {res.text}"
            refresh_data = res.json()
            assert "access_token" in refresh_data
            assert "refresh_token" in res.cookies
            print("      Silent token refresh verified.")

            # Logout
            res = await client.post(f"{BASE_URL}/auth/logout")
            assert res.status_code == 200
            assert res.cookies.get("refresh_token") == "" or "refresh_token" not in res.cookies
            print("      Logout and cookie deletion verified.")

            print("==============================================================")
            print("🎉 ALL TESTS PASSED: Authentication and RBAC Guards fully validated!")
            print("==============================================================")

        except Exception as e:
            import traceback
            print("\n==============================================================")
            print("❌ FAILURE: Integration verification tests failed.")
            traceback.print_exc()
            print("==============================================================")
            sys.exit(1)
        finally:
            # Cleanup database records
            print("      Executing database test records teardown...")
            async with async_session() as session:
                emails = ["owner@acme.com", "analyst@acme.com", "owner@globex.com"]
                await session.execute(delete(Invitation).where(Invitation.email.in_(emails)))
                await session.execute(delete(User).where(User.email.in_(emails)))
                await session.execute(delete(Organization).where(Organization.slug.in_(["acme-corp", "globex-corp"])))
                await session.commit()
            await engine.dispose()
            print("      Teardown completed successfully.")


def uuid_from_str(val: str):
    import uuid
    return uuid.UUID(val)


if __name__ == "__main__":
    asyncio.run(run_auth_rbac_test())

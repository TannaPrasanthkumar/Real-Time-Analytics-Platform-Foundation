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


async def setup_test_environment() -> dict:
    """Sets up clean database state for invitation verification tests."""
    print("      Preparing database state...")
    async with async_session() as session:
        # 1. Stale records cleanup
        emails = [
            "admin@acme-invite.com",
            "new-member@acme-invite.com",
            "existing-member@acme-invite.com",
            "viewer@acme-invite.com",
        ]
        await session.execute(delete(Invitation).where(Invitation.email.in_(emails)))
        await session.execute(delete(User).where(User.email.in_(emails)))
        await session.execute(
            delete(Organization).where(Organization.slug == "acme-invite")
        )
        await session.commit()

        # 2. Seed Admin user
        hashed_pwd = get_password_hash("SecurePassword123")
        admin = User(
            email="admin@acme-invite.com",
            hashed_password=hashed_pwd,
            full_name="Jane Admin",
            is_active=True,
            is_superuser=False,
        )
        session.add(admin)

        # 3. Seed an existing registered user (not yet linked to the org)
        existing_user = User(
            email="existing-member@acme-invite.com",
            hashed_password=hashed_pwd,
            full_name="John Existing",
            is_active=True,
            is_superuser=False,
        )
        session.add(existing_user)

        # 4. Seed a standard viewer user (for role boundary testing)
        viewer_user = User(
            email="viewer@acme-invite.com",
            hashed_password=hashed_pwd,
            full_name="Bob Viewer",
            is_active=True,
            is_superuser=False,
        )
        session.add(viewer_user)

        # 5. Seed Organization
        org = Organization(name="Acme Invite", slug="acme-invite", is_active=True)
        session.add(org)
        await session.commit()

        # 6. Bind Admin to Organization
        admin_membership = UserOrganization(
            user_id=admin.id, organization_id=org.id, role=UserRole.ADMIN
        )
        session.add(admin_membership)

        # 7. Bind Bob Viewer to Organization
        viewer_membership = UserOrganization(
            user_id=viewer_user.id, organization_id=org.id, role=UserRole.VIEWER
        )
        session.add(viewer_membership)
        await session.commit()

        print("      Seed data created successfully.")
        return {
            "org_id": str(org.id),
            "admin_email": admin.email,
            "viewer_email": viewer_user.email,
        }


async def run_invitation_system_tests() -> None:
    """Verifies creation, role boundary restrictions, public retrieval, and acceptance routes."""
    print("==============================================================")
    print("📨 Starting Team Onboarding & Invitation Security Suite")
    print("==============================================================")

    # 1. Setup test environment
    print("[1/5] Setting up database structures...")
    meta = await setup_test_environment()
    org_id = meta["org_id"]

    await asyncio.sleep(0.5)

    async with httpx.AsyncClient() as client:
        try:
            # 2. Login to acquire Admin and Viewer tokens
            print("[2/5] Logging in to acquire role tokens...")
            
            # Admin Login
            login_payload = {
                "email": "admin@acme-invite.com",
                "password": "SecurePassword123",
            }
            res = await client.post(f"{BASE_URL}/auth/login", json=login_payload)
            assert res.status_code == 200, f"Admin login failed: {res.text}"
            admin_token = res.json()["access_token"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}

            # Viewer Login
            login_payload_viewer = {
                "email": "viewer@acme-invite.com",
                "password": "SecurePassword123",
            }
            res = await client.post(f"{BASE_URL}/auth/login", json=login_payload_viewer)
            assert res.status_code == 200, f"Viewer login failed: {res.text}"
            viewer_token = res.json()["access_token"]
            viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

            print("      Tokens acquired successfully.")

            # 3. Test Invite Creation & Role Boundaries
            print("[3/5] Testing Invitation creation and access permissions...")

            # Scenario A: Viewer attempts to create invitation (Should be FORBIDDEN)
            invite_payload = {"email": "new-member@acme-invite.com", "role": "analyst"}
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/invitations",
                json=invite_payload,
                headers=viewer_headers,
            )
            assert res.status_code == 403, "Viewer was incorrectly allowed to create an invitation!"
            print("      SUCCESS: Role boundaries enforced (Viewer block validated).")

            # Scenario B: Admin creates valid invitation
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/invitations",
                json=invite_payload,
                headers=admin_headers,
            )
            assert res.status_code == 201, f"Failed to create invitation: {res.text}"
            invite_data = res.json()
            assert invite_data["email"] == "new-member@acme-invite.com"
            assert invite_data["role"] == "analyst"
            assert invite_data["organization_id"] == org_id
            assert "token" in invite_data
            
            invite_token = invite_data["token"]
            print("      SUCCESS: Admin successfully issued a pending invitation.")

            # 4. Test Public Retrieve & Verification Endpoints
            print("[4/5] Testing public retrieval validation...")
            res = await client.get(f"{BASE_URL}/invitations/{invite_token}")
            assert res.status_code == 200, f"Failed to retrieve invitation: {res.text}"
            retrieved = res.json()
            assert retrieved["email"] == "new-member@acme-invite.com"
            assert retrieved["organization_name"] == "Acme Invite"
            assert retrieved["role"] == "analyst"
            print("      SUCCESS: Public invitation details verification complete.")

            # 5. Test Invite Acceptance Paths
            print("[5/5] Testing onboarding invite acceptance scenarios...")

            # Scenario A: New User acceptance flow (Requires full_name and password)
            accept_payload = {
                "token": invite_token,
                "password": "SecurePassword123",
                "full_name": "Bob Analyst",
            }
            res = await client.post(f"{BASE_URL}/invitations/accept", json=accept_payload)
            assert res.status_code == 200, f"Accept failed: {res.text}"
            accept_data = res.json()
            assert "access_token" in accept_data
            assert accept_data["user"]["email"] == "new-member@acme-invite.com"
            assert accept_data["default_organization_id"] == org_id
            assert "refresh_token" in res.cookies
            print("      SUCCESS: New user dynamically registered and linked to workspace.")

            # Scenario B: Try to accept already accepted invite (Should be BLOCKED)
            res = await client.post(f"{BASE_URL}/invitations/accept", json=accept_payload)
            assert res.status_code == 400, "Onboarding allowed reusing an accepted token!"
            print("      SUCCESS: Single-use token enforcement validated.")

            # Scenario C: Existing registered user acceptance
            # Admin creates invite for existing user
            invite_payload_exist = {
                "email": "existing-member@acme-invite.com",
                "role": "viewer",
            }
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/invitations",
                json=invite_payload_exist,
                headers=admin_headers,
            )
            assert res.status_code == 201, f"Failed existing invite: {res.text}"
            exist_token = res.json()["token"]

            # Accept existing user invite (no password/name needed!)
            accept_payload_exist = {"token": exist_token}
            res = await client.post(
                f"{BASE_URL}/invitations/accept", json=accept_payload_exist
            )
            assert res.status_code == 200, f"Accept existing user failed: {res.text}"
            accept_data_exist = res.json()
            assert "access_token" in accept_data_exist
            assert accept_data_exist["user"]["email"] == "existing-member@acme-invite.com"
            assert accept_data_exist["default_organization_id"] == org_id
            print("      SUCCESS: Existing registered user joined workspace successfully.")

            # Database verification
            print("      Running final database assertion sweeps...")
            async with async_session() as session:
                # Retrieve new member User and their membership
                res_db = await session.execute(
                    select(User).where(User.email == "new-member@acme-invite.com")
                )
                user_obj = res_db.scalar_one_or_none()
                assert user_obj is not None, "New user not in DB!"
                
                res_membership = await session.execute(
                    select(UserOrganization).where(
                        UserOrganization.user_id == user_obj.id,
                        UserOrganization.organization_id == uuid_from_str(org_id),
                    )
                )
                membership_obj = res_membership.scalar_one_or_none()
                assert membership_obj is not None, "New user membership not in DB!"
                assert (
                    membership_obj.role == UserRole.ANALYST
                ), f"Invalid role assigned: {membership_obj.role}"

                # Retrieve existing member membership
                res_exist_user = await session.execute(
                    select(User).where(User.email == "existing-member@acme-invite.com")
                )
                exist_user_obj = res_exist_user.scalar_one_or_none()
                
                res_exist_membership = await session.execute(
                    select(UserOrganization).where(
                        UserOrganization.user_id == exist_user_obj.id,
                        UserOrganization.organization_id == uuid_from_str(org_id),
                    )
                )
                exist_membership_obj = res_exist_membership.scalar_one_or_none()
                assert exist_membership_obj is not None, "Existing user membership not in DB!"
                assert (
                    exist_membership_obj.role == UserRole.VIEWER
                ), f"Invalid role assigned: {exist_membership_obj.role}"

            print("      Database assertions matches perfectly.")
            print("==============================================================")
            print("🎉 ALL TESTS PASSED: Invitation and Team Onboarding fully verified!")
            print("==============================================================")

        except Exception as e:
            import traceback
            print("\n==============================================================")
            print("❌ FAILURE: Integration verification tests failed.")
            traceback.print_exc()
            print("==============================================================")
            sys.exit(1)
        finally:
            # Final teardown
            print("      Executing database test records teardown...")
            async with async_session() as session:
                emails = [
                    "admin@acme-invite.com",
                    "new-member@acme-invite.com",
                    "existing-member@acme-invite.com",
                    "viewer@acme-invite.com",
                ]
                await session.execute(delete(Invitation).where(Invitation.email.in_(emails)))
                await session.execute(delete(User).where(User.email.in_(emails)))
                await session.execute(
                    delete(Organization).where(Organization.slug == "acme-invite")
                )
                await session.commit()
            await engine.dispose()
            print("      Teardown completed successfully.")


def uuid_from_str(val: str):
    import uuid
    return uuid.UUID(val)


if __name__ == "__main__":
    asyncio.run(run_invitation_system_tests())

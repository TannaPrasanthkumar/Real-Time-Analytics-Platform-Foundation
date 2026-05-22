import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

# Add local path to import application modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.db.session import async_session, engine
from app.models.user import User, UserOrganization, UserRole
from app.models.organization import Organization
from app.models.invitation import Invitation


async def run_models_integration_test() -> None:
    """Verifies schema structure, relationships, constraints, and cascades in the database."""
    print("==============================================================")
    print("🚀 Running Authentication & Multi-Tenancy Models Integration Test")
    print("==============================================================")

    async with async_session() as session:
        try:
            # 1. Clean up any existing test records if they exist
            print("[1/6] Cleaning up stale test data...")
            await session.execute(delete(Invitation).where(Invitation.email == "invitee@example.com"))
            await session.execute(delete(User).where(User.email == "jane@acme.com"))
            await session.execute(delete(Organization).where(Organization.slug == "acme-corp"))
            await session.commit()
            print("      Cleanup successful.")

            # 2. Insert test data
            print("[2/6] Inserting test Organization, User, and Membership...")
            org = Organization(name="Acme Corp", slug="acme-corp")
            user = User(
                email="jane@acme.com",
                hashed_password="mock_hashed_password_123",
                full_name="Jane Doe",
                is_active=True,
                is_superuser=False,
            )
            
            session.add(org)
            session.add(user)
            await session.flush()  # Populates IDs

            membership = UserOrganization(
                user_id=user.id,
                organization_id=org.id,
                role=UserRole.OWNER,
            )
            session.add(membership)

            # 3. Create an invitation
            print("[3/6] Creating invitation linked to Organization and User...")
            invitation = Invitation(
                email="invitee@example.com",
                organization_id=org.id,
                inviter_id=user.id,
                role=UserRole.ANALYST,
                token=f"invite_token_{uuid.uuid4()}",
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            session.add(invitation)
            await session.commit()
            print("      Insert and Commit SUCCESS.")

            # 4. Query and verify relationships
            print("[4/6] Verifying relationship loading and attributes...")
            
            # Fetch User and verify memberships
            stmt = select(User).where(User.email == "jane@acme.com").options(selectinload(User.memberships))
            res = await session.execute(stmt)
            fetched_user = res.scalar_one()
            
            assert fetched_user.full_name == "Jane Doe"
            assert len(fetched_user.memberships) == 1
            assert fetched_user.memberships[0].role == UserRole.OWNER
            assert fetched_user.memberships[0].organization_id == org.id
            print("      User to Membership relationships verified.")

            # Fetch Organization and verify memberships
            stmt = select(Organization).where(Organization.slug == "acme-corp").options(selectinload(Organization.memberships))
            res = await session.execute(stmt)
            fetched_org = res.scalar_one()
            
            assert fetched_org.name == "Acme Corp"
            assert len(fetched_org.memberships) == 1
            assert fetched_org.memberships[0].user_id == user.id
            print("      Organization to Membership relationships verified.")

            # Fetch Invitation
            stmt = select(Invitation).where(Invitation.email == "invitee@example.com")
            res = await session.execute(stmt)
            fetched_invite = res.scalar_one()
            
            assert fetched_invite.role == UserRole.ANALYST
            assert fetched_invite.organization_id == org.id
            assert fetched_invite.inviter_id == user.id
            print("      Invitation attributes and associations verified.")

            # 5. Verify cascade behavior (deleting organization deletes memberships and invitations)
            print("[5/6] Testing database cascade delete behavior on Organization...")
            await session.delete(fetched_org)
            await session.commit()
            print("      Organization deleted successfully.")

            # Verify memberships are cascaded and deleted
            stmt = select(UserOrganization).where(UserOrganization.organization_id == org.id)
            res = await session.execute(stmt)
            memberships_left = res.scalars().all()
            assert len(memberships_left) == 0
            print("      SUCCESS: UserOrganization memberships cascaded and deleted.")

            # Verify invitations are cascaded and deleted
            stmt = select(Invitation).where(Invitation.organization_id == org.id)
            res = await session.execute(stmt)
            invitations_left = res.scalars().all()
            assert len(invitations_left) == 0
            print("      SUCCESS: Invitations cascaded and deleted.")

            # Verify User remains intact (not deleted)
            stmt = select(User).where(User.email == "jane@acme.com")
            res = await session.execute(stmt)
            fetched_user_after_delete = res.scalar_one_or_none()
            assert fetched_user_after_delete is not None
            print("      SUCCESS: User remained intact (not affected by cascade).")

            # 6. Final Clean up of test User
            print("[6/6] Final cleanup of test User...")
            await session.delete(fetched_user_after_delete)
            await session.commit()
            print("      Cleanup completed.")

            print("==============================================================")
            print("🎉 ALL CHECKS PASSED: Multi-tenancy models are fully validated!")
            print("==============================================================")

        except Exception as e:
            print("\n==============================================================")
            print("❌ FAILURE during integration testing.")
            print(f"Error Details: {str(e)}")
            print("==============================================================")
            await session.rollback()
            sys.exit(1)
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_models_integration_test())

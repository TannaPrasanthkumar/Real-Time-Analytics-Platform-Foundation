import asyncio
import sys
import os
import httpx
import uuid
import websockets
import json
import traceback
from datetime import datetime, timezone
from sqlalchemy import delete, select

# Add local path to import application modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import app.models.base
from app.db.session import async_session, engine
from app.models.user import User, UserOrganization, UserRole
from app.models.organization import Organization
from app.models.dashboard import Dashboard, Widget
from app.models.api_key import APIKey
from app.models.event import Event
from app.models.invitation import Invitation
from app.models.data_source import DataSource
from app.core.security import get_password_hash

# URLs for real running backend service in Docker Compose
BASE_URL = "http://127.0.0.1:8000/api/v1"
WS_BASE_URL = "ws://127.0.0.1:8000/api/v1"

TEST_ORG_SLUG = "dashboard-test-org"
CROSS_ORG_SLUG = "dashboard-cross-org"

TEST_OWNER_EMAIL = "dashboard-owner@example.com"
TEST_ANALYST_EMAIL = "dashboard-analyst@example.com"
TEST_VIEWER_EMAIL = "dashboard-viewer@example.com"
CROSS_OWNER_EMAIL = "dashboard-cross-owner@example.com"


async def clean_database() -> None:
    """Pre-cleans any testing data to ensure deterministic execution."""
    print("      Cleaning database testing records...")
    async with async_session() as session:
        for slug in [TEST_ORG_SLUG, CROSS_ORG_SLUG]:
            res = await session.execute(select(Organization).where(Organization.slug == slug))
            org = res.scalar_one_or_none()
            if org:
                # Retrieve dashboard IDs to manually prune widgets first
                res_dash = await session.execute(
                    select(Dashboard).where(Dashboard.organization_id == org.id)
                )
                dashboards = res_dash.scalars().all()
                dash_ids = [d.id for d in dashboards]
                if dash_ids:
                    await session.execute(delete(Widget).where(Widget.dashboard_id.in_(dash_ids)))
                    await session.execute(delete(Dashboard).where(Dashboard.id.in_(dash_ids)))
                
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
        
        # Check and create analyst
        analyst = User(
            email=TEST_ANALYST_EMAIL,
            hashed_password=hashed_pwd,
            full_name="Dashboard Analyst",
            is_active=True,
            is_superuser=False
        )
        session.add(analyst)
        
        # Check and create viewer
        viewer = User(
            email=TEST_VIEWER_EMAIL,
            hashed_password=hashed_pwd,
            full_name="Dashboard Viewer",
            is_active=True,
            is_superuser=False
        )
        session.add(viewer)
        await session.flush()
        
        # Link memberships
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


async def run_dashboard_websockets_verification_suite() -> None:
    """Executes the E2E verification suite for Dashboards, Widgets, and WebSockets."""
    print("==============================================================")
    print("🚀 Starting Dashboard & WebSockets E2E Verification Suite")
    print("==============================================================")

    # 1. Clean Database
    print("[1/7] Initializing database clean state...")
    await clean_database()
    
    # Pause slightly to allow system state normalization
    await asyncio.sleep(0.5)

    async with httpx.AsyncClient() as client:
        try:
            # 2. Provision Tenants & Fetch Tokens
            print("[2/7] Provisioning dual tenants and user roles...")
            
            # Signup Target Org Owner
            owner_signup = {
                "email": TEST_OWNER_EMAIL,
                "password": "SecurePassword123",
                "full_name": "Dashboard Owner",
                "organization_name": "Dashboard Test Org"
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
                "organization_name": "Dashboard Cross Org"
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

            # 3. Test Dashboard CRUD with RBAC boundaries
            print("[3/7] Testing Dashboard CRUD & RBAC access restrictions...")
            
            # Viewer tries to create a dashboard (should fail)
            dashboard_create_payload = {
                "name": "Viewer Custom Dashboard",
                "description": "Unauthorized dashboard creation",
                "is_public": False
            }
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/dashboards",
                json=dashboard_create_payload,
                headers=viewer_headers
            )
            assert res.status_code == 403, f"Expected 403 Forbidden for Viewer dashboard creation, got {res.status_code}"
            
            # Analyst creates a dashboard (should succeed)
            dashboard_create_payload = {
                "name": "Operations KPI Console",
                "description": "Monitors active operations latency and DAUs",
                "is_public": False
            }
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/dashboards",
                json=dashboard_create_payload,
                headers=analyst_headers
            )
            assert res.status_code == 201, f"Analyst dashboard creation failed: {res.text}"
            dash_data = res.json()
            dashboard_id = uuid.UUID(dash_data["id"])
            assert dash_data["name"] == "Operations KPI Console"
            assert dash_data["is_public"] is False
            print("      SUCCESS: Dashboard created by Analyst.")

            # Viewer lists dashboards (should succeed)
            res = await client.get(
                f"{BASE_URL}/organizations/{org_id}/dashboards",
                headers=viewer_headers
            )
            assert res.status_code == 200, f"Viewer dashboard listing failed: {res.text}"
            dashboards_list = res.json()
            assert len(dashboards_list) >= 1
            assert any(d["name"] == "Operations KPI Console" for d in dashboards_list)
            print("      SUCCESS: Viewer successfully retrieved dashboard list.")

            # Viewer tries to update dashboard name (should fail)
            res = await client.put(
                f"{BASE_URL}/organizations/{org_id}/dashboards/{dashboard_id}",
                json={"name": "Viewer Changed Dashboard Name"},
                headers=viewer_headers
            )
            assert res.status_code == 403, f"Expected 403 Forbidden for Viewer dashboard update, got {res.status_code}"

            # Analyst updates dashboard name and description (should succeed)
            res = await client.put(
                f"{BASE_URL}/organizations/{org_id}/dashboards/{dashboard_id}",
                json={
                    "name": "Platform Ops Center",
                    "description": "Central visual interface for operational telemetry"
                },
                headers=analyst_headers
            )
            assert res.status_code == 200, f"Analyst dashboard update failed: {res.text}"
            updated_dash = res.json()
            assert updated_dash["name"] == "Platform Ops Center"
            assert updated_dash["description"] == "Central visual interface for operational telemetry"
            print("      SUCCESS: Dashboard updated by Analyst.")

            # 4. Test Widget Layout and Query Config configurations
            print("[4/7] Testing Widget CRUD, Layout coordinates, and Saved queries...")
            
            # Viewer tries to add widget (should fail)
            widget_create_payload = {
                "name": "Average API Latency",
                "type": "line",
                "layout": {"x": 0, "y": 0, "w": 6, "h": 4},
                "query_config": {"metric_type": "latency", "interval": "hour", "time_range": "24h"}
            }
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/dashboards/{dashboard_id}/widgets",
                json=widget_create_payload,
                headers=viewer_headers
            )
            assert res.status_code == 403, f"Expected 403 Forbidden for Viewer widget creation, got {res.status_code}"

            # Analyst adds widget (should succeed)
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/dashboards/{dashboard_id}/widgets",
                json=widget_create_payload,
                headers=analyst_headers
            )
            assert res.status_code == 201, f"Analyst widget creation failed: {res.text}"
            widget_data = res.json()
            widget_id = uuid.UUID(widget_data["id"])
            assert widget_data["name"] == "Average API Latency"
            assert widget_data["type"] == "line"
            assert widget_data["layout"]["w"] == 6
            assert widget_data["query_config"]["metric_type"] == "latency"
            print("      SUCCESS: Widget added by Analyst.")

            # Viewer tries to update widget layout (should fail)
            res = await client.put(
                f"{BASE_URL}/organizations/{org_id}/dashboards/{dashboard_id}/widgets/{widget_id}",
                json={"layout": {"x": 0, "y": 0, "w": 12, "h": 4}},
                headers=viewer_headers
            )
            assert res.status_code == 403, f"Expected 403 Forbidden for Viewer widget update, got {res.status_code}"

            # Analyst updates widget layout and name (should succeed)
            res = await client.put(
                f"{BASE_URL}/organizations/{org_id}/dashboards/{dashboard_id}/widgets/{widget_id}",
                json={
                    "name": "P99 API Latency Dashboard",
                    "layout": {"x": 0, "y": 0, "w": 12, "h": 4}
                },
                headers=analyst_headers
            )
            assert res.status_code == 200, f"Analyst widget update failed: {res.text}"
            updated_widget = res.json()
            assert updated_widget["name"] == "P99 API Latency Dashboard"
            assert updated_widget["layout"]["w"] == 12
            print("      SUCCESS: Widget layout and name updated by Analyst.")

            # 5. Test Template Provisioning & Public Sharing Link
            print("[5/7] Testing Dashboard Templates & Public URL sharing tokens...")
            
            # Provision Web Analytics dashboard template via Analyst
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/dashboards/templates/web_analytics",
                headers=analyst_headers
            )
            assert res.status_code == 201, f"Template provisioning failed: {res.text}"
            template_dash = res.json()
            template_dash_id = uuid.UUID(template_dash["id"])
            assert template_dash["name"] == "Web Analytics Console"
            assert len(template_dash["widgets"]) == 6
            
            widget_types = [w["type"] for w in template_dash["widgets"]]
            assert "kpi" in widget_types
            assert "line" in widget_types
            assert "pie" in widget_types
            print("      SUCCESS: 'web_analytics' template provisioned with 6 default widgets.")

            # Try to get unauthenticated access of template dashboard (should fail)
            res = await client.get(
                f"{BASE_URL}/organizations/{org_id}/dashboards/{template_dash_id}"
            )
            assert res.status_code == 401, f"Expected 401 Unauthorized for unauthenticated dashboard retrieval, got {res.status_code}"

            # Analyst toggles dashboard share to public (should succeed)
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/dashboards/{template_dash_id}/share",
                json={"is_public": True},
                headers=analyst_headers
            )
            assert res.status_code == 200, f"Dashboard sharing toggle failed: {res.text}"
            shared_dash = res.json()
            assert shared_dash["is_public"] is True
            share_token = shared_dash["share_token"]
            assert share_token is not None
            print("      SUCCESS: Dashboard public sharing enabled, token allocated.")

            # Retrieve layout structure unauthenticated using the share token
            res = await client.get(
                f"{BASE_URL}/dashboards/share/{share_token}"
            )
            assert res.status_code == 200, f"Shared dashboard token retrieve failed: {res.text}"
            public_dash_out = res.json()
            assert public_dash_out["name"] == "Web Analytics Console"
            assert len(public_dash_out["widgets"]) == 6
            print("      SUCCESS: Cryptographically secure read-only public access verified.")

            # Analyst toggles dashboard share off (should succeed)
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/dashboards/{template_dash_id}/share",
                json={"is_public": False},
                headers=analyst_headers
            )
            assert res.status_code == 200, f"Dashboard share revoke failed: {res.text}"
            revoked_dash = res.json()
            assert revoked_dash["is_public"] is False
            assert revoked_dash["share_token"] is None
            
            # Access again using prior token (should now fail with 404)
            res = await client.get(
                f"{BASE_URL}/dashboards/share/{share_token}"
            )
            assert res.status_code == 404, f"Expected 404 Not Found for revoked share token, got {res.status_code}"
            print("      SUCCESS: Public share revoke properly enforced.")

            # 6. Test WebSocket secure handshakes and multi-tenant boundary checks
            print("[6/7] Testing WebSocket handshakes, tokens, and multi-tenant boundaries...")
            
            # Establish base ws URLs
            ws_url = f"{WS_BASE_URL}/organizations/{org_id}/ws/events"
            ws_url_cross = f"{WS_BASE_URL}/organizations/{cross_org_id}/ws/events"

            # Connect without token parameter
            try:
                async with websockets.connect(ws_url) as ws:
                    assert False, "Handshake should have failed without token."
            except Exception as e:
                print("      SUCCESS: Connection rejected without token parameter.")

            # Connect with invalid token
            try:
                async with websockets.connect(f"{ws_url}?token=invalid_token") as ws:
                    assert False, "Handshake should have failed with invalid token."
            except Exception as e:
                print("      SUCCESS: Connection rejected with invalid token parameter.")

            # Connect to Tenant A's stream using Tenant B's (Cross Org) Owner token (Isolation Check)
            try:
                async with websockets.connect(f"{ws_url}?token={cross_token}") as ws:
                    assert False, "Handshake should have failed for cross-tenant access."
            except Exception as e:
                print("      SUCCESS: Cross-tenant connection block validated.")

            # Successfully connect to Tenant A's stream using Analyst token
            print("      Connecting to WebSocket stream with Analyst token...")
            async with websockets.connect(f"{ws_url}?token={analyst_token}") as ws_analyst:
                print("      SUCCESS: Analyst WebSocket connection accepted.")

                # Validate WebSocket frame ping-pong
                await ws_analyst.send("ping")
                ping_reply = await ws_analyst.recv()
                ping_reply_data = json.loads(ping_reply)
                assert ping_reply_data["type"] == "pong"
                print("      SUCCESS: Custom WS ping-pong exchange validated.")

                # Keep connection open and proceed to Step 7 (telemetry stream validation)
                print("[7/7] Testing live telemetry ingestion-to-broadcast stream...")

                # First, provision a live API key under target organization (using Owner token)
                res = await client.post(
                    f"{BASE_URL}/organizations/{org_id}/api-keys",
                    json={"name": "E2E Live Stream Ingestion Key"},
                    headers=owner_headers
                )
                assert res.status_code == 201, f"API key generation failed: {res.text}"
                api_key_data = res.json()
                raw_api_key = api_key_data["raw_key"]
                print(f"      Provisioned API Key prefix: {api_key_data['prefix']}")

                # Ingest a live analytical event using the raw API key via HTTP REST endpoint
                event_name_sent = "btn_checkout_click"
                event_payload_sent = {
                    "cart_value": 129.99,
                    "items": 3,
                    "platform": "mobile"
                }
                
                # We expect the event to be published instantly
                ingest_payload = {
                    "event_name": event_name_sent,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": event_payload_sent
                }
                
                # Perform the POST request to trigger the ingestion and subsequent Redis publish
                print("      Ingesting event payload via REST API key route...")
                res_ingest = await client.post(
                    f"{BASE_URL}/ingest",
                    json=ingest_payload,
                    headers={"X-API-Key": raw_api_key}
                )
                assert res_ingest.status_code == 202, f"Event Ingestion failed: {res_ingest.text}"
                print("      REST API accepts event (HTTP 202). Awaiting WebSocket broadcast...")

                # Wait for broadcast frame on WebSocket stream
                # Set a 3.0s timeout to prevent hanging forever if it fails
                ws_response = await asyncio.wait_for(ws_analyst.recv(), timeout=3.0)
                ws_message = json.loads(ws_response)
                
                assert ws_message["type"] == "event"
                assert ws_message["data"]["event_name"] == event_name_sent
                assert ws_message["data"]["organization_id"] == str(org_id)
                assert ws_message["data"]["payload"]["cart_value"] == 129.99
                assert ws_message["data"]["payload"]["platform"] == "mobile"
                
                print("      SUCCESS: Telemetry event successfully streamed and validated!")

                # Test Live Event Isolation (events from Org A must not be sent to Org B)
                print("      Connecting to Cross Tenant Organization WebSocket stream...")
                async with websockets.connect(f"{ws_url_cross}?token={cross_token}") as ws_cross:
                    print("      SUCCESS: Cross Tenant WebSocket connection accepted.")

                    # Ingest another event under Tenant A
                    another_payload = {
                        "event_name": "page_view_isolation_check",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": {"browser": "Edge"}
                    }
                    res_ingest_2 = await client.post(
                        f"{BASE_URL}/ingest",
                        json=another_payload,
                        headers={"X-API-Key": raw_api_key}
                    )
                    assert res_ingest_2.status_code == 202

                    # Wait and assert that Analyst WS receives it (sub-millisecond broadcast roundtrip)
                    ws_response_analyst = await asyncio.wait_for(ws_analyst.recv(), timeout=3.0)
                    ws_message_analyst = json.loads(ws_response_analyst)
                    assert ws_message_analyst["data"]["event_name"] == "page_view_isolation_check"
                    print("      SUCCESS: Analyst client successfully received isolation check event.")

                    # Try to receive on Cross Org WS. It should timeout (1.5 seconds) since it is isolated!
                    try:
                        await asyncio.wait_for(ws_cross.recv(), timeout=1.5)
                        assert False, "Cross Org WebSocket should not have received Tenant A's event."
                    except asyncio.TimeoutError:
                        print("      SUCCESS: Tenant isolation verified. Cross Org client did not receive Tenant A event.")

            print("==============================================================")
            print("🎉 ALL TESTS PASSED: Dashboards, Widgets & WebSockets are 100% correct!")
            print("==============================================================")

        except Exception as e:
            print("\n==============================================================")
            print("❌ FAILURE during Dashboard & WebSockets E2E testing.")
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
    asyncio.run(run_dashboard_websockets_verification_suite())

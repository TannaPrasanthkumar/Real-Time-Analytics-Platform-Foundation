import asyncio
import sys
import os
import httpx
import uuid
import websockets
import json
import traceback
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
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
from app.models.alert import AlertRule, AlertHistory
from app.core.security import get_password_hash
from app.worker.tasks.alert import _execute_alerts_evaluation

# URLs for real running backend service in Docker Compose
BASE_URL = "http://127.0.0.1:8000/api/v1"
WS_BASE_URL = "ws://127.0.0.1:8000/api/v1"

TEST_ORG_SLUG = "alerts-test-org"
CROSS_ORG_SLUG = "alerts-cross-org"

TEST_OWNER_EMAIL = "alerts-owner@example.com"
TEST_ANALYST_EMAIL = "alerts-analyst@example.com"
TEST_VIEWER_EMAIL = "alerts-viewer@example.com"
CROSS_OWNER_EMAIL = "alerts-cross-owner@example.com"


async def clean_database() -> None:
    """Pre-cleans any testing data to ensure deterministic execution."""
    print("      Cleaning database testing records...")
    async with async_session() as session:
        for slug in [TEST_ORG_SLUG, CROSS_ORG_SLUG]:
            res = await session.execute(select(Organization).where(Organization.slug == slug))
            org = res.scalar_one_or_none()
            if org:
                # Delete alert history, alert rules first due to cascading
                await session.execute(delete(AlertHistory).where(AlertHistory.organization_id == org.id))
                await session.execute(delete(AlertRule).where(AlertRule.organization_id == org.id))
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
            full_name="Alerts Analyst",
            is_active=True,
            is_superuser=False
        )
        session.add(analyst)
        
        # Check and create viewer
        viewer = User(
            email=TEST_VIEWER_EMAIL,
            hashed_password=hashed_pwd,
            full_name="Alerts Viewer",
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


async def run_alerts_notifications_verification_suite() -> None:
    """Executes the E2E verification suite for Alerts, Transitions, Muting, recovery, and WebSockets."""
    print("==============================================================")
    print("🚀 Starting Alerts & Notifications E2E Verification Suite")
    print("==============================================================")

    # 1. Clean Database
    print("[1/8] Initializing database clean state...")
    await clean_database()
    
    await asyncio.sleep(0.5)

    async with httpx.AsyncClient() as client:
        try:
            # 2. Provision Tenants & Fetch Tokens
            print("[2/8] Provisioning dual tenants and user roles...")
            
            # Signup Target Org Owner
            owner_signup = {
                "email": TEST_OWNER_EMAIL,
                "password": "SecurePassword123",
                "full_name": "Alerts Owner",
                "organization_name": "Alerts Test Org"
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
                "organization_name": "Alerts Cross Org"
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

            # 3. Test Alert Rules CRUD & Tenant Isolation
            print("[3/8] Testing Alert Rules CRUD & RBAC isolation constraints...")
            
            # Viewer tries to create an alert rule (should fail with 403)
            rule_payload = {
                "name": "Viewer Custom Rule",
                "description": "Viewer should not be allowed to create alert rules",
                "is_enabled": True,
                "metric_type": "error_count",
                "operator": ">",
                "threshold": 5.0,
                "time_window_minutes": 10,
                "snooze_duration_minutes": 30,
                "slack_webhook": "https://hooks.slack.com/services/test/webhook",
                "email_recipient": "test@example.com"
            }
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/alerts/rules",
                json=rule_payload,
                headers=viewer_headers
            )
            assert res.status_code == 403, f"Expected 403 Forbidden for Viewer alert rule creation, got {res.status_code}"

            # Analyst creates a rule (should succeed)
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/alerts/rules",
                json=rule_payload,
                headers=analyst_headers
            )
            assert res.status_code == 201, f"Analyst alert rule creation failed: {res.text}"
            rule_data = res.json()
            rule_id = uuid.UUID(rule_data["id"])
            assert rule_data["name"] == "Viewer Custom Rule"
            assert rule_data["current_state"] == "Resolved"
            print("      SUCCESS: Alert rule successfully created by Analyst.")

            # Viewer lists rules (should succeed)
            res = await client.get(
                f"{BASE_URL}/organizations/{org_id}/alerts/rules",
                headers=viewer_headers
            )
            assert res.status_code == 200, f"Viewer listing alert rules failed: {res.text}"
            rules_list = res.json()
            assert len(rules_list) >= 1
            assert any(r["id"] == str(rule_id) for r in rules_list)
            print("      SUCCESS: Viewer successfully listed alert rules.")

            # Cross Tenant tries to read rule (should fail with 404 since it's tenant-scoped)
            res = await client.get(
                f"{BASE_URL}/organizations/{cross_org_id}/alerts/rules/{rule_id}",
                headers=cross_headers
            )
            assert res.status_code == 404, f"Expected 404 Not Found for cross-tenant alert rule read, got {res.status_code}"
            
            # Cross Tenant tries to update rule (should fail with 404 since they cannot access Tenant A rules)
            res = await client.put(
                f"{BASE_URL}/organizations/{cross_org_id}/alerts/rules/{rule_id}",
                json={"name": "Cross Tenant Modified Rule Name"},
                headers=cross_headers
            )
            assert res.status_code == 404, f"Expected 404 Not Found for cross-tenant alert rule update, got {res.status_code}"
            print("      SUCCESS: Cross-tenant isolation boundaries validated.")

            # Analyst updates rule name (should succeed)
            res = await client.put(
                f"{BASE_URL}/organizations/{org_id}/alerts/rules/{rule_id}",
                json={
                    "name": "E2E Error Limit Alert",
                    "threshold": 3.0  # decrease threshold to 3.0 to trigger easier
                },
                headers=analyst_headers
            )
            assert res.status_code == 200, f"Analyst update alert rule failed: {res.text}"
            updated_rule = res.json()
            assert updated_rule["name"] == "E2E Error Limit Alert"
            assert updated_rule["threshold"] == 3.0
            print("      SUCCESS: Alert rule updated by Analyst.")

            # 4. Ingest Event Telemetry to Violate Threshold
            print("[4/8] Ingesting event telemetry to trigger alert threshold violations...")
            
            # Create a live API key under target organization (using Owner token)
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/api-keys",
                json={"name": "E2E Ingestion Key for Alerts"},
                headers=owner_headers
            )
            assert res.status_code == 201, f"API key generation failed: {res.text}"
            api_key_data = res.json()
            raw_api_key = api_key_data["raw_key"]
            print(f"      Provisioned API Key prefix: {api_key_data['prefix']}")

            # Ingest 1 'error' event via REST API to verify API key validation and 202 response
            print("      Ingesting 1 error event via REST API key route...")
            ingest_payload = {
                "event_name": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "message": "E2E REST API error count 0",
                    "code": 500
                }
            }
            res_ingest = await client.post(
                f"{BASE_URL}/ingest",
                json=ingest_payload,
                headers={"X-API-Key": raw_api_key}
            )
            assert res_ingest.status_code == 202, f"Event Ingestion failed: {res_ingest.text}"
            
            # Seed 4 more error events directly to make sure we violate threshold > 3.0 immediately
            print("      Seeding 4 more error events directly into the database...")
            async with async_session() as session:
                for i in range(1, 5):
                    event = Event(
                        id=uuid.uuid4(),
                        organization_id=org_id,
                        event_name="error",
                        timestamp=datetime.now(timezone.utc),
                        payload={"message": f"E2E direct seed error count {i}", "code": 500}
                    )
                    session.add(event)
                await session.commit()
            print("      Database seeding of error events completed.")

            # 5. Connect WebSocket & Run Scheduled Evaluation
            print("[5/8] Connecting WebSocket client and triggering alert evaluation...")
            
            ws_url = f"{WS_BASE_URL}/organizations/{org_id}/ws/events?token={analyst_token}"
            async with websockets.connect(ws_url) as ws_client:
                print("      WebSocket client successfully connected and subscribed to live stream.")

                # We patch httpx.AsyncClient.post to intercept outgoing Slack webhooks and verify payload.
                with patch("app.services.alert.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_slack_post:
                    mock_slack_post.return_value = httpx.Response(200, text="ok")
                    
                    print("      Executing scheduled evaluation task synchronously...")
                    eval_result = await _execute_alerts_evaluation()
                    print(f"      Evaluation task result: {eval_result}")
                    assert eval_result["success"] is True
                    assert eval_result["evaluated"] >= 1
                    assert eval_result["transitions"] >= 1

                    # Sleep slightly to allow background task of _send_slack_http_post to execute
                    await asyncio.sleep(0.5)

                    # Verify that Slack POST was made with correct block kit contents
                    print("      Verifying Slack Webhook payload dispatch...")
                    assert mock_slack_post.called
                    slack_call_args = mock_slack_post.call_args
                    slack_url = slack_call_args[0][0]
                    slack_payload = slack_call_args[1]["json"]
                    
                    assert slack_url == "https://hooks.slack.com/services/test/webhook"
                    assert "E2E Error Limit Alert" in slack_payload["text"]
                    assert "🚨" in slack_payload["text"]
                    assert slack_payload["blocks"][0]["text"]["text"] is not None
                    print("      SUCCESS: Outgoing Slack webhook payload successfully verified.")

                # Wait and assert that WebSocket receives the live alert broadcast frame
                print("      Awaiting real-time WebSocket alert broadcast frame...")
                ws_response = await asyncio.wait_for(ws_client.recv(), timeout=3.0)
                ws_message = json.loads(ws_response)
                
                assert ws_message["type"] == "alert"
                assert ws_message["data"]["rule_name"] == "E2E Error Limit Alert"
                assert ws_message["data"]["state"] == "Triggered"
                assert ws_message["data"]["value"] == 4.0
                assert ws_message["data"]["threshold"] == 3.0
                print("      SUCCESS: Real-time WebSocket alert broadcast received and validated.")

            # 6. Verify Database In-App History Audit & Email Drafting
            print("[6/8] Verifying database history log records and mock email drafting...")
            
            # Retrieve alert histories
            res = await client.get(
                f"{BASE_URL}/organizations/{org_id}/alerts/history",
                headers=viewer_headers
            )
            assert res.status_code == 200, f"Retrieval of alert histories failed: {res.text}"
            histories = res.json()
            assert len(histories) >= 1
            triggered_history = [h for h in histories if h["state"] == "Triggered" and h["alert_rule_id"] == str(rule_id)]
            assert len(triggered_history) == 1
            assert triggered_history[0]["value"] == 4.0
            assert triggered_history[0]["threshold"] == 3.0
            
            # Check the generated email draft stored inside details
            details = triggered_history[0]["details"]
            assert "email_draft" in details
            assert details["email_draft"]["recipient"] == "test@example.com"
            assert "🚨 ALERT TRIGGERED: E2E Error Limit Alert" in details["email_draft"]["subject"]
            assert "E2E Error Limit Alert" in details["email_draft"]["body"]
            print("      SUCCESS: In-app history log and simulated email draft validated.")

            # 7. Test Muting/Snoozing Functionality
            print("[7/8] Testing manual alert snooze/mute transition capabilities...")
            
            # Viewer tries to snooze (should fail with 403)
            snooze_payload = {"snooze_duration_minutes": 30}
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/alerts/rules/{rule_id}/snooze",
                json=snooze_payload,
                headers=viewer_headers
            )
            assert res.status_code == 403, f"Expected 403 Forbidden for Viewer alert snooze, got {res.status_code}"

            # Analyst snoozes rule (should succeed)
            res = await client.post(
                f"{BASE_URL}/organizations/{org_id}/alerts/rules/{rule_id}/snooze",
                json=snooze_payload,
                headers=analyst_headers
            )
            assert res.status_code == 200, f"Analyst snooze alert rule failed: {res.text}"
            snooze_history = res.json()
            assert snooze_history["state"] == "Muted"
            assert snooze_history["details"]["action"] == "manual_snooze"
            assert snooze_history["details"]["snooze_minutes"] == 30
            print("      SUCCESS: Alert rule successfully muted by Analyst.")

            # Let's verify rule is muted in DB
            res = await client.get(
                f"{BASE_URL}/organizations/{org_id}/alerts/rules/{rule_id}",
                headers=viewer_headers
            )
            assert res.status_code == 200
            rule_details = res.json()
            assert rule_details["current_state"] == "Muted"
            assert rule_details["muted_until"] is not None
            
            # Ingest 1 more error event (total is 5 error events, still violating)
            ingest_payload = {
                "event_name": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {"message": "Violating while muted"}
            }
            res_ingest = await client.post(
                f"{BASE_URL}/ingest",
                json=ingest_payload,
                headers={"X-API-Key": raw_api_key}
            )
            assert res_ingest.status_code == 202
            
            # Seed 1 more error event directly to guarantee it violates
            async with async_session() as session:
                event = Event(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    event_name="error",
                    timestamp=datetime.now(timezone.utc),
                    payload={"message": "Violating while muted direct", "code": 500}
                )
                session.add(event)
                await session.commit()

            # Run evaluation synchronously. Rule is muted so there should be no transitions.
            eval_result = await _execute_alerts_evaluation()
            assert eval_result["success"] is True
            assert eval_result["transitions"] == 0
            print("      SUCCESS: Threshold violations successfully suppressed while muted.")

            # 8. Test Recovery Transition
            print("[8/8] Testing recovery transition to 'Resolved' after metrics normalize...")
            
            # Move the events timestamp older than 10 minutes to simulate no errors in the timeframe
            async with async_session() as session:
                older_time = datetime.now(timezone.utc) - timedelta(minutes=15)
                q = text("""
                    UPDATE events 
                    SET timestamp = :older_time 
                    WHERE organization_id = :org_id 
                      AND event_name = 'error'
                """)
                await session.execute(q, {"older_time": older_time, "org_id": org_id})
                await session.commit()
            print("      Simulating normal status by moving error event timestamps older than window.")

            # We patch httpx.AsyncClient.post to intercept outgoing recovery Slack webhooks
            with patch("app.services.alert.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_slack_post:
                mock_slack_post.return_value = httpx.Response(200, text="ok")
                
                # Execute evaluation. It should see 0 errors, which is <= 3.0 threshold.
                # Since the rule was 'Muted', transitioning to healthy parameters will bring it back to 'Resolved'!
                eval_result = await _execute_alerts_evaluation()
                assert eval_result["success"] is True
                assert eval_result["transitions"] >= 1

                # Sleep slightly to allow background task of _send_slack_http_post to execute
                await asyncio.sleep(0.5)

                # Assert rule transitioned back to Resolved
                res = await client.get(
                    f"{BASE_URL}/organizations/{org_id}/alerts/rules/{rule_id}",
                    headers=viewer_headers
                )
                assert res.status_code == 200
                rule_details = res.json()
                assert rule_details["current_state"] == "Resolved"
                assert rule_details["muted_until"] is None
                print("      SUCCESS: Alert rule transitioned back to 'Resolved'.")

                # Verify Slack Recovery POST payload
                assert mock_slack_post.called
                slack_payload = mock_slack_post.call_args[1]["json"]
                assert "E2E Error Limit Alert" in slack_payload["text"]
                assert "✅" in slack_payload["text"]
                print("      SUCCESS: Recovery Slack webhook payload successfully verified.")

            # Verify that recovery history log was written and email recovery draft was simulated
            res = await client.get(
                f"{BASE_URL}/organizations/{org_id}/alerts/history",
                headers=viewer_headers
            )
            assert res.status_code == 200
            histories = res.json()
            resolved_history = [h for h in histories if h["state"] == "Resolved" and h["alert_rule_id"] == str(rule_id)]
            assert len(resolved_history) == 1
            assert resolved_history[0]["value"] == 0.0
            
            details = resolved_history[0]["details"]
            assert "email_draft" in details
            assert details["email_draft"]["recipient"] == "test@example.com"
            assert "✅ ALERT RESOLVED: E2E Error Limit Alert" in details["email_draft"]["subject"]
            print("      SUCCESS: Recovery DB audit log and email recovery draft validated.")

            print("==============================================================")
            print("🎉 ALL TESTS PASSED: Alerts & Notifications are 100% correct!")
            print("==============================================================")

        except Exception as e:
            print("\n==============================================================")
            print("❌ FAILURE during Alerts & Notifications E2E testing.")
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
    asyncio.run(run_alerts_notifications_verification_suite())

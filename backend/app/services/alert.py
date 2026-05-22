import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import httpx
import structlog
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertRule, AlertHistory
from app.repositories.alert import AlertRuleRepository, AlertHistoryRepository
from app.services.websocket import publish_live_message
from app.core.exceptions import NotFoundException
from app.schemas.alert import AlertRuleCreate, AlertRuleUpdate

logger = structlog.get_logger(__name__)


class AlertService:
    """Service coordinating Alert Rule states, snooze rules, and multi-channel notification dispatches."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.rule_repo = AlertRuleRepository(db)
        self.history_repo = AlertHistoryRepository(db)

    async def get_rule_for_org(self, organization_id: uuid.UUID, rule_id: uuid.UUID) -> AlertRule:
        """Fetch alert rule strictly inside organizational tenant boundary."""
        rule = await self.rule_repo.get_by_org(organization_id, rule_id)
        if not rule:
            raise NotFoundException(
                message=f"Alert rule with ID '{rule_id}' was not found in this organization."
            )
        return rule

    async def get_multi_rules_for_org(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> List[AlertRule]:
        """Fetch multiple alert rules under a specific organization tenant."""
        return await self.rule_repo.get_multi_by_org(organization_id, skip=skip, limit=limit)

    async def create_rule_for_org(self, organization_id: uuid.UUID, schema: AlertRuleCreate) -> AlertRule:
        """Create a new custom alert rule linked to the tenant organization."""
        obj_data = schema.model_dump()
        obj_data["organization_id"] = organization_id
        obj_data["current_state"] = "Resolved"
        obj_data["muted_until"] = None
        return await self.rule_repo.create(obj_data)

    async def update_rule_for_org(
        self, organization_id: uuid.UUID, rule_id: uuid.UUID, schema: AlertRuleUpdate
    ) -> AlertRule:
        """Update an alert rule strictly inside organizational boundaries."""
        rule = await self.get_rule_for_org(organization_id, rule_id)
        return await self.rule_repo.update(rule, schema)

    async def delete_rule_for_org(self, organization_id: uuid.UUID, rule_id: uuid.UUID) -> AlertRule:
        """Soft delete an alert rule strictly inside organizational boundaries."""
        rule = await self.get_rule_for_org(organization_id, rule_id)
        return await self.rule_repo.soft_delete(rule)

    async def get_multi_histories_for_org(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> List[AlertHistory]:
        """Fetch multiple alert histories under a specific organization tenant."""
        return await self.history_repo.get_multi_by_org(organization_id, skip=skip, limit=limit)

    def is_threshold_violated(self, value: float, threshold: float, operator: str) -> bool:
        """Evaluate if the current metric value violates the alert rule threshold."""
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        return False

    async def evaluate_rule(self, rule: AlertRule, current_value: float) -> Optional[AlertHistory]:
        """Core state machine evaluating a rule, transitioning states, and dispatching alerts."""
        now = datetime.now(timezone.utc)
        violated = self.is_threshold_violated(current_value, rule.threshold, rule.operator)

        # 1. Handle muted/snooze expiration checks
        is_currently_muted = False
        if rule.current_state == "Muted":
            if rule.muted_until and rule.muted_until > now:
                is_currently_muted = True
            else:
                # Mute duration has expired. Revert to Resolved so it can re-trigger if still violated.
                rule.current_state = "Resolved"
                rule.muted_until = None
                self.db.add(rule)
                await self.db.commit()
                await self.db.refresh(rule)

        old_state = rule.current_state

        # 2. Evaluate state transitions
        new_history = None
        if violated:
            if not is_currently_muted and old_state != "Triggered":
                # Transition: Resolved -> Triggered
                rule.current_state = "Triggered"
                self.db.add(rule)
                await self.db.commit()
                await self.db.refresh(rule)

                # Formulate notifications and history audit
                details = await self._dispatch_notifications(rule, current_value, is_trigger=True)

                new_history = AlertHistory(
                    alert_rule_id=rule.id,
                    organization_id=rule.organization_id,
                    state="Triggered",
                    value=current_value,
                    threshold=rule.threshold,
                    details=details
                )
                self.db.add(new_history)
                await self.db.commit()
                await self.db.refresh(new_history)
        else:
            if old_state in ("Triggered", "Muted"):
                # Transition: Triggered/Muted -> Resolved (healthy again)
                rule.current_state = "Resolved"
                rule.muted_until = None
                self.db.add(rule)
                await self.db.commit()
                await self.db.refresh(rule)

                # Formulate recovery notifications and history audit
                details = await self._dispatch_notifications(rule, current_value, is_trigger=False)

                new_history = AlertHistory(
                    alert_rule_id=rule.id,
                    organization_id=rule.organization_id,
                    state="Resolved",
                    value=current_value,
                    threshold=rule.threshold,
                    details=details
                )
                self.db.add(new_history)
                await self.db.commit()
                await self.db.refresh(new_history)

        return new_history

    async def snooze_rule(self, organization_id: uuid.UUID, rule_id: uuid.UUID, snooze_minutes: int) -> AlertHistory:
        """Manually mute/snooze an alert rule for a configured lookahead duration."""
        rule = await self.get_rule_for_org(organization_id, rule_id)
        now = datetime.now(timezone.utc)
        muted_until = now + timedelta(minutes=snooze_minutes)

        rule.current_state = "Muted"
        rule.muted_until = muted_until
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)

        details = {
            "action": "manual_snooze",
            "snooze_minutes": snooze_minutes,
            "muted_until": muted_until.isoformat()
        }

        # Create history audit log
        new_history = AlertHistory(
            alert_rule_id=rule.id,
            organization_id=rule.organization_id,
            state="Muted",
            value=0.0,
            threshold=rule.threshold,
            details=details
        )
        self.db.add(new_history)
        await self.db.commit()
        await self.db.refresh(new_history)

        # Broadcast update to websocket clients
        await self._broadcast_websocket_alert(rule, value=0.0)

        return new_history

    async def _dispatch_notifications(self, rule: AlertRule, value: float, is_trigger: bool) -> Dict[str, Any]:
        """Dispatch notifications asynchronously to Slack, Email, and live WebSockets."""
        details = {}

        # 1. Draft mock Email
        if rule.email_recipient:
            email_data = self._generate_email_draft(rule, value, is_trigger)
            details["email_draft"] = email_data
            logger.info(
                "Simulated outgoing email notification drafted",
                recipient=rule.email_recipient,
                subject=email_data["subject"],
                body=email_data["body"]
            )

        # 2. Push real-time event to live WebSocket consoles via Redis Pub/Sub
        await self._broadcast_websocket_alert(rule, value)

        # 3. Post to Slack webhook URL if configured
        if rule.slack_webhook:
            slack_payload = self._generate_slack_payload(rule, value, is_trigger)
            details["slack_notification"] = {
                "webhook": rule.slack_webhook,
                "payload": slack_payload
            }
            # Execute HTTP call asynchronously in a safe task to avoid blocking execution
            asyncio.create_task(self._send_slack_http_post(rule.slack_webhook, slack_payload))

        return details

    async def _broadcast_websocket_alert(self, rule: AlertRule, value: float) -> None:
        """Publishes real-time alert updates onto Redis Pub/Sub for WebSockets dashboard streaming."""
        payload = {
            "type": "alert",
            "data": {
                "rule_id": str(rule.id),
                "rule_name": rule.name,
                "organization_id": str(rule.organization_id),
                "state": rule.current_state,
                "metric_type": rule.metric_type,
                "value": value,
                "threshold": rule.threshold,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        await publish_live_message(rule.organization_id, payload)

    def _generate_email_draft(self, rule: AlertRule, value: float, is_trigger: bool) -> Dict[str, str]:
        """Generates structured email subject and body content."""
        if is_trigger:
            subject = f"🚨 ALERT TRIGGERED: {rule.name}"
            body = (
                f"Alert Rule '{rule.name}' has been triggered!\n\n"
                f"Organization ID: {rule.organization_id}\n"
                f"Metric Evaluated: {rule.metric_type}\n"
                f"Violation Parameters: {rule.operator} {rule.threshold}\n"
                f"Current Value Recorded: {value}\n"
                f"Evaluation Timeframe: Last {rule.time_window_minutes} minutes\n\n"
                f"Please review your dashboard for live logs."
            )
        else:
            subject = f"✅ ALERT RESOLVED: {rule.name}"
            body = (
                f"Alert Rule '{rule.name}' has recovered to healthy parameters.\n\n"
                f"Organization ID: {rule.organization_id}\n"
                f"Metric Evaluated: {rule.metric_type}\n"
                f"Current Value Recorded: {value} (healthy)\n\n"
                f"Thank you."
            )
        return {"recipient": rule.email_recipient, "subject": subject, "body": body}

    def _generate_slack_payload(self, rule: AlertRule, value: float, is_trigger: bool) -> Dict[str, Any]:
        """Generates JSON-compatible Slack Block Kit payloads."""
        if is_trigger:
            text = f"🚨 Alert *{rule.name}* triggered! Value: {value} (threshold: {rule.threshold})"
            mrkdwn = (
                f"🚨 *Alert Triggered: {rule.name}*\n"
                f"*Org ID*: `{rule.organization_id}`\n"
                f"*Metric*: `{rule.metric_type}`\n"
                f"*Operator*: `{rule.operator}`\n"
                f"*Threshold*: `{rule.threshold}`\n"
                f"*Current Value*: *{value}*\n"
                f"*Lookback Window*: `{rule.time_window_minutes} mins`"
            )
        else:
            text = f"✅ Alert *{rule.name}* resolved! Value: {value}"
            mrkdwn = (
                f"✅ *Alert Resolved: {rule.name}*\n"
                f"*Org ID*: `{rule.organization_id}`\n"
                f"*Metric*: `{rule.metric_type}`\n"
                f"*Current Value*: *{value}* (healthy)"
            )

        return {
            "text": text,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": mrkdwn
                    }
                }
            ]
        }

    async def _send_slack_http_post(self, webhook_url: str, payload: dict) -> None:
        """Executes safe outgoing POST to Slack webhook with a 2-second timeout."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=payload, timeout=2.0)
                if resp.status_code >= 400:
                    logger.warning(
                        "Slack webhook returned non-success response code",
                        status_code=resp.status_code,
                        response=resp.text
                    )
        except Exception as e:
            logger.error("Failed to dispatch Slack webhook notification", error=str(e))

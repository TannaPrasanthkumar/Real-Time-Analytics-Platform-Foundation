import uuid
from typing import List
from fastapi import APIRouter, Depends, status, Path

from app.api.deps import get_db, RequireRole
from app.models.user import UserRole
from app.schemas.alert import (
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleOut,
    AlertRuleSnooze,
    AlertHistoryOut
)
from app.services.alert import AlertService

router = APIRouter(tags=["Alerts"])


# ------------------------------------------------------------------------------
# Alert Rule Endpoints
# ------------------------------------------------------------------------------

@router.post(
    "/organizations/{org_id}/alerts/rules",
    response_model=AlertRuleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def create_alert_rule(
    org_id: uuid.UUID,
    schema: AlertRuleCreate,
    db=Depends(get_db)
) -> AlertRuleOut:
    """Create a new alert rule. Requires Analyst role or higher."""
    service = AlertService(db)
    return await service.create_rule_for_org(org_id, schema)


@router.get(
    "/organizations/{org_id}/alerts/rules",
    response_model=List[AlertRuleOut],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def list_alert_rules(
    org_id: uuid.UUID,
    db=Depends(get_db)
) -> List[AlertRuleOut]:
    """List all alert rules for the organization. Requires Viewer role or higher."""
    service = AlertService(db)
    return await service.get_multi_rules_for_org(org_id)


@router.get(
    "/organizations/{org_id}/alerts/rules/{rule_id}",
    response_model=AlertRuleOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def get_alert_rule(
    org_id: uuid.UUID,
    rule_id: uuid.UUID,
    db=Depends(get_db)
) -> AlertRuleOut:
    """Get an alert rule by ID. Requires Viewer role or higher."""
    service = AlertService(db)
    return await service.get_rule_for_org(org_id, rule_id)


@router.put(
    "/organizations/{org_id}/alerts/rules/{rule_id}",
    response_model=AlertRuleOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def update_alert_rule(
    org_id: uuid.UUID,
    rule_id: uuid.UUID,
    schema: AlertRuleUpdate,
    db=Depends(get_db)
) -> AlertRuleOut:
    """Update an alert rule. Requires Analyst role or higher."""
    service = AlertService(db)
    return await service.update_rule_for_org(org_id, rule_id, schema)


@router.delete(
    "/organizations/{org_id}/alerts/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def delete_alert_rule(
    org_id: uuid.UUID,
    rule_id: uuid.UUID,
    db=Depends(get_db)
) -> None:
    """Soft delete an alert rule. Requires Analyst role or higher."""
    service = AlertService(db)
    await service.delete_rule_for_org(org_id, rule_id)


@router.post(
    "/organizations/{org_id}/alerts/rules/{rule_id}/snooze",
    response_model=AlertHistoryOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def snooze_alert_rule(
    org_id: uuid.UUID,
    rule_id: uuid.UUID,
    schema: AlertRuleSnooze,
    db=Depends(get_db)
) -> AlertHistoryOut:
    """Manually snooze/mute an alert rule for configured minutes. Requires Analyst role or higher."""
    service = AlertService(db)
    return await service.snooze_rule(org_id, rule_id, schema.snooze_duration_minutes)


# ------------------------------------------------------------------------------
# Alert History Endpoints
# ------------------------------------------------------------------------------

@router.get(
    "/organizations/{org_id}/alerts/history",
    response_model=List[AlertHistoryOut],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def list_alert_history(
    org_id: uuid.UUID,
    db=Depends(get_db)
) -> List[AlertHistoryOut]:
    """List all alert history logs in chronological order. Requires Viewer role or higher."""
    service = AlertService(db)
    return await service.get_multi_histories_for_org(org_id)

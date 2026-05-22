import os
import uuid
import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.services.base import BaseService
from app.repositories.report import ReportScheduleRepository, ReportHistoryRepository
from app.repositories.dashboard import DashboardRepository
from app.models.report import ReportSchedule, ReportHistory
from app.schemas.report import ReportScheduleCreate, ReportScheduleUpdate
from app.core.exceptions import NotFoundException
from app.services.analytics import AnalyticsService

logger = structlog.get_logger(__name__)


class ReportService(BaseService[ReportSchedule, ReportScheduleRepository]):
    """Service layer coordinating scheduled report CRUD, background snapshots, and simulated emailing."""

    def __init__(self, session: AsyncSession):
        super().__init__(ReportScheduleRepository(session))
        self.session = session
        self.history_repository = ReportHistoryRepository(session)
        self.dashboard_repository = DashboardRepository(session)
        self.analytics_service = AnalyticsService(session)
        self.logger = logger.bind(service="ReportService")

    async def get_schedule_for_org(self, organization_id: uuid.UUID, schedule_id: uuid.UUID) -> ReportSchedule:
        """Fetch report schedule strictly inside organizational boundary."""
        schedule = await self.repository.get_by_org(organization_id, schedule_id)
        if not schedule:
            raise NotFoundException(
                message=f"Report Schedule with ID '{schedule_id}' was not found in this organization."
            )
        return schedule

    async def get_multi_schedules_for_org(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> List[ReportSchedule]:
        """Fetch multiple report schedules under a specific organization tenant."""
        return await self.repository.get_multi_by_org(organization_id, skip=skip, limit=limit)

    async def create_schedule_for_org(self, organization_id: uuid.UUID, schema: ReportScheduleCreate) -> ReportSchedule:
        """Create a new report schedule linked to the tenant organization."""
        obj_data = schema.model_dump()
        obj_data["organization_id"] = organization_id
        return await self.repository.create(obj_data)

    async def update_schedule_for_org(
        self, organization_id: uuid.UUID, schedule_id: uuid.UUID, schema: ReportScheduleUpdate
    ) -> ReportSchedule:
        """Update a report schedule strictly inside organizational boundaries."""
        schedule = await self.get_schedule_for_org(organization_id, schedule_id)
        return await self.repository.update(schedule, schema)

    async def delete_schedule_for_org(self, organization_id: uuid.UUID, schedule_id: uuid.UUID) -> ReportSchedule:
        """Soft delete a report schedule strictly inside organizational boundaries."""
        schedule = await self.get_schedule_for_org(organization_id, schedule_id)
        return await self.repository.soft_delete(schedule)

    # --------------------------------------------------------------------------
    # History CRUD Operations
    # --------------------------------------------------------------------------

    async def get_multi_histories_for_org(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> List[ReportHistory]:
        """Fetch multiple report histories belonging to a specific organization."""
        return await self.history_repository.get_multi_by_org(organization_id, skip=skip, limit=limit)

    async def get_history_for_org(self, organization_id: uuid.UUID, history_id: uuid.UUID) -> ReportHistory:
        """Fetch a single report history log by ID under organization boundaries."""
        history = await self.history_repository.get_by_org(organization_id, history_id)
        if not history:
            raise NotFoundException(
                message=f"Report History with ID '{history_id}' was not found in this organization."
            )
        return history

    # --------------------------------------------------------------------------
    # Snapshots & HTML Report Compilation
    # --------------------------------------------------------------------------

    async def generate_dashboard_report(self, schedule_id: uuid.UUID) -> ReportHistory:
        """Executes current widget analytics, compiles a premium styled HTML summary, and dispatches mock emails."""
        self.logger.info("Starting scheduled report snapshot generation", schedule_id=schedule_id)
        
        # Load the schedule
        schedule = await self.repository.get(schedule_id)
        if not schedule or schedule.is_deleted:
            self.logger.error("Report schedule not found or deleted", schedule_id=schedule_id)
            raise NotFoundException(message=f"Report Schedule with ID '{schedule_id}' does not exist.")

        # Instantiate empty history record to track execution state
        history_entry = ReportHistory(
            report_schedule_id=schedule_id,
            organization_id=schedule.organization_id,
            status="pending",
            triggered_at=datetime.datetime.utcnow()
        )
        self.session.add(history_entry)
        await self.session.commit()
        await self.session.refresh(history_entry)

        try:
            # 1. Fetch the Dashboard
            dashboard = None
            dashboard_name = "Organization Overview"
            widgets = []
            if schedule.dashboard_id:
                dashboard = await self.dashboard_repository.get_by_org(schedule.organization_id, schedule.dashboard_id)
                if dashboard and not dashboard.is_deleted:
                    dashboard_name = dashboard.name
                    widgets = [w for w in dashboard.widgets if not w.is_deleted]
                else:
                    self.logger.warning("Linked dashboard not found or soft-deleted, falling back to org snapshot.", dashboard_id=schedule.dashboard_id)

            # 2. Determine Lookback window
            end_time = datetime.datetime.utcnow()
            if schedule.frequency.lower() == "daily":
                start_time = end_time - datetime.timedelta(days=1)
                time_label = "Past 24 Hours"
            elif schedule.frequency.lower() == "weekly":
                start_time = end_time - datetime.timedelta(days=7)
                time_label = "Past 7 Days"
            elif schedule.frequency.lower() == "monthly":
                start_time = end_time - datetime.timedelta(days=30)
                time_label = "Past 30 Days"
            else:
                start_time = end_time - datetime.timedelta(days=1)
                time_label = f"Lookback Period ({schedule.frequency})"

            # 3. Retrieve general analytical metrics
            overview_data = await self.analytics_service.get_overview(
                organization_id=schedule.organization_id,
                start=start_time,
                end=end_time,
                use_cache=False
            )

            # 4. Evaluate Dashboard widgets configs
            compiled_widgets_html = ""
            for widget in widgets:
                widget_html = await self._compile_widget_to_html(widget, schedule.organization_id, start_time, end_time)
                compiled_widgets_html += widget_html

            # Fallback if no widgets exist
            if not compiled_widgets_html:
                compiled_widgets_html = """
                <div class="glass-card text-center" style="padding: 40px; margin-bottom: 24px;">
                    <p style="color: var(--text-muted); margin: 0; font-size: 16px;">No dynamic widgets configured. Showing general organization telemetry overview above.</p>
                </div>
                """

            # 5. Render standard premium HTML template
            html_content = self._render_premium_html_template(
                org_name="Antigravity Workspace",
                dashboard_name=dashboard_name,
                time_label=time_label,
                frequency=schedule.frequency,
                overview_data=overview_data,
                widgets_html=compiled_widgets_html,
                generated_at=end_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            )

            # 6. Write HTML snapshot file to disk
            archive_dir = "/app/reports_archive" if os.path.exists("/app") else os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports_archive")
            os.makedirs(archive_dir, exist_ok=True)
            
            filename = f"report_{schedule_id}_{history_entry.id}.html"
            file_path = os.path.join(archive_dir, filename)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            # 7. Simulate dispatching emails with structured logging
            self.logger.info(
                "Simulating email dispatch of scheduled report summary",
                report_schedule_name=schedule.name,
                frequency=schedule.frequency,
                recipients=schedule.recipients,
                file_archive_path=file_path,
                page_views=overview_data.get("page_views", 0),
                unique_visitors=overview_data.get("unique_visitors", 0),
                bounce_rate=f"{overview_data.get('bounce_rate', 0.0)}%",
                avg_session_duration=f"{overview_data.get('avg_session_duration', 0.0)}s"
            )

            # Update history to success
            history_entry.status = "success"
            history_entry.file_path = file_path
            await self.session.commit()
            await self.session.refresh(history_entry)
            
            return history_entry

        except Exception as e:
            self.logger.exception("Failed generating scheduled report snapshot", schedule_id=schedule_id, history_id=history_entry.id)
            history_entry.status = "failed"
            history_entry.error_message = str(e)
            await self.session.commit()
            await self.session.refresh(history_entry)
            raise e

    async def _compile_widget_to_html(
        self, widget: Any, organization_id: uuid.UUID, start_time: datetime.datetime, end_time: datetime.datetime
    ) -> str:
        """Fetch widget data and compile it to a clean HTML card representation."""
        try:
            widget_type = widget.type.lower()
            query_config = widget.query_config or {}
            
            if widget_type == "kpi":
                metric_type = query_config.get("metric_type", "page_views")
                # We can fetch general overview or calculate widget lookbacks
                overview = await self.analytics_service.get_overview(organization_id, start_time, end_time, use_cache=False)
                val = overview.get(metric_type, 0)
                change_val = overview.get(f"{metric_type}_change", 0.0)
                
                label = widget.name or metric_type.replace("_", " ").title()
                suffix = "%" if "rate" in metric_type else ("s" if "duration" in metric_type else "")
                
                change_class = "trend-up" if change_val >= 0 else "trend-down"
                change_arrow = "+" if change_val >= 0 else ""
                
                return f"""
                <div class="glass-card kpi-card" style="margin-bottom: 24px;">
                    <div class="card-header">{label}</div>
                    <div style="display: flex; align-items: baseline; justify-content: space-between; margin-top: 12px;">
                        <span class="kpi-value">{val}{suffix}</span>
                        <span class="trend-tag {change_class}">{change_arrow}{change_val}% vs prior</span>
                    </div>
                </div>
                """

            elif widget_type in ["line", "bar"]:
                metric_type = query_config.get("metric_type", "page_views")
                interval = query_config.get("interval", "hour")
                
                points = await self.analytics_service.get_timeseries(
                    organization_id=organization_id,
                    start=start_time,
                    end=end_time,
                    interval=interval,
                    metric=metric_type,
                    use_cache=False
                )
                
                points_rows = ""
                # Keep top 8 points to prevent table bloat in email/printable view
                for p in points[-8:]:
                    timestamp_str = p.get("timestamp", "")
                    if timestamp_str:
                        try:
                            dt = datetime.datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                            timestamp_str = dt.strftime("%b %d, %H:%M" if interval == "hour" else "%b %d, %Y")
                        except Exception:
                            pass
                    val = p.get("value", 0)
                    points_rows += f"""
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); color: var(--text-muted);">{timestamp_str}</td>
                        <td style="padding: 10px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); text-align: right; font-weight: 600;">{val}</td>
                    </tr>
                    """
                
                if not points_rows:
                    points_rows = "<tr><td colspan='2' style='padding: 20px; text-align: center; color: var(--text-muted);'>No timeseries trend data available.</td></tr>"

                # CSS-based mock bar charts represent premium aesthetics
                bar_elements = ""
                if points:
                    max_val = max([p.get("value", 0) for p in points]) or 1
                    for p in points[-12:]:  # Draw up to 12 bars
                        val = p.get("value", 0)
                        pct = int((val / max_val) * 100)
                        bar_elements += f"""
                        <div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100px; margin: 0 4px;">
                            <div style="width: 100%; height: {pct}%; background: linear-gradient(180deg, var(--primary) 0%, var(--primary-dark) 100%); border-radius: 4px; min-height: 4px;"></div>
                            <span style="font-size: 9px; color: var(--text-muted); margin-top: 6px; white-space: nowrap; transform: rotate(-45deg); height: 20px;"></span>
                        </div>
                        """

                return f"""
                <div class="glass-card" style="margin-bottom: 24px;">
                    <div class="card-header">{widget.name or "Time-Series Analytics"}</div>
                    
                    <div style="display: flex; height: 140px; margin-top: 24px; margin-bottom: 24px; align-items: flex-end; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 8px;">
                        {bar_elements}
                    </div>

                    <table style="width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px;">
                        <thead>
                            <tr style="text-align: left; border-bottom: 2px solid rgba(255, 255, 255, 0.1);">
                                <th style="padding: 10px; color: var(--text-heading);">Time Period</th>
                                <th style="padding: 10px; text-align: right; color: var(--text-heading);">{metric_type.replace('_', ' ').title()}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {points_rows}
                        </tbody>
                    </table>
                </div>
                """

            elif widget_type == "pie":
                property_key = query_config.get("property_key", "browser")
                limit = query_config.get("limit", 5)
                
                breakdown = await self.analytics_service.get_breakdown(
                    organization_id=organization_id,
                    start=start_time,
                    end=end_time,
                    property_key=property_key,
                    limit=limit,
                    use_cache=False
                )
                
                total_events = sum([b.get("count", 0) for b in breakdown]) or 1
                breakdown_rows = ""
                
                for b in breakdown:
                    name = b.get("value", "Unknown")
                    count = b.get("count", 0)
                    percentage = round((count / total_events) * 100.0, 1)
                    
                    breakdown_rows += f"""
                    <div style="margin-bottom: 16px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 14px;">
                            <span style="font-weight: 500; color: var(--text-heading);">{name}</span>
                            <span style="color: var(--text-muted); font-weight: 600;">{count} ({percentage}%)</span>
                        </div>
                        <div style="width: 100%; height: 8px; background: rgba(255, 255, 255, 0.08); border-radius: 4px; overflow: hidden;">
                            <div style="width: {percentage}%; height: 100%; background: linear-gradient(90deg, var(--secondary) 0%, var(--primary) 100%); border-radius: 4px;"></div>
                        </div>
                    </div>
                    """
                
                if not breakdown_rows:
                    breakdown_rows = "<p style='text-align: center; color: var(--text-muted); padding: 20px; margin: 0;'>No segmentation breakdown logs recorded.</p>"
                
                return f"""
                <div class="glass-card" style="margin-bottom: 24px;">
                    <div class="card-header">{widget.name or f"Segment by {property_key.title()}"}</div>
                    <div style="margin-top: 20px;">
                        {breakdown_rows}
                    </div>
                </div>
                """

            else:
                return f"""
                <div class="glass-card" style="margin-bottom: 24px; padding: 20px; text-align: center;">
                    <p style="color: var(--text-muted); margin: 0;">Unsupported Widget View Type: {widget_type}</p>
                </div>
                """
        except Exception as e:
            self.logger.exception("Failed compiling widget snapshot card to HTML, rendering error fallback card", widget_id=widget.id)
            return f"""
            <div class="glass-card" style="margin-bottom: 24px; border: 1px solid rgba(239, 68, 68, 0.2); background: rgba(239, 68, 68, 0.05);">
                <div class="card-header" style="color: #ef4444;">Error Loading: {widget.name or "Widget"}</div>
                <p style="font-size: 13px; color: rgba(255,255,255,0.6); margin-top: 12px; margin-bottom: 0;">An error occurred while compiling this metric snapshot card: {e}</p>
            </div>
            """

    def _render_premium_html_template(
        self, org_name: str, dashboard_name: str, time_label: str, frequency: str, overview_data: Dict[str, Any], widgets_html: str, generated_at: str
    ) -> str:
        """HTML standard styling variables representing a sleek glassmorphic dark interface suitable for printing."""
        
        # Pull key metrics
        page_views = overview_data.get("page_views", 0)
        unique_visitors = overview_data.get("unique_visitors", 0)
        bounce_rate = overview_data.get("bounce_rate", 0.0)
        avg_session_duration = overview_data.get("avg_session_duration", 0.0)
        
        # Pull change percentages
        pv_chg = overview_data.get("page_views_change", 0.0)
        uv_chg = overview_data.get("unique_visitors_change", 0.0)
        br_chg = overview_data.get("bounce_rate_change", 0.0)
        asd_chg = overview_data.get("avg_session_duration_change", 0.0)

        # Style tags
        pv_chg_cls = "trend-up" if pv_chg >= 0 else "trend-down"
        uv_chg_cls = "trend-up" if uv_chg >= 0 else "trend-down"
        br_chg_cls = "trend-down" if br_chg <= 0 else "trend-up"  # Bounce rate drop is positive
        asd_chg_cls = "trend-up" if asd_chg >= 0 else "trend-down"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{dashboard_name} - Performance Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0b0f19;
            --surface: rgba(17, 24, 39, 0.6);
            --card-border: rgba(255, 255, 255, 0.08);
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --secondary: #10b981;
            --text-heading: #f3f4f6;
            --text-body: #9ca3af;
            --text-muted: #6b7280;
            --trend-up-color: #34d399;
            --trend-down-color: #f87171;
        }}

        body {{
            background-color: var(--bg);
            color: var(--text-body);
            font-family: 'Outfit', sans-serif;
            margin: 0;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
        }}

        .report-container {{
            max-width: 800px;
            width: 100%;
        }}

        /* Header Style */
        .report-header {{
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(12px);
        }}

        .report-header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
        }}

        .org-badge {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--primary);
            font-weight: 700;
            margin-bottom: 8px;
            display: inline-block;
        }}

        .report-title {{
            font-size: 32px;
            font-weight: 700;
            color: var(--text-heading);
            margin: 0 0 10px 0;
            letter-spacing: -0.5px;
        }}

        .meta-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin-top: 20px;
            font-size: 13px;
            color: var(--text-muted);
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            padding-top: 15px;
        }}

        .meta-item strong {{
            color: var(--text-heading);
        }}

        /* Glass Cards */
        .glass-card {{
            background: var(--surface);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        }}

        .card-header {{
            font-size: 16px;
            font-weight: 600;
            color: var(--text-heading);
            letter-spacing: -0.2px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            padding-bottom: 12px;
            margin-bottom: 16px;
        }}

        /* Quick Overview KPI Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}

        @media (max-width: 600px) {{
            .kpi-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .kpi-card {{
            display: flex;
            flex-direction: column;
        }}

        .kpi-value {{
            font-size: 28px;
            font-weight: 700;
            color: var(--text-heading);
            letter-spacing: -0.5px;
        }}

        .trend-tag {{
            font-size: 12px;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 6px;
        }}

        .trend-up {{
            background: rgba(52, 211, 153, 0.1);
            color: var(--trend-up-color);
        }}

        .trend-down {{
            background: rgba(248, 113, 113, 0.1);
            color: var(--trend-down-color);
        }}

        .section-title {{
            font-size: 20px;
            font-weight: 600;
            color: var(--text-heading);
            margin: 40px 0 20px 0;
            display: flex;
            align-items: center;
            letter-spacing: -0.3px;
        }}

        .section-title::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: var(--card-border);
            margin-left: 15px;
        }}

        /* Footer styling */
        .report-footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 50px;
            border-top: 1px solid var(--card-border);
            padding-top: 24px;
        }}

        @media print {{
            body {{
                background: white;
                color: #111827;
                padding: 0;
            }}
            :root {{
                --bg: #ffffff;
                --surface: #ffffff;
                --card-border: #e5e7eb;
                --text-heading: #111827;
                --text-body: #374151;
                --text-muted: #6b7280;
                --trend-up-color: #047857;
                --trend-down-color: #b91c1c;
            }}
            .glass-card {{
                box-shadow: none;
                page-break-inside: avoid;
            }}
            .report-header {{
                border: 1px solid #d1d5db;
                background: #f3f4f6;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        
        <header class="report-header">
            <span class="org-badge">{org_name}</span>
            <h1 class="report-title">{dashboard_name}</h1>
            <p style="margin: 0; font-size: 15px; color: var(--text-body);">Recurring automated performance audit snapshot digest.</p>
            
            <div class="meta-grid">
                <div class="meta-item">Frequency: <strong>{frequency.title()}</strong></div>
                <div class="meta-item">Time Frame: <strong>{time_label}</strong></div>
                <div class="meta-item">Generated At: <strong>{generated_at}</strong></div>
            </div>
        </header>

        <h2 class="section-title">Overview Analytics</h2>
        <div class="kpi-grid">
            <div class="glass-card kpi-card">
                <span style="font-size: 13px; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Page Views</span>
                <div style="display: flex; align-items: baseline; justify-content: space-between; margin-top: 8px;">
                    <span class="kpi-value">{page_views:,}</span>
                    <span class="trend-tag {pv_chg_cls}">{"+" if pv_chg >= 0 else ""}{pv_chg}%</span>
                </div>
            </div>
            
            <div class="glass-card kpi-card">
                <span style="font-size: 13px; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Unique Visitors</span>
                <div style="display: flex; align-items: baseline; justify-content: space-between; margin-top: 8px;">
                    <span class="kpi-value">{unique_visitors:,}</span>
                    <span class="trend-tag {uv_chg_cls}">{"+" if uv_chg >= 0 else ""}{uv_chg}%</span>
                </div>
            </div>

            <div class="glass-card kpi-card">
                <span style="font-size: 13px; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Bounce Rate</span>
                <div style="display: flex; align-items: baseline; justify-content: space-between; margin-top: 8px;">
                    <span class="kpi-value">{bounce_rate}%</span>
                    <span class="trend-tag {br_chg_cls}">{"+" if br_chg >= 0 else ""}{br_chg}%</span>
                </div>
            </div>

            <div class="glass-card kpi-card">
                <span style="font-size: 13px; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Avg. Session Duration</span>
                <div style="display: flex; align-items: baseline; justify-content: space-between; margin-top: 8px;">
                    <span class="kpi-value">{avg_session_duration}s</span>
                    <span class="trend-tag {asd_chg_cls}">{"+" if asd_chg >= 0 else ""}{asd_chg}%</span>
                </div>
            </div>
        </div>

        <h2 class="section-title">Dashboard Widgets Snapshots</h2>
        
        {widgets_html}

        <footer class="report-footer">
            <p>This report was generated automatically. To modify report schedule parameters or email lists, visit the SaaS Reports Control Room page.</p>
            <p style="color: var(--text-muted); margin-top: 8px;">&copy; 2026 {org_name} Analytics Reporting Gateway.</p>
        </footer>

    </div>
</body>
</html>
"""

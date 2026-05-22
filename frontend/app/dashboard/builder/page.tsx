"use client"

import { useEffect, useState } from "react"
import { useGlobalStore } from "@/store/global-store"
import { api } from "@/lib/api-client"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell
} from "recharts"
import {
  LayoutDashboard,
  Plus,
  Trash2,
  Share2,
  Settings,
  ChevronDown,
  Layers,
  Globe,
  Activity,
  Clock,
  Laptop,
  Loader2,
  Calendar,
  RefreshCw,
  Copy,
  Check,
  Eye,
  Lock,
  ArrowUpRight,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  FolderPlus
} from "lucide-react"

// Widget Types and structures
type WidgetType = "line" | "bar" | "kpi" | "table"

interface Widget {
  id: string
  dashboard_id: string
  name: string
  type: WidgetType
  layout: {
    w: number // 4 = 1/3 width, 6 = 1/2 width, 12 = full width
  }
  query_config: {
    metric_type?: string // page_views, unique_visitors, bounce_rate, avg_session_duration
    interval?: string // minute, hour, day, week, month
    breakdown_property?: string // browser, os, country, source
    limit?: number
  }
}

interface Dashboard {
  id: string
  name: string
  description: string | null
  is_public: boolean
  share_token: string | null
  widgets: Widget[]
}

export default function DashboardBuilderPage() {
  const { organization, organizations } = useGlobalStore()

  // Active user role
  const activeRole = organizations.find((o) => o.organization.id === organization?.id)?.role || "viewer"
  const isReadOnly = activeRole === "viewer"

  // Component States
  const [dashboards, setDashboards] = useState<Dashboard[]>([])
  const [activeDashboard, setActiveDashboard] = useState<Dashboard | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [lookbackHours, setLookbackHours] = useState<number>(24)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  // Modals Toggles
  const [createDashboardModal, setCreateDashboardModal] = useState(false)
  const [addWidgetModal, setAddWidgetModal] = useState(false)
  const [copiedLink, setCopiedLink] = useState(false)

  // Form Fields
  const [newDashName, setNewDashName] = useState("")
  const [newDashDesc, setNewDashDesc] = useState("")
  
  const [newWidgetName, setNewWidgetName] = useState("")
  const [newWidgetType, setNewWidgetType] = useState<WidgetType>("kpi")
  const [newWidgetWidth, setNewWidgetWidth] = useState<number>(6)
  const [widgetMetric, setWidgetMetric] = useState("page_views")
  const [widgetInterval, setWidgetInterval] = useState("hour")
  const [widgetBreakdown, setWidgetBreakdown] = useState("browser")
  
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Fetch all dashboards for organization
  const fetchDashboards = async (selectId?: string) => {
    if (!organization) return
    setIsLoading(true)
    try {
      const list = await api.get<Dashboard[]>(
        `/api/v1/organizations/${organization.id}/dashboards`
      )
      setDashboards(list)

      if (list.length > 0) {
        // If a specific dashboard ID is requested to be selected, find it
        const nextActive = selectId 
          ? list.find(d => d.id === selectId) || list[0] 
          : list[0]
        
        // Fetch full dashboard details including widgets
        const fullDetail = await api.get<Dashboard>(
          `/api/v1/organizations/${organization.id}/dashboards/${nextActive.id}`
        )
        setActiveDashboard(fullDetail)
      } else {
        setActiveDashboard(null)
      }
    } catch (err) {
      console.error("Failed to load dashboards:", err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchDashboards()
  }, [organization, refreshTrigger])

  // Select another dashboard from list
  const handleSelectDashboard = async (id: string) => {
    if (!organization) return
    setIsLoading(true)
    try {
      const fullDetail = await api.get<Dashboard>(
        `/api/v1/organizations/${organization.id}/dashboards/${id}`
      )
      setActiveDashboard(fullDetail)
    } catch (err) {
      console.error("Failed to fetch full dashboard details:", err)
    } finally {
      setIsLoading(false)
    }
  }

  // Provision template dashboard
  const handleProvisionTemplate = async () => {
    if (!organization || isReadOnly) return
    setIsLoading(true)
    try {
      const res = await api.post<Dashboard>(
        `/api/v1/organizations/${organization.id}/dashboards/templates/web_analytics`,
        {}
      )
      await fetchDashboards(res.id)
    } catch (err) {
      console.error("Provisioning template failed:", err)
    }
  }

  // Create custom Dashboard
  const handleCreateDashboard = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!organization || isReadOnly || !newDashName.trim()) return
    setIsSubmitting(true)
    try {
      const res = await api.post<Dashboard>(
        `/api/v1/organizations/${organization.id}/dashboards`,
        {
          name: newDashName,
          description: newDashDesc || null,
          is_public: false
        }
      )
      setNewDashName("")
      setNewDashDesc("")
      setCreateDashboardModal(false)
      await fetchDashboards(res.id)
    } catch (err) {
      console.error("Failed to create dashboard:", err)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Add a new custom widget
  const handleAddWidget = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!organization || !activeDashboard || isReadOnly || !newWidgetName.trim()) return
    setIsSubmitting(true)
    
    // Scrape query config depending on type
    const queryConfig: any = {}
    if (newWidgetType === "kpi" || newWidgetType === "line" || newWidgetType === "bar") {
      queryConfig.metric_type = widgetMetric
      queryConfig.interval = widgetInterval
    } else if (newWidgetType === "table") {
      queryConfig.breakdown_property = widgetBreakdown
      queryConfig.limit = 5
    }

    try {
      await api.post(
        `/api/v1/organizations/${organization.id}/dashboards/${activeDashboard.id}/widgets`,
        {
          name: newWidgetName,
          type: newWidgetType,
          layout: { w: Number(newWidgetWidth) },
          query_config: queryConfig
        }
      )
      setNewWidgetName("")
      setAddWidgetModal(false)
      // Reload active dashboard full details
      await handleSelectDashboard(activeDashboard.id)
    } catch (err) {
      console.error("Failed to add widget:", err)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Delete dashboard
  const handleDeleteDashboard = async () => {
    if (!organization || !activeDashboard || isReadOnly) return
    if (!confirm("Are you sure you want to delete this entire dashboard?")) return
    try {
      await api.delete(
        `/api/v1/organizations/${organization.id}/dashboards/${activeDashboard.id}`
      )
      await fetchDashboards()
    } catch (err) {
      console.error("Dashboard deletion failed:", err)
    }
  }

  // Delete widget
  const handleDeleteWidget = async (widgetId: string) => {
    if (!organization || !activeDashboard || isReadOnly) return
    if (!confirm("Are you sure you want to delete this widget?")) return
    try {
      await api.delete(
        `/api/v1/organizations/${organization.id}/dashboards/${activeDashboard.id}/widgets/${widgetId}`
      )
      await handleSelectDashboard(activeDashboard.id)
    } catch (err) {
      console.error("Widget deletion failed:", err)
    }
  }

  // Toggle Sharing
  const handleToggleSharing = async () => {
    if (!organization || !activeDashboard || isReadOnly) return
    try {
      const updated = await api.post<Dashboard>(
        `/api/v1/organizations/${organization.id}/dashboards/${activeDashboard.id}/share`,
        { is_public: !activeDashboard.is_public }
      )
      setActiveDashboard({
        ...activeDashboard,
        is_public: updated.is_public,
        share_token: updated.share_token
      })
    } catch (err) {
      console.error("Failed to toggle sharing status:", err)
    }
  }

  // Copy share link
  const copyShareLink = () => {
    if (!activeDashboard?.share_token) return
    const url = `${window.location.origin}/share/${activeDashboard.share_token}`
    navigator.clipboard.writeText(url)
    setCopiedLink(true)
    setTimeout(() => setCopiedLink(false), 2000)
  }

  if (!organization) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-2">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
        <span className="text-sm text-zinc-400">Loading active organization context...</span>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      
      {/* 1. HEADER BAR */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-900 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse shadow-[0_0_8px_#6366f1]" />
            <span className="text-[10px] uppercase tracking-widest text-indigo-400 font-bold">Dashboard Builder</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight mt-1 text-white">
            Custom <span className="gradient-text">Studio</span>
          </h1>
          <p className="text-zinc-400 text-xs mt-1">
            Build bespoke reporting dashboards, coordinate grid charts, and provision shareable telemetry layouts.
          </p>
        </div>

        {/* Dashboard Actions and selection */}
        <div className="flex flex-wrap items-center gap-3">
          {dashboards.length > 0 && (
            <div className="flex bg-zinc-950 p-1 rounded-xl border border-zinc-900">
              {/* Select lookback window for widgets queries */}
              {[
                { label: "1H", val: 1 },
                { label: "24H", val: 24 },
                { label: "7D", val: 168 },
                { label: "30D", val: 720 },
              ].map((opt) => (
                <button
                  key={opt.val}
                  onClick={() => setLookbackHours(opt.val)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    lookbackHours === opt.val
                      ? "bg-indigo-650 text-white shadow-[0_2px_8px_rgba(99,102,241,0.3)]"
                      : "text-zinc-500 hover:text-zinc-350"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}

          {dashboards.length > 0 && (
            <select
              value={activeDashboard?.id || ""}
              onChange={(e) => handleSelectDashboard(e.target.value)}
              className="bg-zinc-950 border border-zinc-800 rounded-xl text-xs font-bold text-zinc-350 px-3.5 py-2.5 outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {dashboards.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          )}

          {!isReadOnly && (
            <button
              onClick={() => setCreateDashboardModal(true)}
              className="flex items-center gap-1.5 px-3.5 py-2.5 bg-indigo-650 hover:bg-indigo-600 transition rounded-xl text-xs font-bold text-white shadow-[0_4px_12px_rgba(99,102,241,0.25)]"
            >
              <Plus className="h-4 w-4" />
              New Dashboard
            </button>
          )}
        </div>
      </header>

      {/* RBAC Viewer mode lock badge */}
      {isReadOnly && (
        <div className="flex items-center gap-2 px-4 py-3 bg-zinc-950/80 border border-zinc-900 rounded-xl text-zinc-400 text-xs">
          <Lock className="h-4 w-4 text-purple-400" />
          <span>You are logged in with standard <strong>Viewer role</strong>. Custom layout builds, additions, or edits are read-only.</span>
        </div>
      )}

      {/* 2. LOADING STATE */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-32 gap-3">
          <Loader2 className="h-9 w-9 animate-spin text-indigo-500" />
          <span className="text-zinc-400 text-xs font-medium">Synchronizing studio layout parameters...</span>
        </div>
      ) : dashboards.length === 0 ? (
        /* Empty state: Provision templates */
        <div className="glassmorphism glow-border rounded-2xl p-10 py-16 text-center max-w-2xl mx-auto space-y-6">
          <div className="mx-auto h-14 w-14 rounded-2xl bg-indigo-550/15 border border-indigo-500/10 flex items-center justify-center text-indigo-400 shadow-[0_4px_15px_rgba(99,102,241,0.1)]">
            <LayoutDashboard className="h-7 w-7" />
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-bold text-white">No custom reporting dashboards exist.</h2>
            <p className="text-zinc-400 text-xs max-w-md mx-auto leading-relaxed">
              Create a custom dashboard studio canvas from scratch or instantly provision a default preset Web Analytics template tracking standard page views, unique visitors and bounce rate.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-2">
            {!isReadOnly ? (
              <>
                <button
                  onClick={handleProvisionTemplate}
                  className="flex items-center gap-2 px-5 py-3 bg-indigo-650 hover:bg-indigo-600 transition rounded-xl text-xs font-bold text-white shadow-[0_4px_12px_rgba(99,102,241,0.25)]"
                >
                  <FolderPlus className="h-4.5 w-4.5" />
                  Provision Web Analytics Template
                </button>
                <button
                  onClick={() => setCreateDashboardModal(true)}
                  className="px-5 py-3 bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 hover:text-white transition rounded-xl text-xs font-bold text-zinc-450"
                >
                  Create Custom Blank Studio
                </button>
              </>
            ) : (
              <span className="text-zinc-500 text-xs font-medium">Ask your administrator to provision or create a dashboard.</span>
            )}
          </div>
        </div>
      ) : activeDashboard ? (
        /* Active Dashboard studio canvas */
        <div className="space-y-6">
          
          {/* Metadata & sharing configuration banner */}
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-5 bg-zinc-950 border border-zinc-900 rounded-2xl">
            <div className="space-y-1 max-w-xl">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                {activeDashboard.name}
                <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                  activeDashboard.is_public ? "bg-emerald-500/10 text-emerald-450 border border-emerald-500/10" : "bg-zinc-850 text-zinc-500"
                }`}>
                  {activeDashboard.is_public ? "Publicly Shared" : "Private Workspace"}
                </span>
              </h2>
              <p className="text-xs text-zinc-450 leading-relaxed">
                {activeDashboard.description || "Bespoke studio analytics reporting canvas."}
              </p>
            </div>

            {/* Sharing toggle & deletion settings */}
            <div className="flex flex-wrap items-center gap-3">
              {!isReadOnly && (
                <>
                  <button
                    onClick={handleToggleSharing}
                    className={`flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl text-xs font-bold transition border ${
                      activeDashboard.is_public
                        ? "bg-zinc-900 border-zinc-800 hover:bg-zinc-850 text-zinc-300"
                        : "bg-indigo-650/10 border-indigo-500/10 text-indigo-400 hover:bg-indigo-650/20"
                    }`}
                  >
                    <Share2 className="h-4 w-4" />
                    {activeDashboard.is_public ? "Make Private" : "Enable Public Sharing"}
                  </button>

                  <button
                    onClick={handleDeleteDashboard}
                    className="p-2.5 bg-zinc-900 border border-zinc-800 hover:bg-red-950/20 hover:border-red-900/30 hover:text-red-400 rounded-xl text-zinc-500 transition"
                    title="Delete Dashboard Canvas"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Share links display */}
          {activeDashboard.is_public && activeDashboard.share_token && (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 bg-emerald-500/5 border border-emerald-500/10 rounded-2xl">
              <div className="space-y-1">
                <span className="text-[10px] uppercase font-bold text-emerald-450 block">Cryptographic Stakeholder Link</span>
                <span className="text-xs text-zinc-400 truncate max-w-lg block font-mono">
                  {`${window.location.origin}/share/${activeDashboard.share_token}`}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={copyShareLink}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 hover:bg-zinc-850 hover:text-white border border-zinc-800 transition rounded-lg text-xs font-bold text-zinc-400"
                >
                  {copiedLink ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                  {copiedLink ? "Copied" : "Copy"}
                </button>
                <a
                  href={`/share/${activeDashboard.share_token}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 hover:bg-zinc-850 hover:text-white border border-zinc-800 transition rounded-lg text-xs font-bold text-zinc-400"
                >
                  <Eye className="h-3.5 w-3.5" />
                  Preview
                </a>
              </div>
            </div>
          )}

          {/* Studio empty widgets list helper */}
          {activeDashboard.widgets.length === 0 && (
            <div className="text-center py-20 bg-zinc-950/20 border border-dashed border-zinc-900 rounded-3xl space-y-4">
              <span className="text-zinc-500 text-xs block max-w-sm mx-auto leading-relaxed">
                This dashboard does not contain any analytics chart widgets. Click add widget to configure your custom timeseries, KPI aggregators, OS segmentations or breakdowns.
              </span>
              {!isReadOnly && (
                <button
                  onClick={() => setAddWidgetModal(true)}
                  className="flex items-center gap-1.5 mx-auto px-4 py-2 bg-indigo-650/10 hover:bg-indigo-650/20 border border-indigo-500/10 transition rounded-xl text-xs font-bold text-indigo-400"
                >
                  <Plus className="h-4 w-4" />
                  Add First Widget
                </button>
              )}
            </div>
          )}

          {/* 3. WIDGETS DISPLAY GRID MAP */}
          <div className="grid grid-cols-12 gap-6 items-start">
            {activeDashboard.widgets.map((widget) => (
              <div
                key={widget.id}
                className={`relative group ${
                  widget.layout.w === 4
                    ? "col-span-12 lg:col-span-4"
                    : widget.layout.w === 6
                    ? "col-span-12 lg:col-span-6"
                    : "col-span-12"
                }`}
              >
                {/* Delete widget hover overlay */}
                {!isReadOnly && (
                  <button
                    onClick={() => handleDeleteWidget(widget.id)}
                    className="absolute top-4 right-4 z-20 p-2 bg-zinc-900/90 border border-zinc-800 rounded-lg text-zinc-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition duration-200"
                    title="Delete Widget"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}

                <WidgetContainer widget={widget} orgId={organization.id} lookback={lookbackHours} />
              </div>
            ))}
          </div>

          {/* Floating actions add buttons */}
          {!isReadOnly && activeDashboard.widgets.length > 0 && (
            <div className="flex items-center justify-center pt-6">
              <button
                onClick={() => setAddWidgetModal(true)}
                className="flex items-center gap-2 px-6 py-3 bg-zinc-955 border border-zinc-850 hover:border-zinc-700 hover:text-white rounded-xl text-xs font-bold text-zinc-400 shadow-xl transition"
              >
                <Plus className="h-4.5 w-4.5 text-indigo-500 animate-bounce" />
                Append Widget to Canvas
              </button>
            </div>
          )}

        </div>
      ) : null}

      {/* ==========================================
          4. MODALS INTERFACES
          ========================================== */}

      {/* Modal A: Create Dashboard */}
      {createDashboardModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
          <div className="glassmorphism glow-border w-full max-w-lg rounded-2xl overflow-hidden shadow-2xl relative">
            <header className="p-6 border-b border-zinc-900 flex justify-between items-center">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <LayoutDashboard className="h-5 w-5 text-indigo-400" />
                Create Dashboard Studio
              </h3>
            </header>

            <form onSubmit={handleCreateDashboard} className="p-6 space-y-5">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Dashboard Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Ingestion Errors / Performance Overview"
                  value={newDashName}
                  onChange={(e) => setNewDashName(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-850 focus:border-indigo-500 rounded-xl px-4 py-3 text-xs outline-none transition text-white placeholder-zinc-600"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Description (Optional)</label>
                <textarea
                  placeholder="Write a brief overview describing metrics target details..."
                  rows={3}
                  value={newDashDesc}
                  onChange={(e) => setNewDashDesc(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-850 focus:border-indigo-500 rounded-xl px-4 py-3 text-xs outline-none transition text-white placeholder-zinc-600 resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setCreateDashboardModal(false)}
                  className="px-4.5 py-2.5 bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 rounded-xl text-xs font-bold text-zinc-450 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4.5 py-2.5 bg-indigo-650 hover:bg-indigo-600 transition rounded-xl text-xs font-bold text-white disabled:opacity-50"
                >
                  {isSubmitting ? "Creating..." : "Create Canvas"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal B: Add Widget */}
      {addWidgetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
          <div className="glassmorphism glow-border w-full max-w-xl rounded-2xl overflow-hidden shadow-2xl relative">
            <header className="p-6 border-b border-zinc-900 flex justify-between items-center">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Settings className="h-5 w-5 text-indigo-400" />
                Configure Widget saved query
              </h3>
            </header>

            <form onSubmit={handleAddWidget} className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Widget Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Chrome User Metrics / Bounce Trend"
                  value={newWidgetName}
                  onChange={(e) => setNewWidgetName(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-850 focus:border-indigo-500 rounded-xl px-4 py-3 text-xs outline-none transition text-white placeholder-zinc-600"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Widget visual Type</label>
                  <select
                    value={newWidgetType}
                    onChange={(e) => setNewWidgetType(e.target.value as WidgetType)}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-xl text-xs font-bold text-zinc-350 px-3.5 py-3 outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                    <option value="kpi">Aggregate Metric Card (KPI)</option>
                    <option value="line">Area Trend Chart (Line)</option>
                    <option value="bar">Bar Metric Chart (Bar)</option>
                    <option value="table">Property Segment list (Table)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Canvas Column Width</label>
                  <select
                    value={newWidgetWidth}
                    onChange={(e) => setNewWidgetWidth(Number(e.target.value))}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-xl text-xs font-bold text-zinc-350 px-3.5 py-3 outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                    <option value={4}>Third Width (1/3)</option>
                    <option value={6}>Half Width (1/2)</option>
                    <option value={12}>Full Width (1/1)</option>
                  </select>
                </div>
              </div>

              {/* Conditional configurations based on type selection */}
              {newWidgetType !== "table" ? (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Telemetry Metric</label>
                    <select
                      value={widgetMetric}
                      onChange={(e) => setWidgetMetric(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-850 rounded-xl text-xs font-bold text-zinc-350 px-3.5 py-3 outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option value="page_views">Page Views (count)</option>
                      <option value="unique_visitors">Unique Visitors (DAU)</option>
                      <option value="bounce_rate">Bounce Rate (%)</option>
                      <option value="avg_session_duration">Session Duration (seconds)</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Time Bucket Interval</label>
                    <select
                      value={widgetInterval}
                      onChange={(e) => setWidgetInterval(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-850 rounded-xl text-xs font-bold text-zinc-350 px-3.5 py-3 outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option value="minute">Minute</option>
                      <option value="hour">Hour</option>
                      <option value="day">Day</option>
                      <option value="week">Week</option>
                    </select>
                  </div>
                </div>
              ) : (
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Segmentation property</label>
                  <select
                    value={widgetBreakdown}
                    onChange={(e) => setWidgetBreakdown(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-xl text-xs font-bold text-zinc-350 px-3.5 py-3 outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                    <option value="browser">Browsers</option>
                    <option value="os">OS Layers</option>
                    <option value="country">Countries</option>
                    <option value="source">Ingestion Sources</option>
                  </select>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setAddWidgetModal(false)}
                  className="px-4.5 py-2.5 bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 rounded-xl text-xs font-bold text-zinc-455 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4.5 py-2.5 bg-indigo-650 hover:bg-indigo-600 transition rounded-xl text-xs font-bold text-white disabled:opacity-50"
                >
                  {isSubmitting ? "Adding..." : "Add to Dashboard"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  )
}

// ------------------------------------------------------------------------------
// SUB-COMPONENT: WIDGET CONTAINER (Handles independent widget fetching)
// ------------------------------------------------------------------------------
interface WidgetContainerProps {
  widget: Widget
  orgId: string
  lookback: number
}

function WidgetContainer({ widget, orgId, lookback }: WidgetContainerProps) {
  const [data, setData] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(false)

  const fetchWidgetData = async () => {
    setIsLoading(true)
    setError(false)

    // Calculate dates
    const end = new Date()
    const start = new Date(end.getTime() - lookback * 60 * 60 * 1000)
    const startTimeStr = start.toISOString().replace(/\.\d+Z$/, "Z")
    const endTimeStr = end.toISOString().replace(/\.\d+Z$/, "Z")

    try {
      if (widget.type === "kpi") {
        // Fetch overview
        const res = await api.get<any>(
          `/api/v1/organizations/${orgId}/analytics/overview?start_time=${startTimeStr}&end_time=${endTimeStr}&use_cache=false`
        )
        const metric = widget.query_config.metric_type || "page_views"
        
        let value = 0
        let delta = 0
        
        if (metric === "page_views") {
          value = res.page_views.current
          delta = res.page_views.change_percentage
        } else if (metric === "unique_visitors") {
          value = res.unique_visitors.current
          delta = res.unique_visitors.change_percentage
        } else if (metric === "bounce_rate") {
          value = res.bounce_rate.current
          delta = res.bounce_rate.change_percentage
        } else if (metric === "avg_session_duration") {
          value = res.avg_session_duration.current
          delta = res.avg_session_duration.change_percentage
        }
        
        setData({ value, delta, metric })
      } else if (widget.type === "line" || widget.type === "bar") {
        // Fetch timeseries
        const metric = widget.query_config.metric_type || "page_views"
        const interval = widget.query_config.interval || "hour"
        
        const res = await api.get<any>(
          `/api/v1/organizations/${orgId}/analytics/timeseries?metric=${metric}&interval=${interval}&start_time=${startTimeStr}&end_time=${endTimeStr}`
        )
        
        const formatted = res.points.map((p: any) => {
          const date = new Date(p.bucket)
          const dateStr = lookback <= 24
            ? date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })
            : date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
          return {
            formattedTime: dateStr,
            value: p.value,
          }
        })
        setData(formatted)
      } else if (widget.type === "table") {
        // Fetch breakdowns
        const prop = widget.query_config.breakdown_property || "browser"
        const limit = widget.query_config.limit || 5
        
        const res = await api.get<any>(
          `/api/v1/organizations/${orgId}/analytics/breakdown?property_key=${prop}&limit=${limit}&start_time=${startTimeStr}&end_time=${endTimeStr}`
        )
        setData(res.items)
      }
    } catch (err) {
      console.error(`Failed to load data for widget ${widget.id}:`, err)
      setError(true)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchWidgetData()
  }, [widget, orgId, lookback])

  const renderDelta = (change: number, isLowerBetter = false) => {
    const isZero = change === 0
    const isGood = isLowerBetter ? change < 0 : change > 0
    const Icon = isZero ? null : isGood ? TrendingUp : TrendingDown
    
    return (
      <span
        className={`text-xs font-bold flex items-center gap-0.5 mt-1.5 ${
          isZero ? "text-zinc-500" : isGood ? "text-emerald-450" : "text-red-400"
        }`}
      >
        {Icon && <Icon className="h-3.5 w-3.5" />}
        {change > 0 ? "+" : ""}
        {change.toFixed(1)}%
      </span>
    )
  }

  // Render visual representations based on Widget Visual Type
  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="h-44 w-full flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
        </div>
      )
    }

    if (error) {
      return (
        <div className="h-44 w-full flex flex-col items-center justify-center gap-2 text-zinc-500 px-4">
          <AlertTriangle className="h-6 w-6 text-amber-500" />
          <span className="text-[11px] font-medium text-center">Incompatible widget query configuration or DB failure.</span>
        </div>
      )
    }

    if (!data) return null

    if (widget.type === "kpi") {
      const isSec = data.metric === "avg_session_duration"
      const isBounce = data.metric === "bounce_rate"
      
      let displayValue = data.value.toLocaleString()
      if (isSec) {
        if (data.value < 60) displayValue = `${Math.round(data.value)}s`
        else displayValue = `${Math.floor(data.value / 60)}m ${Math.round(data.value % 60)}s`
      } else if (isBounce) {
        displayValue = `${data.value.toFixed(1)}%`
      }

      const getIcon = () => {
        if (data.metric === "page_views") return Layers
        if (data.metric === "unique_visitors") return Globe
        if (data.metric === "bounce_rate") return Activity
        return Clock
      }
      const Icon = getIcon()

      return (
        <div className="py-4 relative flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-3xl font-extrabold text-white tracking-tight">{displayValue}</span>
            {renderDelta(data.delta, isBounce)}
          </div>
          <div className="p-3.5 bg-indigo-550/10 rounded-2xl text-indigo-400 border border-indigo-500/10 shadow-[0_4px_12px_rgba(99,102,241,0.05)]">
            <Icon className="h-6 w-6" />
          </div>
        </div>
      )
    }

    if (widget.type === "line") {
      return (
        <div className="h-44 w-full mt-4 text-xs font-mono">
          {data.length === 0 ? (
            <div className="h-full flex items-center justify-center text-zinc-550">No events found.</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data}>
                <defs>
                  <linearGradient id={`grad-${widget.id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f1f2e" opacity={0.3} />
                <XAxis dataKey="formattedTime" stroke="#52525b" />
                <YAxis stroke="#52525b" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "rgba(10,10,12,0.9)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    borderRadius: "12px",
                    color: "#fff"
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#6366f1"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill={`url(#grad-${widget.id})`}
                  name="Metrics Volumetrics"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      )
    }

    if (widget.type === "bar") {
      return (
        <div className="h-44 w-full mt-4 text-xs font-mono">
          {data.length === 0 ? (
            <div className="h-full flex items-center justify-center text-zinc-550">No events found.</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f1f2e" opacity={0.2} />
                <XAxis dataKey="formattedTime" stroke="#52525b" />
                <YAxis stroke="#52525b" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "rgba(10,10,12,0.9)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    borderRadius: "12px",
                    color: "#fff"
                  }}
                />
                <Bar dataKey="value" fill="#818cf8" radius={[4, 4, 0, 0]} name="Value" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      )
    }

    if (widget.type === "table") {
      return (
        <div className="mt-4 space-y-3">
          {data.length === 0 ? (
            <div className="text-center text-zinc-500 text-xs py-14">No segment records available.</div>
          ) : (
            data.slice(0, 4).map((item: any, i: number) => (
              <div key={i} className="space-y-1">
                <div className="flex items-center justify-between text-xs font-medium">
                  <span className="text-zinc-300 truncate font-mono max-w-[70%]">
                    {item.label || "Unknown"}
                  </span>
                  <div className="text-zinc-450 font-mono">
                    <span>{item.count} views</span>
                    <span className="font-bold text-indigo-400 ml-2">({item.percentage.toFixed(1)}%)</span>
                  </div>
                </div>
                <div className="w-full bg-zinc-900/60 rounded-full h-1 overflow-hidden">
                  <div
                    className="bg-indigo-500 h-full rounded-full"
                    style={{ width: `${item.percentage}%` }}
                  />
                </div>
              </div>
            ))
          )}
        </div>
      )
    }

    return null
  }

  return (
    <div className="glassmorphism glow-border rounded-2xl p-6 relative overflow-hidden h-full flex flex-col justify-between">
      <div>
        <span className="text-xs uppercase tracking-wider text-zinc-400 font-bold block mb-1">
          {widget.name}
        </span>
        <span className="text-[10px] text-zinc-500 block font-mono">
          {widget.type.toUpperCase()} • {widget.query_config.metric_type || widget.query_config.breakdown_property || "queries"}
        </span>
      </div>

      <div className="flex-1 mt-3">
        {renderContent()}
      </div>

      <div className="text-[9px] text-zinc-550 font-mono border-t border-zinc-900/40 pt-3.5 mt-3 flex items-center justify-between">
        <span>lookback frame query</span>
        <span className="text-emerald-500 font-extrabold flex items-center gap-1 shrink-0">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          Live
        </span>
      </div>
    </div>
  )
}

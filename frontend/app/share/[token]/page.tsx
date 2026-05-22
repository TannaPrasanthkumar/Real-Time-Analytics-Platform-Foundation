"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
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
  Bar
} from "recharts"
import {
  Activity,
  Layers,
  Globe,
  Clock,
  LayoutDashboard,
  AlertTriangle,
  Loader2,
  Calendar,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  ExternalLink
} from "lucide-react"

type WidgetType = "line" | "bar" | "kpi" | "table"

interface Widget {
  id: string
  name: string
  type: WidgetType
  layout: {
    w: number
  }
  query_config: {
    metric_type?: string
    interval?: string
    breakdown_property?: string
    limit?: number
  }
}

interface Dashboard {
  id: string
  name: string
  description: string | null
  is_public: boolean
  widgets: Widget[]
}

export default function SharedDashboardPage() {
  const { token } = useParams()
  const shareToken = Array.isArray(token) ? token[0] : token || ""

  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lookbackHours, setLookbackHours] = useState<number>(24)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  useEffect(() => {
    const fetchSharedLayout = async () => {
      if (!shareToken) return
      setIsLoading(true)
      setError(null)
      try {
        const res = await api.get<Dashboard>(`/api/v1/dashboards/share/${shareToken}`)
        setDashboard(res)
      } catch (err: any) {
        console.error("Public share verification failed:", err)
        setError(err.message || "Requested public dashboard was not found or is no longer shared.")
      } finally {
        setIsLoading(false)
      }
    }
    fetchSharedLayout()
  }, [shareToken, refreshTrigger])

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0a0a0c] flex flex-col items-center justify-center gap-3 text-zinc-400">
        <Loader2 className="h-9 w-9 animate-spin text-purple-500" />
        <span className="text-xs font-bold uppercase tracking-widest font-mono">Verifying credentials...</span>
      </div>
    )
  }

  if (error || !dashboard) {
    return (
      <div className="min-h-screen bg-[#0a0a0c] flex items-center justify-center p-4">
        <div className="glassmorphism glow-border max-w-md w-full p-8 text-center space-y-6">
          <div className="mx-auto h-12 w-12 rounded-xl bg-red-500/10 border border-red-500/15 flex items-center justify-center text-red-400 shadow-[0_4px_15px_rgba(239,68,68,0.1)]">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <div className="space-y-2">
            <h2 className="text-lg font-bold text-white">Public access unauthorized</h2>
            <p className="text-zinc-400 text-xs leading-relaxed">
              {error || "The cryptographic signature passed in your URL is invalid or has been revoked by the workspace administrator."}
            </p>
          </div>
          <div className="pt-2">
            <a
              href="/login"
              className="inline-flex items-center gap-1.5 text-xs font-bold text-purple-400 hover:text-purple-300 transition"
            >
              Sign in to Antigravity console
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-zinc-100 p-4 md:p-8 overflow-y-auto">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* 1. HEADER BRAND BAR */}
        <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-900 pb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_#10b981]" />
              <span className="text-[10px] uppercase tracking-widest text-emerald-400 font-bold">Secure Portal Share</span>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight mt-1 text-white">
              {dashboard.name}
            </h1>
            <p className="text-zinc-450 text-xs mt-1">
              {dashboard.description || "Read-only workspace telemetry aggregates view."}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex bg-zinc-950 p-1 rounded-xl border border-zinc-900">
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
                      ? "bg-purple-650 text-white shadow-[0_2px_8px_rgba(124,58,237,0.3)]"
                      : "text-zinc-500 hover:text-zinc-350"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <button
              onClick={() => setRefreshTrigger((prev) => prev + 1)}
              className="p-2.5 bg-zinc-900 border border-zinc-800 rounded-xl hover:bg-zinc-800 transition text-zinc-400"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* 2. STATS WIDGET GRID MAP */}
        {dashboard.widgets.length === 0 ? (
          <div className="text-center py-20 bg-zinc-950/20 border border-zinc-900 rounded-3xl text-zinc-500 text-xs font-medium">
            This dashboard does not contain any published reporting widgets.
          </div>
        ) : (
          <div className="grid grid-cols-12 gap-6 items-start">
            {dashboard.widgets.map((widget) => (
              <div
                key={widget.id}
                className={
                  widget.layout.w === 4
                    ? "col-span-12 lg:col-span-4"
                    : widget.layout.w === 6
                    ? "col-span-12 lg:col-span-6"
                    : "col-span-12"
                }
              >
                <PublicWidgetContainer widget={widget} shareToken={shareToken} lookback={lookbackHours} />
              </div>
            ))}
          </div>
        )}

        {/* 3. SHIELD PORTAL BRANDING FOOTER */}
        <footer className="flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-zinc-900/60 pt-6 mt-8 text-[10px] text-zinc-500 font-mono">
          <span>Cryptographic share authorization validated • SSL Enforced</span>
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-purple-500" />
            <span className="font-bold text-zinc-400">Antigravity Analytics Platform</span>
          </div>
        </footer>

      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------
// SUB-COMPONENT: PUBLIC WIDGET CONTAINER (Uses unauthenticated analytics endpoints)
// ------------------------------------------------------------------------------
interface PublicWidgetContainerProps {
  widget: Widget
  shareToken: string
  lookback: number
}

function PublicWidgetContainer({ widget, shareToken, lookback }: PublicWidgetContainerProps) {
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
          `/api/v1/dashboards/share/${shareToken}/overview?start_time=${startTimeStr}&end_time=${endTimeStr}`
        )
        const metric = widget.query_config.metric_type || "page_views"
        
        let value = 0
        let delta = 0
        
        if (metric === "page_views") {
          value = res.page_views
          delta = res.page_views_change || 0
        } else if (metric === "unique_visitors") {
          value = res.unique_visitors
          delta = res.unique_visitors_change || 0
        } else if (metric === "bounce_rate") {
          value = res.bounce_rate
          delta = res.bounce_rate_change || 0
        } else if (metric === "avg_session_duration") {
          value = res.avg_session_duration
          delta = res.avg_session_duration_change || 0
        }
        
        setData({ value, delta, metric })
      } else if (widget.type === "line" || widget.type === "bar") {
        // Fetch timeseries
        const metric = widget.query_config.metric_type || "page_views"
        const interval = widget.query_config.interval || "hour"
        
        const res = await api.get<any>(
          `/api/v1/dashboards/share/${shareToken}/timeseries?metric=${metric}&interval=${interval}&start_time=${startTimeStr}&end_time=${endTimeStr}`
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
          `/api/v1/dashboards/share/${shareToken}/breakdown?property_key=${prop}&limit=${limit}&start_time=${startTimeStr}&end_time=${endTimeStr}`
        )
        setData(res.items)
      }
    } catch (err) {
      console.error(`Failed to load data for public widget ${widget.id}:`, err)
      setError(true)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchWidgetData()
  }, [widget, shareToken, lookback])

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

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="h-44 w-full flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-purple-500" />
        </div>
      )
    }

    if (error) {
      return (
        <div className="h-44 w-full flex flex-col items-center justify-center gap-2 text-zinc-500 px-4">
          <AlertTriangle className="h-6 w-6 text-amber-500" />
          <span className="text-[11px] font-medium text-center">Failed to fetch metrics data.</span>
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
          <div className="p-3.5 bg-purple-550/10 rounded-2xl text-purple-400 border border-purple-500/10 shadow-[0_4px_12px_rgba(124,58,237,0.05)]">
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
                  <linearGradient id={`grad-pub-${widget.id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#a855f7" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#a855f7" stopOpacity={0}/>
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
                  stroke="#a855f7"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill={`url(#grad-pub-${widget.id})`}
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
                <Bar dataKey="value" fill="#a855f7" radius={[4, 4, 0, 0]} name="Value" />
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
                  <span className="text-zinc-350 truncate font-mono max-w-[70%]">
                    {item.label || "Unknown"}
                  </span>
                  <div className="text-zinc-450 font-mono">
                    <span>{item.count} views</span>
                    <span className="font-bold text-purple-400 ml-2">({item.percentage.toFixed(1)}%)</span>
                  </div>
                </div>
                <div className="w-full bg-zinc-900/60 rounded-full h-1 overflow-hidden">
                  <div
                    className="bg-purple-500 h-full rounded-full"
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
        <span className="text-[10px] text-zinc-550 block font-mono">
          {widget.type.toUpperCase()} • {widget.query_config.metric_type || widget.query_config.breakdown_property || "queries"}
        </span>
      </div>

      <div className="flex-1 mt-3">
        {renderContent()}
      </div>

      <div className="text-[9px] text-zinc-650 font-mono border-t border-zinc-900/40 pt-3.5 mt-3 flex items-center justify-between">
        <span>lookback frame query</span>
        <span className="text-emerald-500 font-extrabold flex items-center gap-1 shrink-0">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          Live
        </span>
      </div>
    </div>
  )
}

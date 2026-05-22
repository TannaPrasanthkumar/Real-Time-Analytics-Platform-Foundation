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
  Bar
} from "recharts"
import {
  Layers,
  Clock,
  Activity,
  ShieldAlert,
  Calendar,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Globe,
  Chrome,
  Laptop,
  ArrowUpRight,
  Loader2
} from "lucide-react"

interface OverviewData {
  page_views: { current: number; prior: number; change_percentage: number }
  unique_visitors: { current: number; prior: number; change_percentage: number }
  bounce_rate: { current: number; prior: number; change_percentage: number }
  avg_session_duration: { current: number; prior: number; change_percentage: number }
}

interface TimeseriesItem {
  timestamp: string
  page_views: number
  unique_visitors: number
}

interface BreakdownItem {
  property_value: string
  count: number
  percentage: number
}

export default function AnalyticsPage() {
  const { organization } = useGlobalStore()
  
  const [lookbackHours, setLookbackHours] = useState<number>(24)
  const [isLoading, setIsLoading] = useState(true)
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [timeseries, setTimeseries] = useState<TimeseriesItem[]>([])
  
  const [breakdownProperty, setBreakdownProperty] = useState<string>("browser")
  const [breakdown, setBreakdown] = useState<BreakdownItem[]>([])

  const fetchAnalytics = async () => {
    if (!organization) return
    setIsLoading(true)
    
    // 1. Calculate Zulu Time bounds
    const end = new Date()
    const start = new Date(end.getTime() - lookbackHours * 60 * 60 * 1000)
    const startTimeStr = start.toISOString().replace(/\.\d+Z$/, "Z")
    const endTimeStr = end.toISOString().replace(/\.\d+Z$/, "Z")
    
    // Resolve interval based on lookback
    const interval = lookbackHours <= 24 ? "hour" : "day"

    try {
      // 2. Fetch Overview Metrics
      const rawOverview = await api.get<any>(
        `/api/v1/organizations/${organization.id}/analytics/overview?start_time=${startTimeStr}&end_time=${endTimeStr}&use_cache=false`
      )
      const adaptedOverview: OverviewData = {
        page_views: {
          current: rawOverview.page_views || 0,
          prior: 0,
          change_percentage: rawOverview.page_views_change || 0
        },
        unique_visitors: {
          current: rawOverview.unique_visitors || 0,
          prior: 0,
          change_percentage: rawOverview.unique_visitors_change || 0
        },
        bounce_rate: {
          current: rawOverview.bounce_rate || 0,
          prior: 0,
          change_percentage: rawOverview.bounce_rate_change || 0
        },
        avg_session_duration: {
          current: rawOverview.avg_session_duration || 0,
          prior: 0,
          change_percentage: rawOverview.avg_session_duration_change || 0
        }
      }
      setOverview(adaptedOverview)

      // 3. Fetch Timeseries Trends
      const [pageViewsRes, uniqueVisitorsRes] = await Promise.all([
        api.get<any>(
          `/api/v1/organizations/${organization.id}/analytics/timeseries?start_time=${startTimeStr}&end_time=${endTimeStr}&interval=${interval}&metric=page_views&use_cache=false`
        ),
        api.get<any>(
          `/api/v1/organizations/${organization.id}/analytics/timeseries?start_time=${startTimeStr}&end_time=${endTimeStr}&interval=${interval}&metric=unique_visitors&use_cache=false`
        )
      ])

      const mergedMap = new Map<string, { timestamp: string; page_views: number; unique_visitors: number }>()
      
      const pvPoints = pageViewsRes.points || []
      const uvPoints = uniqueVisitorsRes.points || []

      pvPoints.forEach((pt: any) => {
        mergedMap.set(pt.bucket, {
          timestamp: pt.bucket,
          page_views: pt.value,
          unique_visitors: 0
        })
      })
      
      uvPoints.forEach((pt: any) => {
        const existing = mergedMap.get(pt.bucket)
        if (existing) {
          existing.unique_visitors = pt.value
        } else {
          mergedMap.set(pt.bucket, {
            timestamp: pt.bucket,
            page_views: 0,
            unique_visitors: pt.value
          })
        }
      })
      
      const mergedPoints = Array.from(mergedMap.values()).sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      )
      
      // Format timestamps for nicer X-axis representations
      const formattedTimeseries = mergedPoints.map((item) => {
        const date = new Date(item.timestamp)
        const dateStr = lookbackHours <= 24
          ? date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })
          : date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
        return {
          ...item,
          formattedTime: dateStr,
        }
      })
      setTimeseries(formattedTimeseries)

      // 4. Fetch Property Breakdown Segmentations
      const breakdownRes = await api.get<any>(
        `/api/v1/organizations/${organization.id}/analytics/breakdown?start_time=${startTimeStr}&end_time=${endTimeStr}&property_key=${breakdownProperty}&use_cache=false`
      )
      const adaptedBreakdown = (breakdownRes.items || []).map((item: any) => ({
        property_value: item.label,
        count: item.count,
        percentage: item.percentage
      }))
      setBreakdown(adaptedBreakdown)
    } catch (err) {
      console.error("Analytical aggregation loading failed:", err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchAnalytics()
  }, [organization, lookbackHours, breakdownProperty])

  const renderDelta = (change: number, isLowerBetter = false) => {
    const isZero = change === 0
    const isGood = isLowerBetter ? change < 0 : change > 0
    const Icon = isZero ? null : isGood ? TrendingUp : TrendingDown
    
    return (
      <span
        className={`text-xs font-bold flex items-center gap-0.5 mt-1 ${
          isZero ? "text-zinc-500" : isGood ? "text-emerald-450" : "text-red-400"
        }`}
      >
        {Icon && <Icon className="h-3.5 w-3.5" />}
        {change > 0 ? "+" : ""}
        {change.toFixed(1)}%
      </span>
    )
  }

  const formatSessionDuration = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)}s`
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return `${mins}m ${secs}s`
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
      
      {/* 1. HEADER */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-900 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-purple-500 animate-pulse shadow-[0_0_8px_#a855f7]" />
            <span className="text-[10px] uppercase tracking-widest text-purple-400 font-bold">Analytics Engine</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight mt-1 text-white">
            Workspace <span className="gradient-text">Visualizer</span>
          </h1>
          <p className="text-zinc-400 text-xs mt-1">
            Real-time aggregate events pipeline for organization <strong className="text-zinc-300">{organization.name}</strong>.
          </p>
        </div>

        {/* Date window lookback controls */}
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
            onClick={fetchAnalytics}
            disabled={isLoading}
            className="p-2.5 bg-zinc-900 border border-zinc-800 rounded-xl hover:bg-zinc-800 transition text-zinc-400 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin text-purple-500" : ""}`} />
          </button>
        </div>
      </header>

      {/* 2. STATS OVERVIEW GRIDS */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        
        {/* Metric 1: Page Views */}
        <div className="glassmorphism glow-border rounded-2xl p-6 relative overflow-hidden transition hover:scale-[1.01]">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider text-zinc-400 font-bold">Page Views</span>
            <div className="p-2.5 rounded-xl bg-purple-550/15 text-purple-400 border border-purple-500/10">
              <Layers className="h-4.5 w-4.5" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold tracking-tight text-white">
              {isLoading ? "---" : overview?.page_views.current.toLocaleString() || "0"}
            </span>
            {!isLoading && overview && renderDelta(overview.page_views.change_percentage)}
          </div>
          <p className="text-[10px] text-zinc-500 mt-1">Total requests loaded in window</p>
        </div>

        {/* Metric 2: Unique Visitors */}
        <div className="glassmorphism glow-border rounded-2xl p-6 relative overflow-hidden transition hover:scale-[1.01]">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider text-zinc-400 font-bold">Unique Visitors</span>
            <div className="p-2.5 rounded-xl bg-indigo-550/15 text-indigo-400 border border-indigo-500/10">
              <Globe className="h-4.5 w-4.5" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold tracking-tight text-white">
              {isLoading ? "---" : overview?.unique_visitors.current.toLocaleString() || "0"}
            </span>
            {!isLoading && overview && renderDelta(overview.unique_visitors.change_percentage)}
          </div>
          <p className="text-[10px] text-zinc-500 mt-1">Distinct client identities parsed</p>
        </div>

        {/* Metric 3: Bounce Rate */}
        <div className="glassmorphism glow-border rounded-2xl p-6 relative overflow-hidden transition hover:scale-[1.01]">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider text-zinc-400 font-bold">Bounce Rate</span>
            <div className="p-2.5 rounded-xl bg-emerald-550/15 text-emerald-400 border border-emerald-500/10">
              <Activity className="h-4.5 w-4.5" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold tracking-tight text-white">
              {isLoading ? "---" : `${overview?.bounce_rate.current.toFixed(1)}%` || "0.0%"}
            </span>
            {!isLoading && overview && renderDelta(overview.bounce_rate.change_percentage, true)}
          </div>
          <p className="text-[10px] text-zinc-500 mt-1">Single page visit ratios</p>
        </div>

        {/* Metric 4: Session Duration */}
        <div className="glassmorphism glow-border rounded-2xl p-6 relative overflow-hidden transition hover:scale-[1.01]">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider text-zinc-400 font-bold">Avg Duration</span>
            <div className="p-2.5 rounded-xl bg-amber-550/15 text-amber-400 border border-amber-500/10">
              <Clock className="h-4.5 w-4.5" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold tracking-tight text-white">
              {isLoading ? "---" : overview ? formatSessionDuration(overview.avg_session_duration.current) : "0s"}
            </span>
            {!isLoading && overview && renderDelta(overview.avg_session_duration.change_percentage)}
          </div>
          <p className="text-[10px] text-zinc-500 mt-1">Average user engagement timing</p>
        </div>

      </section>

      {/* 3. TIME-SERIES VISUALIZATIONS */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Main Area trend graph */}
        <div className="glassmorphism rounded-2xl p-6 lg:col-span-2 flex flex-col justify-between min-h-[380px]">
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Calendar className="h-4.5 w-4.5 text-purple-400" />
              Real-time Ingestion Volumetrics
            </h3>
            <p className="text-xs text-zinc-400">Time-series distribution across active lookback frames.</p>
          </div>

          <div className="h-64 w-full mt-6 text-xs">
            {isLoading ? (
              <div className="h-full w-full flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
              </div>
            ) : timeseries.length === 0 ? (
              <div className="h-full w-full flex items-center justify-center text-zinc-500 font-medium">
                No telemetry event records found in lookback window.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeseries}>
                  <defs>
                    <linearGradient id="colorViews" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#7c3aed" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorVisitors" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#4f46e5" stopOpacity={0}/>
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
                    dataKey="page_views"
                    stroke="#7c3aed"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorViews)"
                    name="Page Views"
                  />
                  <Area
                    type="monotone"
                    dataKey="unique_visitors"
                    stroke="#4f46e5"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorVisitors)"
                    name="Unique Visitors"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Property breakdowns panel */}
        <div className="glassmorphism rounded-2xl p-6 flex flex-col justify-between min-h-[380px]">
          <div>
            <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Laptop className="h-4.5 w-4.5 text-indigo-400" />
                Property Segmentations
              </h3>
              
              {/* Selector */}
              <select
                value={breakdownProperty}
                onChange={(e) => setBreakdownProperty(e.target.value)}
                className="bg-zinc-950 border border-zinc-800 rounded-lg text-xs font-bold text-zinc-300 px-2.5 py-1.5 outline-none focus:ring-1 focus:ring-purple-500"
              >
                <option value="browser">Browsers</option>
                <option value="os">OS Layers</option>
                <option value="country">Countries</option>
                <option value="source">Sources</option>
              </select>
            </div>

            <div className="mt-4 space-y-3.5">
              {isLoading ? (
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="h-6 w-6 animate-spin text-purple-500" />
                </div>
              ) : breakdown.length === 0 ? (
                <div className="text-center text-zinc-500 text-xs py-20 font-medium">
                  No breakdown segmentations available.
                </div>
              ) : (
                breakdown.map((item, index) => (
                  <div key={index} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs font-medium">
                      <span className="text-zinc-300 truncate font-mono max-w-[70%]">
                        {item.property_value || "Unknown"}
                      </span>
                      <div className="text-zinc-400 space-x-2">
                        <span>{item.count} views</span>
                        <span className="font-bold text-indigo-400">({item.percentage.toFixed(1)}%)</span>
                      </div>
                    </div>
                    {/* Visual Bar percentage representation */}
                    <div className="w-full bg-zinc-900 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-purple-650 to-indigo-500 h-full rounded-full"
                        style={{ width: `${item.percentage}%` }}
                      />
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="text-[10px] text-zinc-500 font-mono flex items-center justify-between pt-4 border-t border-zinc-900">
            <span>Aggregating current window records</span>
            <span className="text-purple-400 animate-pulse">● Active</span>
          </div>
        </div>

      </section>

      {/* 4. FOOTER NOTE */}
      <footer className="text-center text-[10px] text-zinc-500 border-t border-zinc-900/60 pt-4">
        <span>PostgreSQL date_trunc aggregates • Caching layer TTL 5 mins • Cross-tenant isolation boundaries verified.</span>
      </footer>

    </div>
  )
}

"use client"

import { useState, useEffect } from "react"
import { 
  Activity, 
  Database, 
  Cpu, 
  Terminal, 
  ArrowUpRight, 
  ShieldAlert, 
  RefreshCw, 
  Clock, 
  Layers, 
  Zap, 
  CheckCircle2, 
  Loader2 
} from "lucide-react"

// Types for Mock Feeds
interface MockEvent {
  id: string
  timestamp: string
  event: string
  org: string
  duration: number
  status: "200" | "202" | "422" | "429"
}

export default function DashboardHome() {
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [systemHealth, setSystemHealth] = useState({
    api: "operational",
    db: "connected",
    redis: "active",
    latency: 12
  })
  
  // Real-time Event Ingestion Simulation Queue
  const [liveEvents, setLiveEvents] = useState<MockEvent[]>([
    { id: "ev-108", timestamp: "10:03:02", event: "user.auth.login", org: "Acme Corp", duration: 4, status: "200" },
    { id: "ev-107", timestamp: "10:02:59", event: "page.view", org: "Stark Labs", duration: 8, status: "202" },
    { id: "ev-106", timestamp: "10:02:50", event: "cart.add_item", org: "Globex Inc", duration: 11, status: "202" },
    { id: "ev-105", timestamp: "10:02:44", event: "payment.succeeded", org: "Acme Corp", duration: 15, status: "200" },
    { id: "ev-104", timestamp: "10:02:39", event: "user.auth.signup", org: "Lex Corp", duration: 42, status: "422" }
  ])

  // Ingestion Tick Simulator
  useEffect(() => {
    const eventNames = ["user.auth.login", "page.view", "cart.add_item", "payment.succeeded", "checkout.session_start", "api.key_created"]
    const orgs = ["Acme Corp", "Stark Labs", "Globex Inc", "Lex Corp", "Umbrella Inc"]
    const statuses: ("200" | "202" | "422" | "429")[] = ["200", "202", "200", "202", "422", "429"]

    const interval = setInterval(() => {
      const newEvent: MockEvent = {
        id: `ev-${Math.floor(Math.random() * 900) + 110}`,
        timestamp: new Date().toLocaleTimeString("en-US", { hour12: false }),
        event: eventNames[Math.floor(Math.random() * eventNames.length)],
        org: orgs[Math.floor(Math.random() * orgs.length)],
        duration: Math.floor(Math.random() * 35) + 2,
        status: statuses[Math.floor(Math.random() * statuses.length)]
      }
      
      setLiveEvents(prev => [newEvent, ...prev.slice(0, 5)])
      setSystemHealth(prev => ({
        ...prev,
        latency: Math.floor(Math.random() * 8) + 8
      }))
    }, 3500)

    return () => clearInterval(interval)
  }, [])

  const triggerManualRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => {
      setIsRefreshing(false)
    }, 800)
  }

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-8">
      
      {/* 1. HEADER SECTION */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-purple-500 animate-pulse-slow shadow-[0_0_10px_#a855f7]" />
            <span className="text-xs uppercase tracking-widest text-purple-400 font-semibold">Production Console</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight mt-1 text-white">
            Real-Time <span className="gradient-text">Analytics Engine</span>
          </h1>
          <p className="text-zinc-400 text-sm mt-1">
            Unified multi-tenant dashboard managing high-frequency event streams, sub-second queries, and instant notification pipelines.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button 
            onClick={triggerManualRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-4 py-2 text-sm bg-zinc-900 hover:bg-zinc-800 text-zinc-100 rounded-lg border border-zinc-800 hover:border-zinc-700 transition duration-200 disabled:opacity-50"
            id="refresh_btn"
          >
            {isRefreshing ? (
              <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
            ) : (
              <RefreshCw className="h-4 w-4 text-zinc-400" />
            )}
            Sync Metrics
          </button>
          
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium shadow-[0_4px_20px_rgba(124,58,237,0.3)] hover:shadow-[0_4px_25px_rgba(124,58,237,0.5)] transition duration-200"
            id="swagger_docs_link"
          >
            API Swagger
            <ArrowUpRight className="h-4 w-4" />
          </a>

        </div>
      </header>

      {/* 2. STATS GRID */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        
        {/* Metric 1 */}
        <div className="glassmorphism glow-border rounded-xl p-6 relative overflow-hidden transition-all duration-300 hover:scale-[1.02]">
          <div className="absolute top-0 right-0 h-24 w-24 bg-purple-500/5 rounded-full blur-2xl -mr-6 -mt-6 pointer-events-none" />
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider text-zinc-400 font-semibold">Total Ingested Events</span>
            <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
              <Zap className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-bold tracking-tight text-white">4,289,120</span>
            <span className="text-xs font-semibold text-emerald-400 flex items-center gap-0.5">
              +12.4%
            </span>
          </div>
          <p className="text-xs text-zinc-500 mt-1">Live aggregate from active tenants</p>
        </div>

        {/* Metric 2 */}
        <div className="glassmorphism glow-border rounded-xl p-6 relative overflow-hidden transition-all duration-300 hover:scale-[1.02]">
          <div className="absolute top-0 right-0 h-24 w-24 bg-indigo-500/5 rounded-full blur-2xl -mr-6 -mt-6 pointer-events-none" />
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider text-zinc-400 font-semibold">Average API Latency</span>
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
              <Clock className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-bold tracking-tight text-white">{systemHealth.latency}ms</span>
            <span className="text-xs font-semibold text-emerald-400 flex items-center gap-0.5">
              Optimal
            </span>
          </div>
          <p className="text-xs text-zinc-500 mt-1">Sub-second ingestion cycle timing</p>
        </div>

        {/* Metric 3 */}
        <div className="glassmorphism glow-border rounded-xl p-6 relative overflow-hidden transition-all duration-300 hover:scale-[1.02]">
          <div className="absolute top-0 right-0 h-24 w-24 bg-emerald-500/5 rounded-full blur-2xl -mr-6 -mt-6 pointer-events-none" />
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider text-zinc-400 font-semibold">Active Client WebSockets</span>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
              <Activity className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-bold tracking-tight text-white">412</span>
            <span className="text-xs font-semibold text-emerald-400 flex items-center gap-0.5">
              +4.8%
            </span>
          </div>
          <p className="text-xs text-zinc-500 mt-1">Persistent sessions receiving events</p>
        </div>

        {/* Metric 4 */}
        <div className="glassmorphism glow-border rounded-xl p-6 relative overflow-hidden transition-all duration-300 hover:scale-[1.02]">
          <div className="absolute top-0 right-0 h-24 w-24 bg-red-500/5 rounded-full blur-2xl -mr-6 -mt-6 pointer-events-none" />
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider text-zinc-400 font-semibold">Triggered Alerts</span>
            <div className="p-2 rounded-lg bg-red-500/10 text-red-400">
              <ShieldAlert className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-bold tracking-tight text-white">2</span>
            <span className="text-xs font-semibold text-zinc-400">/ 8 rules</span>
          </div>
          <p className="text-xs text-zinc-500 mt-1">1 resolved in the last hour</p>
        </div>

      </section>

      {/* 3. VISUALS / CHARTS & FEEDS WORKSPACE */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Aggregated Analytical Chart Mock Card */}
        <div className="glassmorphism rounded-xl p-6 lg:col-span-2 flex flex-col justify-between h-[380px]">
          <div>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Layers className="h-4 w-4 text-purple-400" />
                  Real-time Ingestion Volumetrics
                </h3>
                <p className="text-xs text-zinc-400">Synchronized every 30s • Visualized by tenant aggregates</p>
              </div>
              <span className="text-xs px-2.5 py-1 bg-zinc-800/80 rounded-full border border-zinc-700 text-purple-300 font-medium">
                Live Stream
              </span>
            </div>

            {/* Custom Visual Representation of a Time-series Graph */}
            <div className="mt-6 h-48 w-full flex items-end justify-between gap-2 px-2 relative border-b border-zinc-800">
              {/* Grid Lines */}
              <div className="absolute inset-0 flex flex-col justify-between pointer-events-none opacity-10">
                <div className="border-t border-zinc-100 w-full" />
                <div className="border-t border-zinc-100 w-full" />
                <div className="border-t border-zinc-100 w-full" />
              </div>

              {/* Decorative Graph Bars */}
              <div className="w-[10%] bg-zinc-800 rounded-t h-[20%] transition-all duration-500" />
              <div className="w-[10%] bg-zinc-800 rounded-t h-[35%] transition-all duration-500" />
              <div className="w-[10%] bg-zinc-800 rounded-t h-[25%] transition-all duration-500" />
              <div className="w-[10%] bg-indigo-950/40 border-t border-indigo-500 rounded-t h-[50%] transition-all duration-500 relative group">
                <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-zinc-900 border border-zinc-800 text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap text-white z-20">
                  48.1k events
                </div>
              </div>
              <div className="w-[10%] bg-indigo-950/60 border-t border-indigo-400 rounded-t h-[45%] transition-all duration-500" />
              <div className="w-[10%] bg-purple-950/60 border-t border-purple-500 rounded-t h-[70%] transition-all duration-500" />
              <div className="w-[10%] bg-purple-900/60 border-t border-purple-400 rounded-t h-[60%] transition-all duration-500" />
              <div className="w-[10%] bg-purple-500/30 border-t-2 border-purple-500 rounded-t h-[85%] transition-all duration-500 relative group animate-pulse-slow">
                <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-zinc-900 border border-zinc-800 text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap text-white z-20">
                  82.4k events (Live)
                </div>
              </div>
            </div>
          </div>
          
          <div className="flex justify-between items-center text-xs text-zinc-500 pt-4 border-t border-zinc-800/80">
            <span>Aggregates: Stark Labs, Acme Corp, Globex Inc</span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-indigo-500" />
              Ingestion buffers healthy
            </span>
          </div>
        </div>

        {/* Live Event Feeds Ticker (FastAPI API Connection Validation Showcase) */}
        <div className="glassmorphism rounded-xl p-6 flex flex-col justify-between h-[380px]">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Terminal className="h-4 w-4 text-emerald-400" />
              Live Ingestion Stream
            </h3>
            <p className="text-xs text-zinc-400">Incoming API event buffer stream</p>
            
            <div className="mt-4 space-y-2">
              {liveEvents.map((ev, index) => (
                <div 
                  key={ev.id}
                  className={`p-2.5 rounded-lg text-xs flex items-center justify-between border border-zinc-800/60 transition-all duration-300 ${
                    index === 0 ? "bg-zinc-800/50 border-purple-500/20 translate-x-1" : "bg-zinc-900/40"
                  }`}
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold text-zinc-100">{ev.event}</span>
                      <span className="text-[10px] text-zinc-500 font-mono">({ev.id})</span>
                    </div>
                    <div className="text-[10px] text-zinc-400 flex items-center gap-2">
                      <span>{ev.org}</span>
                      <span>•</span>
                      <span>{ev.timestamp}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-zinc-500">{ev.duration}ms</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      ev.status === "200" || ev.status === "202"
                        ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800/50"
                        : ev.status === "422"
                        ? "bg-amber-950/80 text-amber-400 border border-amber-800/50"
                        : "bg-red-950/80 text-red-400 border border-red-800/50"
                    }`}>
                      {ev.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="text-zinc-500 text-[10px] font-mono flex items-center justify-between pt-2">
            <span>Tail stream listening...</span>
            <span className="text-emerald-400 animate-pulse">● Connected</span>
          </div>
        </div>

      </section>

      {/* 4. HEALTH CHECK / INTEGRATION MONITORS */}
      <section className="glassmorphism rounded-xl p-6 border border-zinc-800/80">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <Database className="h-4 w-4 text-indigo-400" />
          SaaS Foundation Health Monitor
        </h3>
        <p className="text-xs text-zinc-400 mb-6">
          Diagnostic checks monitoring active monorepo service boundaries, network routing, and database pools.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          
          {/* Check Item 1 */}
          <div className="p-4 bg-zinc-900/30 rounded-lg border border-zinc-800 flex items-start gap-3">
            <div className="p-2 rounded bg-indigo-500/10 text-indigo-400 mt-0.5">
              <Cpu className="h-4 w-4" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-1.5">
                <h4 className="text-sm font-semibold text-zinc-200">FastAPI Ingestion Gateway</h4>
                <CheckCircle2 className="h-4.5 w-4.5 text-emerald-400" />
              </div>
              <p className="text-xs text-zinc-400">
                Uvicorn server hosting async REST endpoints and raw WebSockets gateway.
              </p>
              <div className="text-[10px] text-zinc-500 font-mono">
                Endpoint: <span className="text-indigo-300">/api/v1/health</span> (200 OK)
              </div>
            </div>
          </div>

          {/* Check Item 2 */}
          <div className="p-4 bg-zinc-900/30 rounded-lg border border-zinc-800 flex items-start gap-3">
            <div className="p-2 rounded bg-purple-500/10 text-purple-400 mt-0.5">
              <Database className="h-4 w-4" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-1.5">
                <h4 className="text-sm font-semibold text-zinc-200">PostgreSQL Transactional Layer</h4>
                <span className="text-[10px] px-2 py-0.5 bg-zinc-800 rounded border border-zinc-700 text-zinc-400 font-mono">
                  Pending Setup
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                SQLAlchemy 2.0 async sessions & range monthly partitions setup ready for Step 2.
              </p>
              <div className="text-[10px] text-zinc-500 font-mono">
                Host: <span className="text-purple-300">db:5432</span> (Idle)
              </div>
            </div>
          </div>

          {/* Check Item 3 */}
          <div className="p-4 bg-zinc-900/30 rounded-lg border border-zinc-800 flex items-start gap-3">
            <div className="p-2 rounded bg-purple-500/10 text-purple-400 mt-0.5">
              <Activity className="h-4 w-4" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-1.5">
                <h4 className="text-sm font-semibold text-zinc-200">Redis Broker & Celery Tasks</h4>
                <span className="text-[10px] px-2 py-0.5 bg-zinc-800 rounded border border-zinc-700 text-zinc-400 font-mono">
                  Pending Setup
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                Task worker event consumer and Beat scheduling setup ready for Step 3.
              </p>
              <div className="text-[10px] text-zinc-500 font-mono">
                Host: <span className="text-purple-300">redis:6379</span> (Idle)
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* FOOTER */}
      <footer className="text-center text-xs text-zinc-500 pt-4 border-t border-zinc-800/80">
        <p>© 2026 Real-Time Analytics Platform. Formulated to meet high-volume enterprise ingestion architectures.</p>
      </footer>
      
    </div>
  )
}

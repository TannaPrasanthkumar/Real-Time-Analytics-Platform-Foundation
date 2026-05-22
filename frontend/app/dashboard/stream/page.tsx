"use client"

import { useEffect, useState, useRef } from "react"
import { useGlobalStore } from "@/store/global-store"
import {
  Terminal,
  Activity,
  Zap,
  ShieldAlert,
  Loader2,
  Lock,
  Play,
  Pause,
  Trash2,
  Sliders,
  X,
  ChevronDown,
  Wifi,
  WifiOff,
  Server,
  Database,
  Copy,
  Check,
  Bell,
  CheckCircle2,
  Clock,
  ArrowDownCircle,
  Search,
  Volume2,
  VolumeX
} from "lucide-react"

interface LogMessage {
  id: string
  timestamp: string
  type: "event" | "alert" | "system"
  label: string
  title: string
  raw: any
}

export default function StreamPage() {
  const { organization, organizations } = useGlobalStore()

  // RBAC Access Control
  const activeRole = organizations.find((o) => o.organization.id === organization?.id)?.role || "viewer"
  const isViewer = activeRole === "viewer"

  // Live Stream States
  const [logs, setLogs] = useState<LogMessage[]>([])
  const [connectionStatus, setConnectionStatus] = useState<"connecting" | "connected" | "disconnected" | "reconnecting">("connecting")
  const [reconnectCount, setReconnectCount] = useState(0)
  const [isPaused, setIsPaused] = useState(false)
  const [soundEnabled, setSoundEnabled] = useState(true)
  
  // Filtering & Search
  const [filterType, setFilterType] = useState<"all" | "event" | "alert" | "system">("all")
  const [searchQuery, setSearchQuery] = useState("")

  // Statistics counters
  const [totalEvents, setTotalEvents] = useState(0)
  const [totalAlerts, setTotalAlerts] = useState(0)

  // Overlay warning banner state (Triggered Alert)
  const [activeBannerAlert, setActiveBannerAlert] = useState<{
    id: string
    name: string
    state: string
    metricType: string
    value: number
    threshold: number
    timestamp: string
  } | null>(null)

  // Selected Log Detail Panel
  const [selectedLog, setSelectedLog] = useState<LogMessage | null>(null)
  const [copiedLogText, setCopiedLogText] = useState(false)

  // References
  const socketRef = useRef<WebSocket | null>(null)
  const terminalEndRef = useRef<HTMLDivElement | null>(null)
  const autoScrollRef = useRef<boolean>(true)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const logsBufferRef = useRef<LogMessage[]>([])

  // Web Audio API Synthesizers for WOW Sound Effects
  const playSirenAlertSound = () => {
    if (!soundEnabled || typeof window === "undefined") return
    try {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      
      // Siren sweep sound effect
      const osc1 = ctx.createOscillator()
      const osc2 = ctx.createOscillator()
      const gain = ctx.createGain()

      osc1.type = "sawtooth"
      osc2.type = "square"

      osc1.frequency.setValueAtTime(220, ctx.currentTime)
      osc1.frequency.linearRampToValueAtTime(440, ctx.currentTime + 0.2)
      osc1.frequency.linearRampToValueAtTime(220, ctx.currentTime + 0.4)
      osc1.frequency.linearRampToValueAtTime(440, ctx.currentTime + 0.6)

      osc2.frequency.setValueAtTime(225, ctx.currentTime)
      osc2.frequency.linearRampToValueAtTime(445, ctx.currentTime + 0.2)
      osc2.frequency.linearRampToValueAtTime(225, ctx.currentTime + 0.4)
      osc2.frequency.linearRampToValueAtTime(445, ctx.currentTime + 0.6)

      gain.gain.setValueAtTime(0.08, ctx.currentTime)
      gain.gain.linearRampToValueAtTime(0.08, ctx.currentTime + 0.5)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.8)

      osc1.connect(gain)
      osc2.connect(gain)
      gain.connect(ctx.destination)

      osc1.start()
      osc2.start()
      osc1.stop(ctx.currentTime + 0.8)
      osc2.stop(ctx.currentTime + 0.8)
    } catch (e) {
      console.warn("Failed to trigger Web Audio API:", e)
    }
  }

  const playSuccessChime = () => {
    if (!soundEnabled || typeof window === "undefined") return
    try {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()

      osc.type = "sine"
      osc.frequency.setValueAtTime(523.25, ctx.currentTime) // C5
      osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.1) // E5
      osc.frequency.setValueAtTime(783.99, ctx.currentTime + 0.2) // G5
      osc.frequency.setValueAtTime(1046.50, ctx.currentTime + 0.3) // C6

      gain.gain.setValueAtTime(0.06, ctx.currentTime)
      gain.gain.linearRampToValueAtTime(0.06, ctx.currentTime + 0.25)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45)

      osc.connect(gain)
      gain.connect(ctx.destination)

      osc.start()
      osc.stop(ctx.currentTime + 0.45)
    } catch (e) {
      console.warn("Failed to trigger success chime:", e)
    }
  }

  const addSystemLog = (message: string) => {
    const systemLog: LogMessage = {
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      type: "system",
      label: "SYS",
      title: message,
      raw: { timestamp: new Date().toISOString(), details: message }
    }
    setLogs((prev) => {
      const next = [...prev, systemLog]
      return next.slice(-200) // Keep standard buffer of 200 logs
    })
  }

  // Connect to live WebSocket events gateway
  const connectWebSocket = () => {
    if (!organization) return

    // Clean up previous socket if existing
    if (socketRef.current) {
      socketRef.current.close()
      socketRef.current = null
    }

    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null
    if (!token) {
      addSystemLog("Authentication JWT token missing. Aborting live connection.")
      setConnectionStatus("disconnected")
      return
    }

    setConnectionStatus(reconnectCount > 0 ? "reconnecting" : "connecting")
    addSystemLog(`Initiating handshake with events gateway for ${organization.name}...`)

    const apiURL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    const wsBaseURL = apiURL.replace(/^http/, "ws")
    const fullURL = `${wsBaseURL}/api/v1/organizations/${organization.id}/ws/events?token=${encodeURIComponent(token)}`

    try {
      const ws = new WebSocket(fullURL)
      socketRef.current = ws

      ws.onopen = () => {
        setConnectionStatus("connected")
        setReconnectCount(0)
        addSystemLog("WebSocket tunnel established successfully. Telemetry subscribing.")
        playSuccessChime()

        // Set active client ping interval to keep connection alive (e.g. bypass proxy drops)
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current)
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send("ping")
          }
        }, 30000)
      }

      ws.onmessage = (event) => {
        // Skip server pong heartbeats
        if (event.data === "pong" || event.data.includes('"type":"pong"')) return

        try {
          const payload = JSON.parse(event.data)
          
          let parsedLog: LogMessage | null = null

          if (payload.type === "event") {
            setTotalEvents((prev) => prev + 1)
            parsedLog = {
              id: payload.data.id || crypto.randomUUID(),
              timestamp: payload.data.timestamp || new Date().toISOString(),
              type: "event",
              label: "EVENT",
              title: `Event Ingested: ${payload.data.event_name || "Unknown event"}`,
              raw: payload.data
            }
          } else if (payload.type === "alert") {
            setTotalAlerts((prev) => prev + 1)
            const alertState = payload.data.state || "triggered"
            const isTriggered = alertState.toLowerCase() === "triggered"
            const isResolved = alertState.toLowerCase() === "resolved"

            parsedLog = {
              id: crypto.randomUUID(),
              timestamp: payload.data.timestamp || new Date().toISOString(),
              type: "alert",
              label: isTriggered ? "ALERT BREACH" : isResolved ? "ALERT RECOVERY" : "ALERT UPDATE",
              title: `[${alertState.toUpperCase()}] ${payload.data.rule_name || "Alert Threshold"}`,
              raw: payload.data
            }

            // Sound siren & trigger overlay warning banner for breaches
            if (isTriggered) {
              playSirenAlertSound()
              setActiveBannerAlert({
                id: payload.data.rule_id || crypto.randomUUID(),
                name: payload.data.rule_name || "Alert Rule Limit Exceeded",
                state: alertState,
                metricType: payload.data.metric_type || "errors",
                value: payload.data.value || 0,
                threshold: payload.data.threshold || 0,
                timestamp: payload.data.timestamp || new Date().toISOString()
              })
            } else if (isResolved) {
              playSuccessChime()
              // Dismiss banner if same rule got resolved
              setActiveBannerAlert((current) => {
                if (current && current.name === payload.data.rule_name) {
                  return null
                }
                return current
              })
            }
          }

          if (parsedLog) {
            // Buffer logs if page is paused (frozen tail logs)
            if (isPaused) {
              logsBufferRef.current.push(parsedLog)
            } else {
              setLogs((prev) => {
                const next = [...prev, parsedLog!]
                return next.slice(-200)
              })
            }
          }
        } catch (err) {
          console.error("Malformed log message parse failure:", err)
        }
      }

      ws.onerror = (err) => {
        console.error("WebSocket socket error encountered:", err)
        addSystemLog("WebSocket pipeline error. Inspect connection rules.")
      }

      ws.onclose = (event) => {
        setConnectionStatus("disconnected")
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current)
        
        // Handle custom closed codes
        let reason = "Socket closed by gateway server."
        if (event.code === 1008) {
          reason = "Access policy violation: Invalid JWT or multi-tenant boundary denied."
        }
        addSystemLog(`Connection severed. Reason: ${reason} (Code: ${event.code})`)

        // Trigger exponential reconnect backoff
        if (event.code !== 1008) {
          const nextRetrySecs = Math.min(30, Math.pow(2, reconnectCount) + Math.random() * 2)
          addSystemLog(`Attempting auto reconnect in ${nextRetrySecs.toFixed(1)} seconds...`)
          
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectCount((c) => c + 1)
            connectWebSocket()
          }, nextRetrySecs * 1000)
        }
      }
    } catch (e) {
      addSystemLog(`Failed to establish socket instantiation: ${e}`)
      setConnectionStatus("disconnected")
    }
  }

  // Handle switching Organizations
  useEffect(() => {
    // Reset stats & log history
    setLogs([])
    logsBufferRef.current = []
    setTotalEvents(0)
    setTotalAlerts(0)
    setSelectedLog(null)
    setActiveBannerAlert(null)
    setReconnectCount(0)

    if (organization) {
      connectWebSocket()
    }

    return () => {
      if (socketRef.current) {
        socketRef.current.close()
      }
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current)
    }
  }, [organization])

  // Pause / Resume buffering handler
  const handleTogglePause = () => {
    if (isPaused) {
      // Catch up logs buffer
      if (logsBufferRef.current.length > 0) {
        setLogs((prev) => {
          const next = [...prev, ...logsBufferRef.current]
          return next.slice(-200)
        })
        logsBufferRef.current = []
      }
      setIsPaused(false)
      addSystemLog("Terminal stream resumed. Catching up tail logs.")
    } else {
      setIsPaused(true)
      addSystemLog("Terminal stream paused. Buffering incoming telemetry...")
    }
  }

  // Clear log screen
  const handleClearLogs = () => {
    setLogs([])
    logsBufferRef.current = []
    setSelectedLog(null)
    addSystemLog("Terminal logs cleared by user.")
  }

  // Auto-scroll handler
  useEffect(() => {
    if (autoScrollRef.current && terminalEndRef.current && !isPaused) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [logs, isPaused])

  // Helper to format values
  const getMetricLabel = (m: string) => {
    const maps: any = {
      error_count: "Error Count",
      page_views: "Page Views",
      bounce_rate: "Bounce Rate (%)",
      error_rate: "Error Rate (%)",
      unique_visitors: "Unique Visitors"
    }
    return maps[m] || m
  }

  // Copy parsed JSON block to clipboard
  const handleCopyJSON = () => {
    if (!selectedLog) return
    navigator.clipboard.writeText(JSON.stringify(selectedLog.raw, null, 2))
    setCopiedLogText(true)
    setTimeout(() => setCopiedLogText(false), 2000)
  }

  // Dynamic filter lists
  const filteredLogs = logs.filter((log) => {
    if (filterType !== "all" && log.type !== filterType) return false
    
    if (searchQuery.trim() !== "") {
      const query = searchQuery.toLowerCase()
      const eventNameMatch = log.raw.event_name && log.raw.event_name.toLowerCase().includes(query)
      const ruleNameMatch = log.raw.rule_name && log.raw.rule_name.toLowerCase().includes(query)
      const stateMatch = log.raw.state && log.raw.state.toLowerCase().includes(query)
      const titleMatch = log.title.toLowerCase().includes(query)
      
      return eventNameMatch || ruleNameMatch || stateMatch || titleMatch
    }
    
    return true
  })

  return (
    <div className="space-y-6 relative">
      
      {/* ==========================================
          A. FLOATING SIREN WARNING ALARM BANNER
          ========================================== */}
      {activeBannerAlert && (
        <div className="fixed top-6 right-6 z-[100] max-w-md w-full animate-slideIn">
          <div className="glassmorphism border-red-500/30 bg-red-950/20 text-white rounded-2xl p-5 shadow-[0_10px_40px_rgba(239,68,68,0.3)] border relative overflow-hidden">
            
            {/* Alarm siren glowing ripple */}
            <span className="absolute top-0 right-0 h-24 w-24 rounded-full bg-red-500/5 -mr-4 -mt-4 animate-ping" />
            
            <button
              onClick={() => setActiveBannerAlert(null)}
              className="absolute top-3.5 right-3.5 p-1 bg-red-950/40 hover:bg-red-900/40 rounded-lg text-red-300 hover:text-white transition"
              title="Dismiss Notification"
            >
              <X className="h-4 w-4" />
            </button>

            <div className="flex gap-4">
              <div className="h-10 w-10 rounded-xl bg-red-600 flex items-center justify-center text-white shrink-0 shadow-[0_4px_15px_rgba(239,68,68,0.4)] animate-pulse">
                <ShieldAlert className="h-5 w-5" />
              </div>
              <div className="space-y-1.5 flex-1 pr-6">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-extrabold uppercase bg-red-600 px-2 py-0.5 rounded text-white tracking-widest animate-pulse">
                    Alert Triggered
                  </span>
                  <span className="text-[10px] text-red-300 font-mono">
                    {new Date(activeBannerAlert.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <h4 className="text-sm font-black tracking-tight">{activeBannerAlert.name}</h4>
                <p className="text-xs text-red-200/80 leading-relaxed font-medium">
                  Rule evaluated threshold has been violated! Recorded a metric value of{" "}
                  <strong className="text-white underline font-mono">
                    {activeBannerAlert.value.toFixed(1)}
                  </strong>{" "}
                  on type <span className="font-mono">{getMetricLabel(activeBannerAlert.metricType)}</span>.
                </p>
                <div className="pt-2 border-t border-red-500/10 flex items-center justify-between gap-4">
                  <span className="text-[10px] text-red-300 font-mono">
                    Limit: {activeBannerAlert.value > activeBannerAlert.threshold ? ">" : "<"} {activeBannerAlert.threshold}
                  </span>
                  <a
                    href="/dashboard/alerts"
                    className="text-[10px] font-extrabold text-white hover:underline uppercase flex items-center gap-1"
                  >
                    Manage Rules
                    <ArrowDownCircle className="h-3 w-3 -rotate-90" />
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ==========================================
          1. PAGE HEADER
          ========================================== */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-900 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full shrink-0 ${
              connectionStatus === "connected" 
                ? "bg-emerald-500 animate-pulse shadow-[0_0_8px_#10b981]" 
                : connectionStatus === "connecting" || connectionStatus === "reconnecting"
                ? "bg-amber-500 animate-spin" 
                : "bg-red-500"
            }`} />
            <span className={`text-[10px] uppercase tracking-widest font-bold ${
              connectionStatus === "connected" ? "text-emerald-400" : "text-zinc-500"
            }`}>
              {connectionStatus === "connected" 
                ? "Subscribed to Live Gateway" 
                : connectionStatus === "reconnecting"
                ? `Reconnecting (Try #${reconnectCount})...`
                : "Disconnected"}
            </span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight mt-1 text-white">
            Live Stream <span className="gradient-text">Ticker</span>
          </h1>
          <p className="text-zinc-400 text-xs mt-1">
            Persistent raw terminal console logging event ingestions and alert rules threshold state machine transitions.
          </p>
        </div>

        {/* Global Sound Toggles and Info */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={`p-2.5 rounded-xl border transition flex items-center justify-center ${
              soundEnabled 
                ? "bg-purple-950/15 border-purple-500/10 text-purple-400 hover:bg-purple-900/10" 
                : "bg-zinc-900 border-zinc-800 text-zinc-500 hover:bg-zinc-850"
            }`}
            title={soundEnabled ? "Disable Synthesizer Audio Alerts" : "Enable Synthesizer Audio Alerts"}
          >
            {soundEnabled ? <Volume2 className="h-4.5 w-4.5" /> : <VolumeX className="h-4.5 w-4.5" />}
          </button>

          <div className="px-3.5 py-2 bg-zinc-950/80 border border-zinc-900 rounded-xl text-[10px] font-mono text-zinc-400 flex items-center gap-2">
            <Server className="h-3.5 w-3.5 text-zinc-550" />
            <span>Port: <strong>8000</strong></span>
          </div>
        </div>
      </header>

      {/* ==========================================
          2. TELEMETRY STATS COUNTER SUMMARY PANELS
          ========================================== */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        
        {/* Metric A: Log Count */}
        <div className="glassmorphism glow-border p-4 rounded-xl space-y-1">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Terminal Buffer</span>
          <div className="flex items-center justify-between">
            <span className="text-lg font-black text-white">{filteredLogs.length}</span>
            <Terminal className="h-4.5 w-4.5 text-zinc-650" />
          </div>
        </div>

        {/* Metric B: Ingested Events */}
        <div className="glassmorphism glow-border p-4 rounded-xl space-y-1">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Ingested Events</span>
          <div className="flex items-center justify-between">
            <span className="text-lg font-black text-purple-400">{totalEvents}</span>
            <Zap className="h-4.5 w-4.5 text-purple-500 animate-pulse-slow" />
          </div>
        </div>

        {/* Metric C: Violations Evaluated */}
        <div className="glassmorphism glow-border p-4 rounded-xl space-y-1">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Alert Triggers</span>
          <div className="flex items-center justify-between">
            <span className="text-lg font-black text-red-400">{totalAlerts}</span>
            <ShieldAlert className="h-4.5 w-4.5 text-red-500" />
          </div>
        </div>

        {/* Metric D: Connection Uptime */}
        <div className="glassmorphism glow-border p-4 rounded-xl space-y-1">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Connection State</span>
          <div className="flex items-center justify-between">
            <span className={`text-xs uppercase font-extrabold px-1.5 py-0.5 rounded ${
              connectionStatus === "connected"
                ? "bg-emerald-500/10 text-emerald-450 border border-emerald-500/10"
                : connectionStatus === "connecting" || connectionStatus === "reconnecting"
                ? "bg-amber-500/10 text-amber-450 border border-amber-500/10"
                : "bg-red-500/10 text-red-450 border border-red-500/10"
            }`}>
              {connectionStatus.toUpperCase()}
            </span>
            {connectionStatus === "connected" ? <Wifi className="h-4.5 w-4.5 text-emerald-500" /> : <WifiOff className="h-4.5 w-4.5 text-zinc-500" />}
          </div>
        </div>

      </div>

      {/* ==========================================
          3. MAIN STREAM TERMINAL PLATFORM
          ========================================== */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-stretch min-h-[580px]">
        
        {/* A. TERMINAL LOG VIEW PANEL (2 Columns Span) */}
        <div className="xl:col-span-2 flex flex-col justify-between glassmorphism glow-border rounded-2xl overflow-hidden bg-black/40 border">
          
          {/* Header controls bar */}
          <div className="p-4 border-b border-zinc-900 bg-zinc-950/90 flex flex-col sm:flex-row sm:items-center justify-between gap-3 select-none">
            
            {/* Filter segments */}
            <div className="flex items-center gap-1.5 bg-zinc-900 p-1 rounded-lg border border-zinc-850">
              <button
                onClick={() => setFilterType("all")}
                className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase transition ${
                  filterType === "all" ? "bg-zinc-800 text-white" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                All Logs
              </button>
              <button
                onClick={() => setFilterType("event")}
                className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase transition ${
                  filterType === "event" ? "bg-purple-900/30 text-purple-300 border border-purple-800/10" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                Events
              </button>
              <button
                onClick={() => setFilterType("alert")}
                className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase transition ${
                  filterType === "alert" ? "bg-red-900/30 text-red-300 border border-red-800/10" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                Alerts
              </button>
              <button
                onClick={() => setFilterType("system")}
                className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase transition ${
                  filterType === "system" ? "bg-zinc-800 text-zinc-300" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                System
              </button>
            </div>

            {/* Action buttons and filters */}
            <div className="flex items-center gap-3">
              
              {/* Search box input */}
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-zinc-550" />
                <input
                  type="text"
                  placeholder="Filter ticker log content..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full sm:w-44 bg-zinc-900 border border-zinc-850 hover:border-zinc-800 focus:border-purple-550 focus:ring-0 rounded-lg pl-8 pr-3.5 py-1.5 text-[10px] outline-none text-white placeholder-zinc-650 transition"
                />
              </div>

              {/* Pause/Resume logs stream */}
              <button
                onClick={handleTogglePause}
                className={`flex items-center gap-1.5 px-3 py-2 border rounded-lg text-[10px] font-bold transition uppercase ${
                  isPaused 
                    ? "bg-amber-950/15 border-amber-500/20 text-amber-450 hover:bg-amber-900/20" 
                    : "bg-zinc-900 border-zinc-850 text-zinc-400 hover:bg-zinc-850"
                }`}
              >
                {isPaused ? <Play className="h-3 w-3 fill-amber-450 text-amber-450" /> : <Pause className="h-3 w-3 fill-zinc-400" />}
                {isPaused ? "Resume log" : "Pause Log"}
              </button>

              {/* Clear logs panel */}
              <button
                onClick={handleClearLogs}
                className="p-2 bg-zinc-900 hover:bg-red-950/20 hover:border-red-900/20 hover:text-red-400 rounded-lg text-zinc-450 border border-zinc-850 transition"
                title="Clear Logs Screen"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>

          </div>

          {/* Terminal Code Logs Frame */}
          <div className="flex-1 p-5 font-mono text-[10px] overflow-y-auto max-h-[480px] bg-black/90 space-y-2 border-b border-zinc-900 select-text scrollbar-thin scrollbar-thumb-zinc-800">
            {filteredLogs.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-32 text-center space-y-2">
                <Terminal className="h-8 w-8 text-zinc-700 animate-pulse" />
                <span className="text-zinc-500 max-w-xs block leading-relaxed">
                  Terminal stream silent. Trigger ingestion events or await background alert rule cron tasks evaluations.
                </span>
              </div>
            ) : (
              filteredLogs.map((log) => {
                const isAlert = log.type === "alert"
                const isSystem = log.type === "system"
                const isTriggeredAlert = isAlert && log.label.includes("BREACH")
                const isResolvedAlert = isAlert && log.label.includes("RECOVERY")
                
                // Color codes
                let textClass = "text-zinc-350"
                let labelBg = "bg-zinc-900 text-zinc-400 border border-zinc-850"

                if (isTriggeredAlert) {
                  textClass = "text-red-400 font-bold"
                  labelBg = "bg-red-500/10 text-red-400 border border-red-500/20 shadow-[0_0_10px_rgba(239,68,68,0.1)]"
                } else if (isResolvedAlert) {
                  textClass = "text-emerald-400 font-bold"
                  labelBg = "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                } else if (log.type === "event") {
                  textClass = "text-purple-300"
                  labelBg = "bg-purple-500/10 text-purple-300 border border-purple-500/10"
                } else if (isSystem) {
                  textClass = "text-cyan-400"
                  labelBg = "bg-cyan-950/30 text-cyan-400 border border-cyan-500/10"
                }

                const isSelected = selectedLog?.id === log.id

                return (
                  <div
                    key={log.id}
                    onClick={() => setSelectedLog(log)}
                    className={`group flex items-start gap-3 p-2 rounded-lg cursor-pointer transition select-text ${
                      isSelected 
                        ? "bg-purple-950/20 border border-purple-500/20 text-white" 
                        : "hover:bg-zinc-950 hover:text-zinc-200 border border-transparent"
                    }`}
                  >
                    {/* Timestamp */}
                    <span className="text-zinc-600 shrink-0 select-none">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>

                    {/* Tag Label */}
                    <span className={`shrink-0 px-2 py-0.5 rounded text-[8px] font-extrabold uppercase font-sans tracking-wide ${labelBg} select-none`}>
                      {log.label}
                    </span>

                    {/* Log text description */}
                    <span className={`flex-1 break-all ${textClass}`}>
                      {log.title}
                    </span>

                    {/* Metadata indicators */}
                    <span className="text-zinc-700 group-hover:text-zinc-500 text-[8px] shrink-0 font-sans tracking-wider uppercase select-none opacity-0 group-hover:opacity-100 transition">
                      View Payload
                    </span>
                  </div>
                )
              })
            )}
            
            <div ref={terminalEndRef} />
          </div>

          {/* Footer details terminal stats */}
          <div className="p-3 bg-zinc-950/80 border-t border-zinc-900 flex items-center justify-between text-[9px] text-zinc-500 font-mono select-none">
            <span>Terminal Log Tail Buffer Max: 200 items</span>
            <button 
              onClick={() => {
                autoScrollRef.current = !autoScrollRef.current
                addSystemLog(`Autoscroll toggled: ${autoScrollRef.current ? "ON" : "OFF"}`)
              }}
              className={`hover:text-purple-400 flex items-center gap-1.5 transition ${
                autoScrollRef.current ? "text-purple-400" : "text-zinc-550"
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${autoScrollRef.current ? "bg-purple-500 animate-pulse" : "bg-zinc-700"}`} />
              Autoscroll: {autoScrollRef.current ? "ACTIVE" : "PAUSED"}
            </button>
          </div>

        </div>

        {/* B. DETAILED METADATA COMPILATION DRAWER (1 Column Span) */}
        <div className="glassmorphism glow-border rounded-2xl flex flex-col justify-between overflow-hidden bg-black/35 border h-full">
          
          <div className="p-4 border-b border-zinc-900 bg-zinc-950/90 flex items-center justify-between">
            <h3 className="text-xs font-bold text-white flex items-center gap-2">
              <Database className="h-4.5 w-4.5 text-purple-400" />
              Log Payload Inspector
            </h3>
            {selectedLog && (
              <button
                onClick={handleCopyJSON}
                className="p-1.5 bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 text-zinc-400 hover:text-white rounded-lg transition"
                title="Copy full JSON payload"
              >
                {copiedLogText ? <Check className="h-3.5 w-3.5 text-emerald-450" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            )}
          </div>

          {selectedLog ? (
            <div className="flex-1 p-5 overflow-y-auto space-y-5 select-text scrollbar-thin">
              
              {/* Event general outline */}
              <div className="space-y-3.5 border-b border-zinc-900 pb-4">
                <div>
                  <span className="text-[9px] uppercase tracking-wider font-bold text-zinc-500 block">Logging Scope</span>
                  <span className="text-xs font-extrabold text-white mt-0.5 block">{selectedLog.title}</span>
                </div>

                <div className="grid grid-cols-2 gap-3.5 text-[10px]">
                  <div>
                    <span className="text-[9px] uppercase tracking-wider font-bold text-zinc-550 block">Log Type</span>
                    <span className="font-bold text-purple-400 uppercase mt-0.5 block">{selectedLog.type}</span>
                  </div>
                  <div>
                    <span className="text-[9px] uppercase tracking-wider font-bold text-zinc-550 block">Evaluation Date</span>
                    <span className="font-mono text-zinc-350 mt-0.5 block">
                      {new Date(selectedLog.timestamp).toLocaleDateString()} {new Date(selectedLog.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              </div>

              {/* Event Detailed attributes table */}
              {selectedLog.type === "event" && (
                <div className="space-y-3 border-b border-zinc-900 pb-4">
                  <span className="text-[9px] uppercase tracking-wider font-bold text-zinc-500 block">Telemetry Attributes</span>
                  
                  <div className="bg-zinc-950/70 p-3.5 rounded-xl border border-zinc-900 text-[10px] space-y-2 font-mono">
                    <div className="flex justify-between items-center text-zinc-400">
                      <span>Event Name:</span>
                      <span className="font-bold text-white">{selectedLog.raw.event_name}</span>
                    </div>
                    {selectedLog.raw.data_source_id && (
                      <div className="flex justify-between items-center text-zinc-450">
                        <span>Source ID:</span>
                        <span className="text-zinc-300 truncate max-w-[120px]">{selectedLog.raw.data_source_id}</span>
                      </div>
                    )}
                    {selectedLog.raw.id && (
                      <div className="flex justify-between items-center text-zinc-450">
                        <span>UUID Trace:</span>
                        <span className="text-zinc-300 truncate max-w-[120px]">{selectedLog.raw.id}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Alert threshold violations details table */}
              {selectedLog.type === "alert" && (
                <div className="space-y-3 border-b border-zinc-900 pb-4">
                  <span className="text-[9px] uppercase tracking-wider font-bold text-zinc-550 block">Violation Metrics</span>
                  
                  <div className="bg-zinc-950/70 p-3.5 rounded-xl border border-zinc-900 text-[10px] space-y-2 font-mono">
                    <div className="flex justify-between items-center text-zinc-400">
                      <span>Rule Name:</span>
                      <span className="font-bold text-white truncate max-w-[120px]">{selectedLog.raw.rule_name}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-400">
                      <span>Trigger state:</span>
                      <span className={`font-extrabold uppercase px-1.5 py-0.5 rounded text-[8px] ${
                        selectedLog.raw.state?.toLowerCase() === "triggered" 
                          ? "bg-red-500/10 text-red-400" 
                          : "bg-emerald-500/10 text-emerald-400"
                      }`}>{selectedLog.raw.state}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-400">
                      <span>Evaluated Metric:</span>
                      <span className="text-zinc-300">{getMetricLabel(selectedLog.raw.metric_type)}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-400">
                      <span>Violated Value:</span>
                      <span className="font-bold text-red-400">{selectedLog.raw.value?.toFixed(2) || "0.0"}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-400">
                      <span>Threshold Rule:</span>
                      <span className="text-zinc-300">{selectedLog.raw.value > selectedLog.raw.threshold ? ">" : "<"} {selectedLog.raw.threshold}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Raw JSON viewer */}
              <div className="space-y-2">
                <span className="text-[9px] uppercase tracking-wider font-bold text-zinc-550 block">JSON Raw Payload</span>
                <div className="bg-zinc-950/80 border border-zinc-900 p-4 rounded-xl max-h-56 overflow-y-auto text-[9.5px] font-mono leading-relaxed text-zinc-400 shadow-inner">
                  <pre>{JSON.stringify(selectedLog.raw, null, 2)}</pre>
                </div>
              </div>

            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-2">
              <Sliders className="h-6 w-6 text-zinc-700 animate-pulse-slow" />
              <span className="text-zinc-550 text-[11px] max-w-xs leading-relaxed font-medium">
                Select an active log row from the scrolling console log stream to inspect structural telemetry properties and parameters.
              </span>
            </div>
          )}

          <div className="p-3 bg-zinc-950/80 border-t border-zinc-900 text-[9px] text-zinc-550 text-center font-mono">
            <span>Prettified structural telemetry viewer</span>
          </div>

        </div>

      </div>

    </div>
  )
}

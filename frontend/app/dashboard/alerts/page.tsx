"use client"

import { useEffect, useState } from "react"
import { useGlobalStore } from "@/store/global-store"
import { api } from "@/lib/api-client"
import {
  ShieldAlert,
  Plus,
  Trash2,
  Bell,
  BellOff,
  History,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Clock,
  Mail,
  Slack,
  Settings,
  RefreshCw,
  Sliders,
  ChevronDown,
  Lock
} from "lucide-react"

interface AlertRule {
  id: string
  organization_id: string
  name: string
  description: string | null
  is_enabled: boolean
  metric_type: string
  operator: string
  threshold: number
  time_window_minutes: number
  snooze_duration_minutes: number
  slack_webhook: string | null
  email_recipient: string | null
  current_state: string // "triggered" | "ok" | "muted"
  muted_until: string | null
  created_at: string
}

interface AlertHistory {
  id: string
  alert_rule_id: string
  state: string
  value: number
  threshold: number
  details: any
  created_at: string
}

export default function AlertsPage() {
  const { organization, organizations } = useGlobalStore()

  // RBAC permissions check
  const activeRole = organizations.find((o) => o.organization.id === organization?.id)?.role || "viewer"
  const isReadOnly = activeRole === "viewer"

  // Data States
  const [rules, setRules] = useState<AlertRule[]>([])
  const [histories, setHistories] = useState<AlertHistory[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  // Form States
  const [createRuleModal, setCreateRuleModal] = useState(false)
  const [snoozeModal, setSnoozeModal] = useState<AlertRule | null>(null)
  
  const [newRuleName, setNewRuleName] = useState("")
  const [newRuleDesc, setNewRuleDesc] = useState("")
  const [metricType, setMetricType] = useState("error_count")
  const [operator, setOperator] = useState(">")
  const [threshold, setThreshold] = useState<number>(10)
  const [timeWindow, setTimeWindow] = useState<number>(10)
  const [snoozeDuration, setSnoozeDuration] = useState<number>(30)
  const [slackWebhook, setSlackWebhook] = useState("")
  const [emailRecipient, setEmailRecipient] = useState("")
  
  const [selectedSnoozeMins, setSelectedSnoozeMins] = useState<number>(30)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Fetch Rules & History
  const fetchAlertsData = async () => {
    if (!organization) return
    setIsLoading(true)
    try {
      // 1. Fetch alert rules
      const rulesList = await api.get<AlertRule[]>(
        `/api/v1/organizations/${organization.id}/alerts/rules`
      )
      setRules(rulesList)

      // 2. Fetch history logs
      const historyList = await api.get<AlertHistory[]>(
        `/api/v1/organizations/${organization.id}/alerts/history`
      )
      setHistories(historyList)
    } catch (err) {
      console.error("Failed to load alerts telemetry:", err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchAlertsData()
  }, [organization, refreshTrigger])

  // Create rule
  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!organization || isReadOnly || !newRuleName.trim()) return
    setIsSubmitting(true)
    try {
      await api.post(
        `/api/v1/organizations/${organization.id}/alerts/rules`,
        {
          name: newRuleName,
          description: newRuleDesc || null,
          metric_type: metricType,
          operator: operator,
          threshold: Number(threshold),
          time_window_minutes: Number(timeWindow),
          snooze_duration_minutes: Number(snoozeDuration),
          slack_webhook: slackWebhook.trim() || null,
          email_recipient: emailRecipient.trim() || null,
          is_enabled: true
        }
      )
      // Reset form fields
      setNewRuleName("")
      setNewRuleDesc("")
      setSlackWebhook("")
      setEmailRecipient("")
      setCreateRuleModal(false)
      await fetchAlertsData()
    } catch (err) {
      console.error("Failed to create alert rule:", err)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Delete rule
  const handleDeleteRule = async (ruleId: string) => {
    if (!organization || isReadOnly) return
    if (!confirm("Are you sure you want to delete this alert rule? Previous history audits will be preserved.")) return
    try {
      await api.delete(
        `/api/v1/organizations/${organization.id}/alerts/rules/${ruleId}`
      )
      await fetchAlertsData()
    } catch (err) {
      console.error("Rule deletion failed:", err)
    }
  }

  // Snooze rule
  const handleSnoozeRuleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!organization || isReadOnly || !snoozeModal) return
    setIsSubmitting(true)
    try {
      await api.post(
        `/api/v1/organizations/${organization.id}/alerts/rules/${snoozeModal.id}/snooze`,
        { snooze_duration_minutes: Number(selectedSnoozeMins) }
      )
      setSnoozeModal(null)
      await fetchAlertsData()
    } catch (err) {
      console.error("Failed to snooze rule:", err)
    } finally {
      setIsSubmitting(false)
    }
  }

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
            <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse shadow-[0_0_8px_#ef4444]" />
            <span className="text-[10px] uppercase tracking-widest text-red-400 font-bold">Diagnostics Center</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight mt-1 text-white">
            Alert <span className="gradient-text">Studio</span>
          </h1>
          <p className="text-zinc-400 text-xs mt-1">
            Configure threshold rules, execute manual snooze windows, and verify history transition audits.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setRefreshTrigger((prev) => prev + 1)}
            disabled={isLoading}
            className="p-2.5 bg-zinc-900 border border-zinc-800 rounded-xl hover:bg-zinc-850 transition text-zinc-450"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin text-red-500" : ""}`} />
          </button>

          {!isReadOnly && (
            <button
              onClick={() => setCreateRuleModal(true)}
              className="flex items-center gap-1.5 px-3.5 py-2.5 bg-red-600 hover:bg-red-500 transition rounded-xl text-xs font-bold text-white shadow-[0_4px_12px_rgba(239,68,68,0.25)] animate-pulse-slow"
            >
              <Plus className="h-4 w-4" />
              New Alert Rule
            </button>
          )}
        </div>
      </header>

      {/* RBAC Viewer guard warning */}
      {isReadOnly && (
        <div className="flex items-center gap-2 px-4 py-3 bg-zinc-950/80 border border-zinc-900 rounded-xl text-zinc-400 text-xs">
          <Lock className="h-4 w-4 text-red-400 shrink-0" />
          <span>You are logged in with <strong>Viewer role</strong>. Modifying alert thresholds, rules, or snooze statuses are read-only.</span>
        </div>
      )}

      {/* 2. LOADING TIER */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-32 gap-3">
          <Loader2 className="h-9 w-9 animate-spin text-red-500" />
          <span className="text-zinc-400 text-xs font-medium">Reading alarm parameters from DB...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          
          {/* ==========================================
              A. ACTIVE RULES LIST (2 Columns span)
              ========================================== */}
          <div className="xl:col-span-2 space-y-6">
            <h2 className="text-base font-bold text-white flex items-center gap-2 px-1">
              <Sliders className="h-4.5 w-4.5 text-red-400" />
              Active Alert Thresholds ({rules.length})
            </h2>

            {rules.length === 0 ? (
              <div className="text-center py-20 bg-zinc-950/20 border border-dashed border-zinc-900 rounded-3xl space-y-4">
                <span className="text-zinc-500 text-xs block max-w-sm mx-auto leading-relaxed">
                  No alert threshold rules are configured in this workspace. Set critical triggers on errors, traffic surges, or bounce rate anomalies.
                </span>
                {!isReadOnly && (
                  <button
                    onClick={() => setCreateRuleModal(true)}
                    className="flex items-center gap-1.5 mx-auto px-4 py-2 bg-red-950/20 hover:bg-red-900/10 border border-red-500/10 transition rounded-xl text-xs font-bold text-red-400"
                  >
                    <Plus className="h-4 w-4" />
                    Configure First Rule
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {rules.map((rule) => {
                  const isTriggered = rule.current_state.toLowerCase() === "triggered"
                  const isMuted = rule.current_state.toLowerCase() === "muted" || (rule.muted_until && new Date(rule.muted_until) > new Date())
                  
                  return (
                    <div
                      key={rule.id}
                      className={`glassmorphism glow-border rounded-2xl p-5 flex flex-col justify-between space-y-4 transition hover:scale-[1.01] relative ${
                        isTriggered
                          ? "shadow-[0_4px_20px_rgba(239,68,68,0.15)] border-red-500/20 bg-red-950/5"
                          : isMuted
                          ? "shadow-[0_4px_15px_rgba(245,158,11,0.08)] border-amber-500/10 bg-amber-950/5"
                          : ""
                      }`}
                    >
                      {/* Trash rule action */}
                      {!isReadOnly && (
                        <button
                          onClick={() => handleDeleteRule(rule.id)}
                          className="absolute top-4 right-4 p-2 bg-zinc-900/90 hover:bg-red-950/20 hover:text-red-400 rounded-lg text-zinc-500 border border-zinc-850 hover:border-red-900/20 transition"
                          title="Delete Threshold Rule"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}

                      <div className="space-y-1.5">
                        <div className="flex items-center gap-2">
                          <span className={`h-2 w-2 rounded-full shrink-0 ${
                            isTriggered ? "bg-red-500 animate-pulse" : isMuted ? "bg-amber-500" : "bg-emerald-500"
                          }`} />
                          <h3 className="text-sm font-bold text-white truncate max-w-[80%] pr-4">{rule.name}</h3>
                        </div>

                        <p className="text-[11px] text-zinc-450 leading-relaxed min-h-[32px]">
                          {rule.description || "Diagnostics threshold alarm rule."}
                        </p>
                      </div>

                      {/* Threshold metadata specifications */}
                      <div className="bg-zinc-950/60 p-3 rounded-xl border border-zinc-900 space-y-2 text-[11px]">
                        <div className="flex justify-between items-center text-zinc-400">
                          <span>Condition:</span>
                          <span className="font-mono text-zinc-200">
                            {getMetricLabel(rule.metric_type)} {rule.operator} {rule.threshold}
                          </span>
                        </div>
                        <div className="flex justify-between items-center text-zinc-400">
                          <span>Evaluation Frame:</span>
                          <span className="font-mono text-zinc-200">{rule.time_window_minutes} mins</span>
                        </div>
                        
                        {/* Snooze state detail */}
                        {isMuted && rule.muted_until && (
                          <div className="pt-1.5 border-t border-zinc-900 flex justify-between items-center text-[10px] text-amber-400 font-mono">
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3 animate-spin-slow" />
                              Muted until:
                            </span>
                            <span>{new Date(rule.muted_until).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>
                        )}
                      </div>

                      {/* Footer targets and snooze actions */}
                      <div className="flex items-center justify-between border-t border-zinc-900/40 pt-3 text-[10px] text-zinc-550 font-mono">
                        <div className="flex items-center gap-2">
                          {rule.slack_webhook && <span title="Slack Hook Set"><Slack className="h-3.5 w-3.5 text-zinc-500" /></span>}
                          {rule.email_recipient && <span title={`Email: ${rule.email_recipient}`}><Mail className="h-3.5 w-3.5 text-zinc-500" /></span>}
                          {!rule.slack_webhook && !rule.email_recipient && <span title="No channels set"><BellOff className="h-3.5 w-3.5 text-zinc-650" /></span>}
                        </div>

                        {!isReadOnly && (
                          <button
                            onClick={() => setSnoozeModal(rule)}
                            className="flex items-center gap-1 text-[10px] font-bold text-zinc-400 hover:text-white transition"
                          >
                            <Bell className="h-3 w-3 text-red-500" />
                            {isMuted ? "Change Snooze" : "Snooze Alert"}
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* ==========================================
              B. ALERT AUDIT LOGS / HISTORY (1 Column span)
              ========================================== */}
          <div className="space-y-6">
            <h2 className="text-base font-bold text-white flex items-center gap-2 px-1">
              <History className="h-4.5 w-4.5 text-indigo-400" />
              Transition Audit Logs
            </h2>

            {histories.length === 0 ? (
              <div className="text-center py-16 bg-zinc-955/35 border border-zinc-900 rounded-2xl text-zinc-500 text-xs font-medium">
                No recent rule state transitions recorded.
              </div>
            ) : (
              <div className="bg-zinc-955/50 border border-zinc-900 rounded-2xl divide-y divide-zinc-900 max-h-[550px] overflow-y-auto shadow-inner">
                {histories.slice(0, 15).map((log) => {
                  const ruleObj = rules.find((r) => r.id === log.alert_rule_id)
                  const isTriggered = log.state.toLowerCase() === "triggered"
                  const isMuted = log.state.toLowerCase() === "muted"
                  
                  return (
                    <div key={log.id} className="p-4 space-y-2 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-white font-bold block truncate max-w-[65%]">
                          {ruleObj?.name || "System Alarm"}
                        </span>
                        
                        <span className={`text-[9px] uppercase font-extrabold px-1.5 py-0.5 rounded ${
                          isTriggered 
                            ? "bg-red-500/10 text-red-400 border border-red-500/10" 
                            : isMuted 
                            ? "bg-amber-500/10 text-amber-450 border border-amber-500/10"
                            : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/10"
                        }`}>
                          {log.state.toUpperCase()}
                        </span>
                      </div>

                      {/* Audit details */}
                      <div className="flex justify-between items-center text-[10px] text-zinc-500 font-mono">
                        <span>Trigger Val:</span>
                        <span className="text-zinc-400 font-bold">
                          {log.value.toFixed(1)} (Limit: {log.threshold})
                        </span>
                      </div>

                      <div className="flex justify-between items-center text-[9px] text-zinc-550 font-mono">
                        <span>Date:</span>
                        <span>{new Date(log.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

        </div>
      )}

      {/* ==========================================
          3. MODALS FOR ALERTS MANAGER
          ========================================== */}

      {/* Modal A: Create Rule */}
      {createRuleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
          <div className="glassmorphism glow-border w-full max-w-xl rounded-2xl overflow-hidden shadow-2xl relative">
            <header className="p-6 border-b border-zinc-900 flex justify-between items-center">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <ShieldAlert className="h-5 w-5 text-red-500" />
                Configure Alert Rule
              </h3>
            </header>

            <form onSubmit={handleCreateRule} className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Rule Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Critical 5xx Ingestion Failures / Spike DAU"
                  value={newRuleName}
                  onChange={(e) => setNewRuleName(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-850 focus:border-red-550 rounded-xl px-4 py-3 text-xs outline-none transition text-white placeholder-zinc-650"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Description (Optional)</label>
                <textarea
                  placeholder="Summarize the intent and target integration of this alert rule..."
                  rows={2}
                  value={newRuleDesc}
                  onChange={(e) => setNewRuleDesc(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-850 focus:border-red-550 rounded-xl px-4 py-3 text-xs outline-none transition text-white placeholder-zinc-650 resize-none"
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-1.5 col-span-1.5">
                  <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Metric Target</label>
                  <select
                    value={metricType}
                    onChange={(e) => setMetricType(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-xl text-xs font-bold text-zinc-350 px-3.5 py-3 outline-none focus:ring-1 focus:ring-red-550"
                  >
                    <option value="error_count">Error count (absolute)</option>
                    <option value="page_views">Page Views (volume)</option>
                    <option value="bounce_rate">Bounce Rate (%)</option>
                    <option value="error_rate">Error Rate (%)</option>
                    <option value="unique_visitors">Unique Visitors</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Operator</label>
                  <select
                    value={operator}
                    onChange={(e) => setOperator(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-xl text-xs font-bold text-zinc-350 px-3.5 py-3 outline-none focus:ring-1 focus:ring-red-550"
                  >
                    <option value=">">&gt; (greater than)</option>
                    <option value="<">&lt; (less than)</option>
                    <option value=">=">&gt;= (greater or equal)</option>
                    <option value="==">== (equal to)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Threshold</label>
                  <input
                    type="number"
                    step="any"
                    required
                    value={threshold}
                    onChange={(e) => setThreshold(Number(e.target.value))}
                    className="w-full bg-zinc-950 border border-zinc-855 focus:border-red-550 rounded-xl px-4 py-3 text-xs outline-none transition text-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Query Window (Minutes)</label>
                  <input
                    type="number"
                    required
                    min={1}
                    value={timeWindow}
                    onChange={(e) => setTimeWindow(Number(e.target.value))}
                    className="w-full bg-zinc-950 border border-zinc-855 focus:border-red-550 rounded-xl px-4 py-3 text-xs outline-none transition text-white"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Default Snooze (Minutes)</label>
                  <input
                    type="number"
                    required
                    min={1}
                    value={snoozeDuration}
                    onChange={(e) => setSnoozeDuration(Number(e.target.value))}
                    className="w-full bg-zinc-950 border border-zinc-855 focus:border-red-550 rounded-xl px-4 py-3 text-xs outline-none transition text-white"
                  />
                </div>
              </div>

              <div className="pt-2 border-t border-zinc-900/60 space-y-4">
                <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Integration Notification Channels (Optional)</span>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-zinc-450 uppercase block">Slack Webhook URL</label>
                    <input
                      type="url"
                      placeholder="https://hooks.slack.com/services/..."
                      value={slackWebhook}
                      onChange={(e) => setSlackWebhook(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-855 focus:border-red-550 rounded-xl px-3.5 py-2.5 text-xs outline-none transition text-white placeholder-zinc-650"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-zinc-450 uppercase block">Email Recipient</label>
                    <input
                      type="email"
                      placeholder="engineering@acme.org"
                      value={emailRecipient}
                      onChange={(e) => setEmailRecipient(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-855 focus:border-red-550 rounded-xl px-3.5 py-2.5 text-xs outline-none transition text-white placeholder-zinc-650"
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2 border-t border-zinc-900/60">
                <button
                  type="button"
                  onClick={() => setCreateRuleModal(false)}
                  className="px-4.5 py-2.5 bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 rounded-xl text-xs font-bold text-zinc-455 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4.5 py-2.5 bg-red-600 hover:bg-red-550 transition rounded-xl text-xs font-bold text-white disabled:opacity-50"
                >
                  {isSubmitting ? "Saving rule..." : "Activate Threshold"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal B: Snooze Alert Rule */}
      {snoozeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
          <div className="glassmorphism glow-border w-full max-w-md rounded-2xl overflow-hidden shadow-2xl relative">
            <header className="p-6 border-b border-zinc-900 flex justify-between items-center">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Clock className="h-5 w-5 text-amber-500" />
                Snooze Threshold Alert
              </h3>
            </header>

            <form onSubmit={handleSnoozeRuleSubmit} className="p-6 space-y-5">
              <div className="space-y-1">
                <span className="text-xs font-bold text-white block">Snooze rule: <strong>{snoozeModal.name}</strong></span>
                <span className="text-[11px] text-zinc-500 block leading-relaxed">
                  Temporarily suppress notifications and state evaluations. Rule will automatically unmute when the timeframe expires.
                </span>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Mute Timeframe</label>
                <select
                  value={selectedSnoozeMins}
                  onChange={(e) => setSelectedSnoozeMins(Number(e.target.value))}
                  className="w-full bg-zinc-950 border border-zinc-850 rounded-xl text-xs font-bold text-zinc-350 px-3.5 py-2.5 outline-none focus:ring-1 focus:ring-amber-500"
                >
                  <option value={15}>15 Minutes</option>
                  <option value={30}>30 Minutes</option>
                  <option value={60}>1 Hour</option>
                  <option value={180}>3 Hours</option>
                  <option value={1440}>24 Hours</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setSnoozeModal(null)}
                  className="px-4.5 py-2.5 bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 rounded-xl text-xs font-bold text-zinc-455 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4.5 py-2.5 bg-amber-500 hover:bg-amber-450 transition rounded-xl text-xs font-bold text-zinc-950 disabled:opacity-50 font-bold"
                >
                  {isSubmitting ? "Snoozing..." : "Apply Mute"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  )
}

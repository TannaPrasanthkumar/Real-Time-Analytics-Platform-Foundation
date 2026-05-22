"use client"

import { useEffect, useState } from "react"
import { useGlobalStore } from "@/store/global-store"
import { api } from "@/lib/api-client"
import {
  FileText,
  Plus,
  Trash2,
  Calendar,
  Mail,
  LayoutDashboard,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  RefreshCw,
  Sliders,
  Lock,
  Play,
  Download,
  X,
  Sparkles
} from "lucide-react"

interface Dashboard {
  id: string
  name: string
  description: string | null
}

interface ReportSchedule {
  id: string
  organization_id: string
  name: string
  dashboard_id: string | null
  frequency: string // "daily", "weekly", "monthly"
  recipients: string[]
  is_active: boolean
  created_at: string
}

interface ReportHistory {
  id: string
  report_schedule_id: string
  organization_id: string
  triggered_at: string
  status: string // "success" | "failed" | "pending"
  error_message: string | null
  file_path: string | null
  created_at: string
}

export default function ReportsPage() {
  const { organization, organizations } = useGlobalStore()

  // RBAC permissions check
  const activeRole = organizations.find((o) => o.organization.id === organization?.id)?.role || "viewer"
  const isReadOnly = activeRole === "viewer"

  // Data States
  const [schedules, setSchedules] = useState<ReportSchedule[]>([])
  const [histories, setHistories] = useState<ReportHistory[]>([])
  const [dashboards, setDashboards] = useState<Dashboard[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  // Form States
  const [createScheduleModal, setCreateScheduleModal] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isTriggeringId, setIsTriggeringId] = useState<string | null>(null)

  // New Schedule Fields
  const [newScheduleName, setNewScheduleName] = useState("")
  const [selectedDashboardId, setSelectedDashboardId] = useState<string>("")
  const [frequency, setFrequency] = useState("weekly")
  const [recipientEmail, setRecipientEmail] = useState("")
  const [recipients, setRecipients] = useState<string[]>([])
  const [emailError, setEmailError] = useState("")

  // Load Dashboards, Schedules and History
  const fetchReportsData = async () => {
    if (!organization) return
    setIsLoading(true)
    try {
      // 1. Fetch custom dashboards for selection dropdown
      const dashboardsList = await api.get<Dashboard[]>(
        `/api/v1/organizations/${organization.id}/dashboards`
      )
      setDashboards(dashboardsList)

      // 2. Fetch report schedules
      const schedulesList = await api.get<ReportSchedule[]>(
        `/api/v1/organizations/${organization.id}/reports/schedules`
      )
      setSchedules(schedulesList)

      // 3. Fetch report run histories
      const historyList = await api.get<ReportHistory[]>(
        `/api/v1/organizations/${organization.id}/reports/history`
      )
      setHistories(historyList)
    } catch (err) {
      console.error("Failed to load reporting context telemetry:", err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchReportsData()
  }, [organization, refreshTrigger])

  // Handle email chip addition
  const handleAddRecipient = (e: React.KeyboardEvent | React.MouseEvent) => {
    if (e.type === "keydown" && (e as React.KeyboardEvent).key !== "Enter" && (e as React.KeyboardEvent).key !== ",") {
      return
    }
    if (e.type === "keydown") {
      e.preventDefault()
    }

    const email = recipientEmail.trim().toLowerCase()
    if (!email) return

    // Simple email regex validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) {
      setEmailError("Invalid email format.")
      return
    }

    if (recipients.includes(email)) {
      setEmailError("Email already added.")
      return
    }

    setRecipients([...recipients, email])
    setRecipientEmail("")
    setEmailError("")
  }

  const handleRemoveRecipient = (email: string) => {
    setRecipients(recipients.filter((r) => r !== email))
  }

  // Create report schedule
  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!organization || isReadOnly || !newScheduleName.trim()) return

    if (recipients.length === 0) {
      setEmailError("Please add at least one recipient email address.")
      return
    }

    setIsSubmitting(true)
    try {
      await api.post(
        `/api/v1/organizations/${organization.id}/reports/schedules`,
        {
          name: newScheduleName,
          dashboard_id: selectedDashboardId || null,
          frequency: frequency,
          recipients: recipients,
          is_active: true
        }
      )

      // Reset form fields
      setNewScheduleName("")
      setSelectedDashboardId("")
      setFrequency("weekly")
      setRecipients([])
      setCreateScheduleModal(false)
      await fetchReportsData()
    } catch (err) {
      console.error("Failed to create report schedule:", err)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Soft delete report schedule
  const handleDeleteSchedule = async (scheduleId: string) => {
    if (!organization || isReadOnly) return
    if (!confirm("Are you sure you want to delete this scheduled report? Action is immediate.")) return
    try {
      await api.delete(
        `/api/v1/organizations/${organization.id}/reports/schedules/${scheduleId}`
      )
      await fetchReportsData()
    } catch (err) {
      console.error("Report schedule deletion failed:", err)
    }
  }

  // Manually trigger single report snapshot compile run
  const handleTriggerSchedule = async (scheduleId: string) => {
    if (!organization || isReadOnly) return
    setIsTriggeringId(scheduleId)
    try {
      await api.post(
        `/api/v1/organizations/${organization.id}/reports/schedules/${scheduleId}/trigger`,
        {}
      )
      // Play brief animation, reload data
      alert("Snapshot successfully compiled and dispatched in the background. Audit history updated.")
      await fetchReportsData()
    } catch (err) {
      console.error("Failed manual report generation trigger:", err)
      alert("Error compiling report snapshot: " + (err instanceof Error ? err.message : String(err)))
    } finally {
      setIsTriggeringId(null)
    }
  }

  // Authenticated secure file retrieval download
  const handleDownloadSnapshot = async (historyId: string, scheduleName: string) => {
    if (!organization) return
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null
    const filename = `${scheduleName.replace(/\s+/g, "_")}_Snapshot_${new Date().toISOString().split('T')[0]}.html`
    const url = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/organizations/${organization.id}/reports/history/${historyId}/download`

    try {
      const res = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      })
      if (!res.ok) {
        throw new Error("Failed to download snapshot file from disk archive.")
      }
      const blob = await res.blob()
      const link = document.createElement("a")
      link.href = window.URL.createObjectURL(blob)
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } catch (err) {
      console.error("Download failed:", err)
      alert("Error downloading compiled report file snapshot: " + (err instanceof Error ? err.message : String(err)))
    }
  }

  const getDashboardLabel = (dbId: string | null) => {
    if (!dbId) return "Organization Overview Layout"
    const matched = dashboards.find((d) => d.id === dbId)
    return matched ? matched.name : "Custom Dashboard"
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
      {/* 1. HEADER SECTION */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-900 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-purple-500 animate-pulse shadow-[0_0_8px_#8b5cf6]" />
            <span className="text-[10px] uppercase tracking-widest text-purple-400 font-bold flex items-center gap-1">
              <Sparkles className="h-3 w-3 animate-spin-slow" />
              SaaS Performance Digests
            </span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight mt-1 text-white">
            Reports <span className="gradient-text">Studio</span>
          </h1>
          <p className="text-zinc-400 text-xs mt-1">
            Automate recurring performance updates. Compile customized glassmorphic HTML digests of your dashboards and email them directly to stakeholders.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setRefreshTrigger((prev) => prev + 1)}
            disabled={isLoading}
            className="p-2.5 bg-zinc-900 border border-zinc-800 rounded-xl hover:bg-zinc-850 transition text-zinc-400 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin text-purple-500" : ""}`} />
          </button>

          {!isReadOnly && (
            <button
              onClick={() => {
                setRecipients([])
                setEmailError("")
                setCreateScheduleModal(true)
              }}
              className="flex items-center gap-1.5 px-3.5 py-2.5 bg-purple-650 hover:bg-purple-600 transition rounded-xl text-xs font-bold text-white shadow-[0_4px_12px_rgba(124,58,237,0.25)] animate-pulse-slow"
            >
              <Plus className="h-4 w-4" />
              Schedule Report
            </button>
          )}
        </div>
      </header>

      {/* RBAC Viewer Guard Warning */}
      {isReadOnly && (
        <div className="flex items-center gap-2 px-4 py-3 bg-zinc-950/80 border border-zinc-900 rounded-xl text-zinc-400 text-xs">
          <Lock className="h-4 w-4 text-purple-400 shrink-0" />
          <span>You are logged in with the <strong>Viewer role</strong>. Scheduling new digests or manual snapshot generation triggers are disabled.</span>
        </div>
      )}

      {/* 2. MAIN WORKSPACE CONTENT */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-32 gap-3">
          <Loader2 className="h-9 w-9 animate-spin text-purple-500" />
          <span className="text-zinc-400 text-xs font-medium">Loading report schedules & snapshots...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          
          {/* LEFT: ACTIVE SCHEDULES (2 Columns) */}
          <div className="xl:col-span-2 space-y-6">
            <h2 className="text-base font-bold text-white flex items-center gap-2 px-1">
              <Sliders className="h-4.5 w-4.5 text-purple-400" />
              Active Automated Schedules ({schedules.length})
            </h2>

            {schedules.length === 0 ? (
              <div className="text-center py-20 bg-zinc-950/20 border border-dashed border-zinc-900 rounded-3xl space-y-4">
                <span className="text-zinc-500 text-xs block max-w-sm mx-auto leading-relaxed">
                  No automated performance reports are scheduled in this workspace. Set recurring HTML performance digests for CEOs, analysts, or custom external stakeholders.
                </span>
                {!isReadOnly && (
                  <button
                    onClick={() => setCreateScheduleModal(true)}
                    className="flex items-center gap-1.5 mx-auto px-4 py-2 bg-purple-950/20 hover:bg-purple-900/10 border border-purple-500/10 transition rounded-xl text-xs font-bold text-purple-400"
                  >
                    <Plus className="h-4 w-4" />
                    Configure First Report
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {schedules.map((schedule) => (
                  <div
                    key={schedule.id}
                    className="glassmorphism glow-border rounded-2xl p-5 flex flex-col justify-between space-y-4 transition hover:scale-[1.01] relative border-purple-500/5 bg-purple-950/2 shadow-[0_4px_15px_rgba(124,58,237,0.03)]"
                  >
                    {/* Delete Action Button */}
                    {!isReadOnly && (
                      <button
                        onClick={() => handleDeleteSchedule(schedule.id)}
                        className="absolute top-4 right-4 p-2 bg-zinc-900/90 hover:bg-red-950/20 hover:text-red-400 rounded-lg text-zinc-500 border border-zinc-850 hover:border-red-900/20 transition"
                        title="Delete Schedule"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}

                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-purple-400 shrink-0" />
                        <h3 className="text-sm font-bold text-white truncate max-w-[85%] pr-6">{schedule.name}</h3>
                      </div>

                      {/* Schedule Settings Detail Card */}
                      <div className="bg-zinc-950/60 p-3.5 rounded-xl border border-zinc-900 space-y-2.5 text-[11px]">
                        <div className="flex justify-between items-center text-zinc-400">
                          <span className="flex items-center gap-1">
                            <LayoutDashboard className="h-3.5 w-3.5 text-zinc-500" />
                            Target Dashboard:
                          </span>
                          <span className="text-zinc-200 font-bold truncate max-w-[50%]">
                            {getDashboardLabel(schedule.dashboard_id)}
                          </span>
                        </div>

                        <div className="flex justify-between items-center text-zinc-400">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5 text-zinc-500" />
                            Trigger Frequency:
                          </span>
                          <span className="text-purple-400 font-bold uppercase font-mono bg-purple-950/40 border border-purple-800/10 px-1.5 py-0.5 rounded text-[10px]">
                            {schedule.frequency}
                          </span>
                        </div>

                        <div className="pt-2 border-t border-zinc-900/80">
                          <span className="text-[10px] text-zinc-500 font-bold block mb-1.5 flex items-center gap-1">
                            <Mail className="h-3.5 w-3.5 text-zinc-500" />
                            Recipients ({schedule.recipients.length}):
                          </span>
                          <div className="flex flex-wrap gap-1 max-h-16 overflow-y-auto pr-1">
                            {schedule.recipients.map((email, idx) => (
                              <span
                                key={idx}
                                className="px-1.5 py-0.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-400 text-[10px] truncate max-w-[130px]"
                                title={email}
                              >
                                {email}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Quick Action Manual Trigger button */}
                    <div className="border-t border-zinc-900/60 pt-3 flex items-center justify-between">
                      <span className="text-[9px] text-zinc-550 font-mono">
                        Added: {new Date(schedule.created_at).toLocaleDateString()}
                      </span>
                      
                      {!isReadOnly && (
                        <button
                          onClick={() => handleTriggerSchedule(schedule.id)}
                          disabled={isTriggeringId !== null}
                          className="flex items-center gap-1 text-[10px] font-extrabold text-purple-400 hover:text-purple-300 disabled:opacity-50 transition"
                        >
                          {isTriggeringId === schedule.id ? (
                            <>
                              <Loader2 className="h-3 w-3 animate-spin" />
                              Compiling...
                            </>
                          ) : (
                            <>
                              <Play className="h-3 w-3 fill-current" />
                              Trigger Run
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* RIGHT: RUN HISTORY AUDIT (1 Column) */}
          <div className="space-y-6">
            <h2 className="text-base font-bold text-white flex items-center gap-2 px-1">
              <FileText className="h-4.5 w-4.5 text-indigo-400" />
              Run Audit & Downloads
            </h2>

            {histories.length === 0 ? (
              <div className="text-center py-16 bg-zinc-950/20 border border-zinc-900 rounded-2xl text-zinc-500 text-xs font-medium">
                No report snapshot archives compiled yet.
              </div>
            ) : (
              <div className="bg-zinc-955/50 border border-zinc-900 rounded-2xl divide-y divide-zinc-900 max-h-[580px] overflow-y-auto shadow-inner">
                {histories.slice(0, 20).map((log) => {
                  const scheduleObj = schedules.find((s) => s.id === log.report_schedule_id)
                  const isSuccess = log.status.toLowerCase() === "success"
                  const isFailed = log.status.toLowerCase() === "failed"
                  const scheduleName = scheduleObj?.name || "Manual Snapshot Audit"

                  return (
                    <div key={log.id} className="p-4 space-y-3 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-white font-bold block truncate max-w-[65%]" title={scheduleName}>
                          {scheduleName}
                        </span>

                        <span
                          className={`text-[9px] uppercase font-extrabold px-1.5 py-0.5 rounded ${
                            isSuccess
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/10"
                              : isFailed
                              ? "bg-red-500/10 text-red-400 border border-red-500/10"
                              : "bg-zinc-800 text-zinc-400"
                          }`}
                        >
                          {log.status}
                        </span>
                      </div>

                      {isFailed && log.error_message && (
                        <p className="text-[10px] text-red-400/90 leading-relaxed font-mono bg-red-950/10 p-2 rounded border border-red-900/10">
                          Error: {log.error_message}
                        </p>
                      )}

                      <div className="flex justify-between items-center text-[10px] text-zinc-500 font-mono">
                        <span>Triggered At:</span>
                        <span className="text-zinc-400 font-bold">
                          {new Date(log.triggered_at).toLocaleString([], {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit"
                          })}
                        </span>
                      </div>

                      {/* Download link for success snapshots */}
                      {isSuccess && (
                        <button
                          onClick={() => handleDownloadSnapshot(log.id, scheduleName)}
                          className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 bg-zinc-900 hover:bg-zinc-850 hover:text-white border border-zinc-800 transition rounded-xl text-[10px] font-bold text-zinc-350"
                        >
                          <Download className="h-3 w-3" />
                          Download HTML Snapshot
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

        </div>
      )}

      {/* 3. CONFIGURE SCHEDULE MODAL DIALOG */}
      {createScheduleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
          <div className="glassmorphism glow-border w-full max-w-xl rounded-2xl overflow-hidden shadow-2xl relative border-purple-500/10">
            <header className="p-6 border-b border-zinc-900 flex justify-between items-center">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <FileText className="h-5 w-5 text-purple-400" />
                Schedule Automated Performance digest
              </h3>
              <button
                onClick={() => setCreateScheduleModal(false)}
                className="p-1.5 hover:bg-zinc-900 rounded-lg text-zinc-400 transition"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </header>

            <form onSubmit={handleCreateSchedule} className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
              {/* Schedule Title */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Digest Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Weekly Management Dashboard Snapshot"
                  value={newScheduleName}
                  onChange={(e) => setNewScheduleName(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-550 rounded-xl px-4 py-3 text-xs outline-none transition text-white placeholder-zinc-650"
                />
              </div>

              {/* Target dashboard dropdown & frequency selection */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Dashboard Source</label>
                  <select
                    value={selectedDashboardId}
                    onChange={(e) => setSelectedDashboardId(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-xl text-xs font-bold text-zinc-350 px-3.5 py-3 outline-none focus:ring-1 focus:ring-purple-550"
                  >
                    <option value="">Organization Telemetry Overview</option>
                    {dashboards.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Trigger Frequency</label>
                  <select
                    value={frequency}
                    onChange={(e) => setFrequency(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-xl text-xs font-bold text-zinc-350 px-3.5 py-3 outline-none focus:ring-1 focus:ring-purple-550"
                  >
                    <option value="daily">Daily Sweeps (Past 24 Hours)</option>
                    <option value="weekly">Weekly Sweeps (Past 7 Days)</option>
                    <option value="monthly">Monthly Sweeps (Past 30 Days)</option>
                  </select>
                </div>
              </div>

              {/* Email list interactive configurator */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">
                  Recipient Email Addresses
                </label>
                <div className="flex gap-2">
                  <input
                    type="email"
                    placeholder="e.g. CEO@acme.org"
                    value={recipientEmail}
                    onChange={(e) => {
                      setRecipientEmail(e.target.value)
                      setEmailError("")
                    }}
                    onKeyDown={handleAddRecipient}
                    className="flex-1 bg-zinc-950 border border-zinc-850 focus:border-purple-550 rounded-xl px-4 py-2.5 text-xs outline-none transition text-white placeholder-zinc-650"
                  />
                  <button
                    type="button"
                    onClick={handleAddRecipient}
                    className="px-4 py-2.5 bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 text-xs font-bold rounded-xl text-zinc-300 transition"
                  >
                    Add
                  </button>
                </div>

                {/* Email inputs error validation indicator */}
                {emailError && (
                  <span className="text-[10px] text-red-400 font-bold block pl-1 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    {emailError}
                  </span>
                )}

                {/* Interactive Email list chips */}
                <div className="flex flex-wrap gap-2 pt-2 min-h-[40px] p-3 bg-zinc-950 border border-zinc-900 rounded-xl">
                  {recipients.map((email) => (
                    <span
                      key={email}
                      className="flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 bg-purple-650/15 border border-purple-800/25 rounded-lg text-xs font-medium text-purple-300"
                    >
                      {email}
                      <button
                        type="button"
                        onClick={() => handleRemoveRecipient(email)}
                        className="p-0.5 hover:bg-purple-900/30 rounded text-purple-400 transition"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                  {recipients.length === 0 && (
                    <span className="text-[11px] text-zinc-600 font-medium my-auto pl-1">
                      No emails configured. Press Enter or click Add to append recipients.
                    </span>
                  )}
                </div>
              </div>

              {/* Form buttons */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-zinc-900/60">
                <button
                  type="button"
                  onClick={() => setCreateScheduleModal(false)}
                  className="px-4.5 py-2.5 bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 rounded-xl text-xs font-bold text-zinc-450 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4.5 py-2.5 bg-purple-650 hover:bg-purple-600 transition rounded-xl text-xs font-bold text-white disabled:opacity-50"
                >
                  {isSubmitting ? "Creating schedule..." : "Activate automated Digest"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

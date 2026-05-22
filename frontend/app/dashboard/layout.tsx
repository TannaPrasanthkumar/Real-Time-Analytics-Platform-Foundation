"use client"

import { useEffect, useState } from "react"
import { useRouter, usePathname } from "next/navigation"
import Link from "next/link"
import { useGlobalStore } from "@/store/global-store"
import { api } from "@/lib/api-client"
import {
  Activity,
  Layers,
  Terminal,
  ShieldAlert,
  Zap,
  LayoutDashboard,
  ChevronDown,
  LogOut,
  Menu,
  X,
  Gauge,
  UserCheck,
  RefreshCw,
  FileText,
  Database
} from "lucide-react"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const {
    user,
    organization,
    organizations,
    sidebarOpen,
    clearAuth,
    toggleSidebar,
    setOrganization,
    setOrganizations
  } = useGlobalStore()

  const [orgDropdownOpen, setOrgDropdownOpen] = useState(false)
  const [latency, setLatency] = useState<number | null>(null)
  const [dbStatus, setDbStatus] = useState<string>("connecting")
  const [redisStatus, setRedisStatus] = useState<string>("connecting")
  const [checkingHealth, setCheckingHealth] = useState(false)

  // 1. Authentication protection guard
  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null
    if (!token) {
      router.push("/login")
    }
  }, [router])

  // 2. Automated health and latency tracking
  const checkHealth = async () => {
    if (checkingHealth) return
    setCheckingHealth(true)
    const startTime = performance.now()
    try {
      const healthRes = await api.get<any>("/api/v1/health")
      const endTime = performance.now()
      setLatency(Math.round(endTime - startTime))
      setDbStatus(healthRes.services.database.status)
      setRedisStatus(healthRes.services.redis.status)
    } catch (err) {
      setLatency(null)
      setDbStatus("offline")
      setRedisStatus("offline")
    } finally {
      setCheckingHealth(false)
    }
  }

  useEffect(() => {
    checkHealth()
    const interval = setInterval(checkHealth, 15000) // Ping health check every 15s
    return () => clearInterval(interval)
  }, [])

  // 3. Sync memberships if organizations list is empty on mount
  useEffect(() => {
    const syncWorkspaces = async () => {
      try {
        const orgs = await api.get<any>("/api/v1/auth/organizations")
        setOrganizations(orgs)
      } catch (err) {
        console.error("Workspace synchronization failed:", err)
      }
    }
    if (user && organizations.length === 0) {
      syncWorkspaces()
    }
  }, [user, organizations, setOrganizations])

  const handleLogout = async () => {
    try {
      await api.post("/api/v1/auth/logout", {})
    } catch (e) {
      // Proceed with local clean anyway
    }
    clearAuth()
    router.push("/login")
  }

  // Get active role inside the currently selected workspace organization
  const activeRole = organizations.find((o) => o.organization.id === organization?.id)?.role || "viewer"

  const navLinks = [
    { name: "Analytics Console", path: "/dashboard/analytics", icon: Layers },
    { name: "Dashboard Builder", path: "/dashboard/builder", icon: LayoutDashboard },
    { name: "Alerts & Rules", path: "/dashboard/alerts", icon: ShieldAlert },
    { name: "Scheduled Reports", path: "/dashboard/reports", icon: FileText },
    { name: "Live Event Stream", path: "/dashboard/stream", icon: Terminal },
    { name: "SQL Sandbox", path: "/dashboard/sandbox", icon: Database },
    { name: "Developer Ingestion", path: "/dashboard/ingestion", icon: Zap },
  ]

  return (
    <div className="min-h-screen flex bg-[#0a0a0c] text-zinc-100 overflow-hidden">
      
      {/* ==========================================
          1. SIDEBAR SHELL
          ========================================== */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-zinc-950 border-r border-zinc-900 transition-all duration-300 transform md:relative md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="h-full flex flex-col justify-between p-4">
          <div className="space-y-6">
            
            {/* Header / Logo */}
            <div className="flex items-center justify-between border-b border-zinc-900 pb-4">
              <Link href="/dashboard/analytics" className="flex items-center gap-2.5">
                <div className="h-9 w-9 rounded-xl bg-purple-650 flex items-center justify-center text-white shadow-[0_4px_15px_rgba(124,58,237,0.3)]">
                  <Activity className="h-5 w-5 animate-pulse-slow" />
                </div>
                <div>
                  <span className="font-extrabold text-sm tracking-tight text-white block">Antigravity</span>
                  <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-bold">Analytics</span>
                </div>
              </Link>
              <button onClick={toggleSidebar} className="md:hidden p-1.5 hover:bg-zinc-900 rounded-lg text-zinc-400">
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Workspace switcher dropdown selector */}
            <div className="relative">
              <button
                onClick={() => setOrgDropdownOpen(!orgDropdownOpen)}
                className="w-full flex items-center justify-between p-3 bg-zinc-900/60 hover:bg-zinc-900 border border-zinc-850 hover:border-zinc-800 rounded-xl transition text-left group"
              >
                <div className="truncate">
                  <span className="text-[9px] uppercase tracking-wider font-bold text-purple-400 block mb-0.5">Active Workspace</span>
                  <span className="text-xs font-bold text-white block truncate">{organization?.name || "Select Org"}</span>
                </div>
                <ChevronDown className={`h-4 w-4 text-zinc-500 group-hover:text-zinc-400 transition-transform ${orgDropdownOpen ? "rotate-180" : ""}`} />
              </button>

              {orgDropdownOpen && (
                <div className="absolute top-full left-0 right-0 z-50 mt-2 bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl p-1.5 space-y-1 max-h-48 overflow-y-auto">
                  {organizations.map((membership) => (
                    <button
                      key={membership.organization.id}
                      onClick={() => {
                        setOrganization(membership.organization)
                        setOrgDropdownOpen(false)
                      }}
                      className={`w-full flex items-center justify-between p-2 rounded-lg text-xs font-medium transition ${
                        organization?.id === membership.organization.id
                          ? "bg-purple-650/15 text-purple-300 border border-purple-800/20"
                          : "text-zinc-400 hover:bg-zinc-800 hover:text-white"
                      }`}
                    >
                      <span className="truncate">{membership.organization.name}</span>
                      <span className="text-[9px] uppercase px-1.5 py-0.5 bg-zinc-800 rounded text-zinc-400 font-semibold">{membership.role}</span>
                    </button>
                  ))}
                  {organizations.length === 0 && (
                    <div className="p-3 text-center text-xs text-zinc-500 font-medium">No active organizations found.</div>
                  )}
                </div>
              )}
            </div>

            {/* Navigation links */}
            <nav className="space-y-1.5">
              {navLinks.map((link) => {
                const Icon = link.icon
                const isActive = pathname === link.path
                return (
                  <Link
                    key={link.path}
                    href={link.path}
                    className={`flex items-center gap-3 px-3 py-2.5 text-xs font-bold rounded-xl transition ${
                      isActive
                        ? "bg-purple-650 text-white shadow-[0_4px_15px_rgba(124,58,237,0.2)]"
                        : "text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200"
                    }`}
                  >
                    <Icon className={`h-4.5 w-4.5 ${isActive ? "text-white" : "text-zinc-400"}`} />
                    {link.name}
                  </Link>
                )
              })}
            </nav>
          </div>

          {/* Sidebar Footer context */}
          <div className="space-y-4 pt-4 border-t border-zinc-900">
            {/* User profile & Role representation */}
            {user && (
              <div className="flex items-center justify-between p-2 bg-zinc-900/30 rounded-xl border border-zinc-900">
                <div className="truncate pr-2">
                  <span className="text-[10px] text-zinc-500 block truncate">{user.email}</span>
                  <span className="text-[9px] uppercase tracking-wider font-bold text-zinc-400 flex items-center gap-1.5 mt-0.5">
                    <UserCheck className="h-3 w-3 text-purple-400 shrink-0" />
                    Role: {activeRole}
                  </span>
                </div>
                <button
                  onClick={handleLogout}
                  className="p-2 bg-zinc-900 hover:bg-zinc-850 hover:text-red-400 rounded-lg text-zinc-400 transition"
                  title="Sign Out"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            )}

            {/* Performance diagnostics badge */}
            <div className="flex items-center justify-between text-[10px] text-zinc-500 px-1 font-mono">
              <span className="flex items-center gap-1">
                <Gauge className="h-3.5 w-3.5" />
                System Latency:
              </span>
              <button 
                onClick={checkHealth}
                disabled={checkingHealth}
                className="hover:text-purple-400 flex items-center gap-1.5 transition"
              >
                {checkingHealth ? (
                  <RefreshCw className="h-3 w-3 animate-spin text-purple-500" />
                ) : (
                  <span className={latency !== null && latency < 50 ? "text-emerald-400 font-bold" : "text-amber-400"}>
                    {latency !== null ? `${latency}ms` : "Offline"}
                  </span>
                )}
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* ==========================================
          2. VIEWPORT CONTENT SHELL
          ========================================== */}
      <div className="flex-1 flex flex-col overflow-hidden">
        
        {/* Mobile Header bar */}
        <header className="md:hidden flex items-center justify-between p-4 bg-zinc-950 border-b border-zinc-900">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-purple-500" />
            <span className="font-extrabold text-sm text-white">Antigravity</span>
          </div>
          <button onClick={toggleSidebar} className="p-2 hover:bg-zinc-900 rounded-lg text-zinc-400">
            <Menu className="h-5 w-5" />
          </button>
        </header>

        {/* Dynamic viewport children body */}
        <main className="flex-1 overflow-y-auto p-4 md:p-8 relative">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>

    </div>
  )
}

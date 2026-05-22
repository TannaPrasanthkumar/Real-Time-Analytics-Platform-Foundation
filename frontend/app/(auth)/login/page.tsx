"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { api } from "@/lib/api-client"
import { useGlobalStore } from "@/store/global-store"
import { Loader2, Lock, Mail, ArrowRight, ShieldAlert, CheckCircle2 } from "lucide-react"

export default function LoginPage() {
  const router = useRouter()
  const { setAuth, setOrganizations } = useGlobalStore()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setErrorMsg(null)
    setSuccessMsg(null)

    if (!email || !password) {
      setErrorMsg("Please provide both email and password credentials.")
      setIsLoading(false)
      return
    }

    try {
      // 1. Perform Authentication Login Post
      const loginRes = await api.post<any>("/api/v1/auth/login", {
        email,
        password,
      })

      // 2. Set user authentication context in global store
      setAuth(loginRes.user, loginRes.access_token)
      setSuccessMsg("Credentials validated successfully. Syncing active workspaces...")

      // 3. Retrieve user organization memberships
      const orgsRes = await api.get<any>("/api/v1/auth/organizations", {
        headers: { Authorization: `Bearer ${loginRes.access_token}` },
      })
      setOrganizations(orgsRes)

      // 4. Redirect to SaaS Analytics Console
      setTimeout(() => {
        router.push("/dashboard/analytics")
      }, 800)
    } catch (err: any) {
      setIsLoading(false)
      setErrorMsg(err.message || "Authentication failed. Please verify credentials.")
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative">
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full bg-purple-600/10 blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 rounded-full bg-indigo-600/10 blur-[120px]" />
      </div>

      <div className="w-full max-w-md z-10">
        <div className="text-center mb-8">
          <div className="inline-flex p-3 rounded-2xl bg-purple-500/10 border border-purple-500/20 text-purple-400 mb-4 shadow-[0_0_15px_rgba(168,85,247,0.1)]">
            <Lock className="h-6 w-6" />
          </div>
          <h2 className="text-3xl font-extrabold tracking-tight text-white">
            Access <span className="gradient-text">Console</span>
          </h2>
          <p className="text-sm text-zinc-400 mt-2">
            Sign in to manage your real-time analytics dashboards.
          </p>
        </div>

        <div className="glassmorphism glow-border rounded-2xl p-8 relative overflow-hidden shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-6">
            {errorMsg && (
              <div className="p-3 bg-red-950/60 border border-red-800/50 rounded-xl flex items-start gap-2.5 text-xs text-red-400 animate-shake">
                <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{errorMsg}</span>
              </div>
            )}

            {successMsg && (
              <div className="p-3 bg-emerald-950/60 border border-emerald-800/50 rounded-xl flex items-start gap-2.5 text-xs text-emerald-400 animate-pulse">
                <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{successMsg}</span>
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="email" className="text-xs uppercase tracking-wider font-semibold text-zinc-400">
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-zinc-500" />
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full bg-zinc-950/80 border border-zinc-800 focus:border-purple-500 rounded-xl pl-10 pr-4 py-3 text-sm text-white placeholder-zinc-600 focus:ring-1 focus:ring-purple-500 outline-none transition duration-200"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="text-xs uppercase tracking-wider font-semibold text-zinc-400">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-zinc-500" />
                <input
                  type="password"
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full bg-zinc-950/80 border border-zinc-800 focus:border-purple-500 rounded-xl pl-10 pr-4 py-3 text-sm text-white placeholder-zinc-600 focus:ring-1 focus:ring-purple-500 outline-none transition duration-200"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-medium shadow-[0_4px_20px_rgba(124,58,237,0.3)] hover:shadow-[0_4px_25px_rgba(124,58,237,0.5)] transition duration-200 disabled:opacity-50"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Verifying...
                </>
              ) : (
                <>
                  Sign In
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center text-xs text-zinc-500">
            <span>Don&apos;t have a workspace yet? </span>
            <Link href="/signup" className="text-purple-400 hover:text-purple-300 font-semibold transition">
              Create one now
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

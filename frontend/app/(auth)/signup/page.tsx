"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { api } from "@/lib/api-client"
import { useGlobalStore } from "@/store/global-store"
import { Loader2, UserPlus, Mail, User, ShieldAlert, CheckCircle2, ArrowRight, Building } from "lucide-react"

export default function SignupPage() {
  const router = useRouter()
  const { setAuth, setOrganizations } = useGlobalStore()
  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [orgName, setOrgName] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setErrorMsg(null)
    setSuccessMsg(null)

    if (!fullName || !email || !password || !orgName) {
      setErrorMsg("Please fill out all the configuration fields.")
      setIsLoading(false)
      return
    }

    if (password.length < 8) {
      setErrorMsg("Password must be at least 8 characters long.")
      setIsLoading(false)
      return
    }

    try {
      // 1. Perform Signup POST
      const signupRes = await api.post<any>("/api/v1/auth/signup", {
        email,
        password,
        full_name: fullName,
        organization_name: orgName,
      })

      // 2. Set user credentials context in global store
      setAuth(signupRes.user, signupRes.access_token)
      setSuccessMsg("Account & Owner workspace provisioned! Loading dashboard...")

      // 3. Retrieve user organization memberships
      const orgsRes = await api.get<any>("/api/v1/auth/organizations", {
        headers: { Authorization: `Bearer ${signupRes.access_token}` },
      })
      setOrganizations(orgsRes)

      // 4. Redirect to SaaS Analytics Console
      setTimeout(() => {
        router.push("/dashboard/analytics")
      }, 800)
    } catch (err: any) {
      setIsLoading(false)
      setErrorMsg(err.message || "Registration failed. Please check input parameters.")
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 relative">
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full bg-purple-600/10 blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 rounded-full bg-indigo-600/10 blur-[120px]" />
      </div>

      <div className="w-full max-w-md z-10">
        <div className="text-center mb-8">
          <div className="inline-flex p-3 rounded-2xl bg-purple-500/10 border border-purple-500/20 text-purple-400 mb-4 shadow-[0_0_15px_rgba(168,85,247,0.1)]">
            <UserPlus className="h-6 w-6" />
          </div>
          <h2 className="text-3xl font-extrabold tracking-tight text-white">
            Register <span className="gradient-text">Workspace</span>
          </h2>
          <p className="text-sm text-zinc-400 mt-2">
            Create an owner account and spin up a dedicated analytics workspace.
          </p>
        </div>

        <div className="glassmorphism glow-border rounded-2xl p-8 relative overflow-hidden shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-4">
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

            <div className="space-y-1.5">
              <label htmlFor="fullName" className="text-xs uppercase tracking-wider font-semibold text-zinc-400">
                Full Name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-zinc-500" />
                <input
                  type="text"
                  id="fullName"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Miller"
                  className="w-full bg-zinc-950/80 border border-zinc-800 focus:border-purple-500 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-zinc-600 focus:ring-1 focus:ring-purple-500 outline-none transition duration-200"
                  required
                />
              </div>
            </div>

            <div className="space-y-1.5">
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
                  placeholder="jane.miller@company.com"
                  className="w-full bg-zinc-950/80 border border-zinc-800 focus:border-purple-500 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-zinc-600 focus:ring-1 focus:ring-purple-500 outline-none transition duration-200"
                  required
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="password" className="text-xs uppercase tracking-wider font-semibold text-zinc-400">
                Password (min 8 chars)
              </label>
              <div className="relative">
                <Building className="absolute left-3 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-zinc-500" />
                <input
                  type="password"
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full bg-zinc-950/80 border border-zinc-800 focus:border-purple-500 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-zinc-600 focus:ring-1 focus:ring-purple-500 outline-none transition duration-200"
                  required
                  minLength={8}
                />
              </div>
            </div>

            <div className="space-y-1.5 border-t border-zinc-850 pt-4 mt-2">
              <label htmlFor="orgName" className="text-xs uppercase tracking-wider font-semibold text-zinc-400 flex items-center gap-1.5">
                <Building className="h-3.5 w-3.5 text-purple-400" />
                Workspace / Organization Name
              </label>
              <input
                type="text"
                id="orgName"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="Acme Corp"
                className="w-full bg-zinc-950/80 border border-zinc-800 focus:border-purple-500 rounded-xl px-4 py-2.5 text-sm text-white placeholder-zinc-600 focus:ring-1 focus:ring-purple-500 outline-none transition duration-200"
                required
              />
              <span className="text-[10px] text-zinc-500 block">
                This provisions a unique workspace URL slug (e.g. acme-corp) to isolate database structures.
              </span>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-medium shadow-[0_4px_20px_rgba(124,58,237,0.3)] hover:shadow-[0_4px_25px_rgba(124,58,237,0.5)] transition duration-200 disabled:opacity-50 mt-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Provisioning...
                </>
              ) : (
                <>
                  Register & Provision
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center text-xs text-zinc-500">
            <span>Already have an account? </span>
            <Link href="/login" className="text-purple-400 hover:text-purple-300 font-semibold transition">
              Sign in here
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

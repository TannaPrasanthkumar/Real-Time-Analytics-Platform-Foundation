"use client"

import { useState, useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { api } from "@/lib/api-client"
import { useGlobalStore } from "@/store/global-store"
import { Loader2, Mail, Lock, User, ShieldAlert, CheckCircle2, UserCheck, LayoutDashboard } from "lucide-react"

interface InvitationDetails {
  id: string
  email: string
  organization_id: string
  role: string
  created_at: string
}

function InvitationAcceptorContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get("token")
  const { user: currentUser, isAuthenticated, setAuth, setOrganizations } = useGlobalStore()

  const [invitation, setInvitation] = useState<InvitationDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Register state for unauthenticated Scenario A
  const [fullName, setFullName] = useState("")
  const [password, setPassword] = useState("")

  useEffect(() => {
    if (!token) {
      setErrorMsg("Invitation token is missing. Please check your invitation link.")
      setLoading(false)
      return
    }

    const fetchInvitation = async () => {
      try {
        const details = await api.get<InvitationDetails>(`/api/v1/invitations/${token}`)
        setInvitation(details)
      } catch (err: any) {
        setErrorMsg(err.message || "Failed to retrieve invitation details. The token may be expired or invalid.")
      } finally {
        setLoading(false)
      }
    }

    fetchInvitation()
  }, [token])

  const handleAccept = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return

    setSubmitting(true)
    setErrorMsg(null)
    setSuccessMsg(null)

    // Build payload depending on auth state
    const payload: any = { token }
    
    // If not authenticated, we must provide registration details
    if (!isAuthenticated) {
      if (!fullName || !password) {
        setErrorMsg("Please fill out both name and password credentials.")
        setSubmitting(false)
        return
      }
      if (password.length < 8) {
        setErrorMsg("Password must be at least 8 characters long.")
        setSubmitting(false)
        return
      }
      payload.full_name = fullName
      payload.password = password
    }

    try {
      // 1. Post accept-invitation details
      const loginRes = await api.post<any>("/api/v1/invitations/accept", payload)

      // 2. Set user credentials in state
      setAuth(loginRes.user, loginRes.access_token)
      setSuccessMsg("Onboarding complete! Syncing workspace...")

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
      setSubmitting(false)
      setErrorMsg(err.message || "Failed to accept organization invitation.")
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
        <span className="text-sm text-zinc-400 font-medium">Validating invitation token...</span>
      </div>
    )
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
            <UserCheck className="h-6 w-6" />
          </div>
          <h2 className="text-3xl font-extrabold tracking-tight text-white">
            Accept <span className="gradient-text">Invitation</span>
          </h2>
          <p className="text-sm text-zinc-400 mt-2">
            You&apos;ve been invited to join an analytics workspace.
          </p>
        </div>

        <div className="glassmorphism glow-border rounded-2xl p-8 relative overflow-hidden shadow-2xl">
          {errorMsg && !invitation ? (
            <div className="space-y-4 text-center">
              <div className="p-3 bg-red-950/60 border border-red-800/50 rounded-xl flex items-start gap-2.5 text-xs text-red-400">
                <ShieldAlert className="h-5 w-5 shrink-0" />
                <span>{errorMsg}</span>
              </div>
              <button
                onClick={() => router.push("/login")}
                className="w-full py-2.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-sm text-white font-medium rounded-xl transition"
              >
                Return to Login
              </button>
            </div>
          ) : (
            <form onSubmit={handleAccept} className="space-y-5">
              {errorMsg && (
                <div className="p-3 bg-red-950/60 border border-red-800/50 rounded-xl flex items-start gap-2.5 text-xs text-red-400">
                  <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {successMsg && (
                <div className="p-3 bg-emerald-950/60 border border-emerald-800/50 rounded-xl flex items-start gap-2.5 text-xs text-emerald-400">
                  <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{successMsg}</span>
                </div>
              )}

              {/* Workspace summary panel */}
              {invitation && (
                <div className="p-4 bg-purple-500/5 border border-purple-500/10 rounded-xl space-y-1">
                  <div className="text-[10px] uppercase font-bold tracking-wider text-purple-400">Target Workspace</div>
                  <div className="text-base font-extrabold text-white">Join Organization</div>
                  <div className="text-xs text-zinc-400 flex items-center gap-2 mt-1">
                    <span>Role: <strong className="text-zinc-200 capitalize">{invitation.role}</strong></span>
                    <span>•</span>
                    <span>For: <strong className="text-zinc-200">{invitation.email}</strong></span>
                  </div>
                </div>
              )}

              {isAuthenticated && currentUser ? (
                /* Scenario B: Authenticated - Single-click accept */
                <div className="space-y-4 pt-2">
                  <div className="text-xs text-zinc-400 text-center">
                    You are currently logged in as <strong className="text-zinc-200">{currentUser.email}</strong>.
                  </div>
                  
                  {currentUser.email.toLowerCase() !== invitation?.email.toLowerCase() ? (
                    <div className="p-3 bg-amber-950/40 border border-amber-800/40 rounded-xl text-[11px] text-amber-400">
                      <strong>Caution:</strong> Your logged-in email doesn&apos;t match the invitation email ({invitation?.email}). You must logout and use the correct email to join.
                    </div>
                  ) : (
                    <button
                      type="submit"
                      disabled={submitting}
                      className="w-full flex items-center justify-center gap-2 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-medium shadow-[0_4px_20px_rgba(124,58,237,0.3)] transition"
                    >
                      {submitting ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Joining Workspace...
                        </>
                      ) : (
                        <>
                          Join Workspace Now
                          <LayoutDashboard className="h-4 w-4" />
                        </>
                      )}
                    </button>
                  )}
                  
                  <div className="text-center">
                    <button
                      type="button"
                      onClick={() => {
                        useGlobalStore.getState().clearAuth()
                        router.refresh()
                      }}
                      className="text-xs text-zinc-500 hover:text-zinc-400 underline"
                    >
                      Sign in with a different account
                    </button>
                  </div>
                </div>
              ) : (
                /* Scenario A: Unauthenticated - Account registration form */
                <div className="space-y-4 pt-2">
                  <div className="text-xs text-zinc-400 mb-2">
                    Create your account profile credentials to complete joining this organization.
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs uppercase tracking-wider font-semibold text-zinc-400">Email Address</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-zinc-650" />
                      <input
                        type="email"
                        value={invitation?.email || ""}
                        disabled
                        className="w-full bg-zinc-900/50 border border-zinc-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-zinc-500 cursor-not-allowed outline-none"
                      />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label htmlFor="fullName" className="text-xs uppercase tracking-wider font-semibold text-zinc-400">Full Name</label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-zinc-500" />
                      <input
                        type="text"
                        id="fullName"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="Jane Miller"
                        className="w-full bg-zinc-950/80 border border-zinc-800 focus:border-purple-500 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white outline-none focus:ring-1 focus:ring-purple-500 transition duration-200"
                        required
                      />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label htmlFor="password" className="text-xs uppercase tracking-wider font-semibold text-zinc-400">Password (min 8 chars)</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-zinc-500" />
                      <input
                        type="password"
                        id="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••••••"
                        className="w-full bg-zinc-950/80 border border-zinc-800 focus:border-purple-500 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white outline-none focus:ring-1 focus:ring-purple-500 transition duration-200"
                        required
                        minLength={8}
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full flex items-center justify-center gap-2 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-medium shadow-[0_4px_20px_rgba(124,58,237,0.3)] transition mt-2"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Completing Registration...
                      </>
                    ) : (
                      <>
                        Register & Accept Invitation
                        <UserCheck className="h-4 w-4" />
                      </>
                    )}
                  </button>
                </div>
              )}
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex flex-col items-center justify-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
        <span className="text-sm text-zinc-400 font-medium">Bootstrapping invitation module...</span>
      </div>
    }>
      <InvitationAcceptorContent />
    </Suspense>
  )
}

"use client"

import { useEffect, useState } from "react"
import { useGlobalStore } from "@/store/global-store"
import { api } from "@/lib/api-client"
import {
  Zap,
  Key,
  RotateCw,
  Trash2,
  Plus,
  Copy,
  Check,
  UploadCloud,
  FileSpreadsheet,
  Terminal,
  ShieldAlert,
  Loader2,
  CheckCircle2,
  HelpCircle,
  Code,
  Lock,
  RefreshCw,
  Info
} from "lucide-react"

interface APIKey {
  id: string
  name: string
  prefix: string
  is_active: boolean
  created_at: string
}

interface APIKeyCreated {
  id: string
  name: string
  api_key: string
  prefix: string
  created_at: string
}

interface DataSource {
  id: string
  name: string
  type: string
  is_active: boolean
}

export default function IngestionPage() {
  const { organization, organizations } = useGlobalStore()

  // Resolve active role clearances
  const activeRole = organizations.find((o) => o.organization.id === organization?.id)?.role || "viewer"
  const isAdminOrOwner = activeRole === "admin" || activeRole === "owner"
  const isAnalyst = activeRole === "analyst" || isAdminOrOwner
  const isReadOnlyViewer = activeRole === "viewer"

  // Ingestion API Keys states
  const [apiKeys, setApiKeys] = useState<APIKey[]>([])
  const [loadingKeys, setLoadingKeys] = useState(false)
  const [newKeyName, setNewKeyName] = useState("")
  const [submittingKey, setSubmittingKey] = useState(false)
  const [lastCreatedKey, setLastCreatedKey] = useState<APIKeyCreated | null>(null)
  const [copiedKeyText, setCopiedKeyText] = useState(false)

  // CSV Ingestion states
  const [dataSources, setDataSources] = useState<DataSource[]>([])
  const [loadingSources, setLoadingSources] = useState(false)
  const [selectedSourceId, setSelectedSourceId] = useState<string>("")
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [uploadingCsv, setUploadingCsv] = useState(false)
  const [uploadResult, setUploadResult] = useState<any>(null)

  // Sync / Refresh Key list
  const fetchAPIKeys = async () => {
    if (!organization || !isAdminOrOwner) return
    setLoadingKeys(true)
    try {
      const keys = await api.get<APIKey[]>(
        `/api/v1/organizations/${organization.id}/api-keys`
      )
      setApiKeys(keys)
    } catch (err) {
      console.error("Failed to load API keys:", err)
    } finally {
      setLoadingKeys(false)
    }
  }

  // Sync / Refresh Data Sources
  const fetchDataSources = async () => {
    if (!organization || !isAnalyst) return
    setLoadingSources(true)
    try {
      const sources = await api.get<DataSource[]>(
        `/api/v1/organizations/${organization.id}/data-sources`
      )
      setDataSources(sources)
      
      // Auto select the first CSV source or any source
      if (sources.length > 0) {
        const csvSource = sources.find((s) => s.type === "csv") || sources[0]
        setSelectedSourceId(csvSource.id)
      }
    } catch (err) {
      console.error("Failed to load data sources:", err)
    } finally {
      setLoadingSources(false)
    }
  }

  useEffect(() => {
    if (organization) {
      fetchAPIKeys()
      fetchDataSources()
    }
  }, [organization])

  // Create API Key
  const handleGenerateKey = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!organization || !isAdminOrOwner || !newKeyName.trim()) return
    setSubmittingKey(true)
    setLastCreatedKey(null)
    try {
      const res = await api.post<APIKeyCreated>(
        `/api/v1/organizations/${organization.id}/api-keys`,
        { name: newKeyName }
      )
      setNewKeyName("")
      setLastCreatedKey(res)
      await fetchAPIKeys()
    } catch (err) {
      console.error("Key generation failed:", err)
    } finally {
      setSubmittingKey(false)
    }
  }

  // Revoke Key
  const handleRevokeKey = async (keyId: string) => {
    if (!organization || !isAdminOrOwner) return
    if (!confirm("Are you sure you want to revoke this API key? Systems utilizing this key will be instantly blocked from ingestion.")) return
    try {
      await api.delete(
        `/api/v1/organizations/${organization.id}/api-keys/${keyId}`
      )
      await fetchAPIKeys()
    } catch (err) {
      console.error("Failed to revoke key:", err)
    }
  }

  // Rotate Key
  const handleRotateKey = async (keyId: string) => {
    if (!organization || !isAdminOrOwner) return
    if (!confirm("Are you sure you want to rotate this key? A new API key will be generated and the old one revoked immediately.")) return
    setLoadingKeys(true)
    setLastCreatedKey(null)
    try {
      const res = await api.post<APIKeyCreated>(
        `/api/v1/organizations/${organization.id}/api-keys/${keyId}/rotate`,
        {}
      )
      setLastCreatedKey(res)
      await fetchAPIKeys()
    } catch (err) {
      console.error("Key rotation failed:", err)
    } finally {
      setLoadingKeys(false)
    }
  }

  // Provision CSV Source dynamically if none exists
  const handleCreateCSVSource = async () => {
    if (!organization || !isAnalyst) return
    setLoadingSources(true)
    try {
      const res = await api.post<DataSource>(
        `/api/v1/organizations/${organization.id}/data-sources`,
        {
          name: "Default CSV Ingress Source",
          type: "csv"
        }
      )
      setDataSources((prev) => [...prev, res])
      setSelectedSourceId(res.id)
    } catch (err) {
      console.error("Failed to provision default CSV source:", err)
    } finally {
      setLoadingSources(false)
    }
  }

  // CSV Drag and drop file select
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setCsvFile(e.target.files[0])
      setUploadResult(null)
    }
  }

  // CSV Upload action
  const handleUploadCSV = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!organization || !isAnalyst || !csvFile || !selectedSourceId) return
    setUploadingCsv(true)
    setUploadResult(null)

    // Build Form Data payload
    const formData = new FormData()
    formData.append("file", csvFile)

    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null

    try {
      // Direct raw post for multipart upload
      const response = await fetch(
        `http://localhost:8000/api/v1/organizations/${organization.id}/data-sources/${selectedSourceId}/upload-csv`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`
          },
          body: formData
        }
      )
      if (!response.ok) {
        throw new Error("CSV Upload failed. Verify syntax formats.")
      }
      const data = await response.json()
      setUploadResult(data)
      setCsvFile(null)
    } catch (err: any) {
      console.error("CSV ingestion uploader failed:", err)
      setUploadResult({ error: err.message || "Failed to parse CSV columns." })
    } finally {
      setUploadingCsv(false)
    }
  }

  const copyKeyToClipboard = () => {
    if (!lastCreatedKey) return
    navigator.clipboard.writeText(lastCreatedKey.api_key)
    setCopiedKeyText(true)
    setTimeout(() => setCopiedKeyText(false), 2000)
  }

  const apiSampleCode = `curl -X POST "http://localhost:8000/api/v1/ingest" \\
  -H "X-API-Key: ${lastCreatedKey?.api_key || "your_api_key_here"}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "event_type": "page_view",
    "url": "https://acme.org/pricing",
    "referrer": "https://google.com",
    "payload": {
      "browser": "Chrome",
      "os": "Windows",
      "country": "US",
      "source": "organic"
    }
  }'`

  return (
    <div className="space-y-8">
      
      {/* 1. HEADER */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-900 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-purple-500 animate-pulse shadow-[0_0_8px_#a855f7]" />
            <span className="text-[10px] uppercase tracking-widest text-purple-400 font-bold">Ingress Console</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight mt-1 text-white">
            Developer <span className="gradient-text">Ingestion</span>
          </h1>
          <p className="text-zinc-400 text-xs mt-1">
            Generate secure client API tokens, view webhook endpoints, and manually queue raw CSV events telemetry.
          </p>
        </div>
      </header>

      {/* Global Viewer Warning */}
      {isReadOnlyViewer && (
        <div className="flex items-center gap-2.5 px-4 py-3 bg-zinc-950/80 border border-zinc-900 rounded-xl text-zinc-400 text-xs">
          <Lock className="h-4 w-4 text-purple-400 shrink-0" />
          <span>Ingress Developer features are locked for <strong>Viewer</strong> role. Ask workspace admin to manage API keys.</span>
        </div>
      )}

      {/* 2. MAIN SPLIT GRID: Keys & CSV Upload */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* ==========================================
            A. API KEYS MANAGEMENT PANEL (Restricted)
            ========================================== */}
        <section className="glassmorphism glow-border rounded-2xl p-6 flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Key className="h-4.5 w-4.5 text-purple-400" />
              Ingestion API Tokens
            </h2>
            <p className="text-xs text-zinc-450 leading-relaxed">
              API Keys authenticate third-party servers submitting analytic payloads. Safeguard these tokens securely.
            </p>

            {!isAdminOrOwner ? (
              <div className="p-5 bg-zinc-950/80 border border-zinc-900 rounded-xl flex items-start gap-3">
                <ShieldAlert className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <span className="text-xs font-bold text-white block">RBAC Restricted Clearances</span>
                  <span className="text-[11px] text-zinc-500 block leading-relaxed">
                    API key credentials management (rotation, creation, revocation) is locked for standard Analysts and Viewers. Only Owners and Administrators have credentials control access.
                  </span>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                
                {/* Create Key Form */}
                <form onSubmit={handleGenerateKey} className="flex gap-2">
                  <input
                    type="text"
                    required
                    disabled={submittingKey}
                    placeholder="e.g. server-production-key"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    className="flex-1 bg-zinc-950 border border-zinc-850 focus:border-purple-550 rounded-xl px-3.5 py-2.5 text-xs outline-none transition text-white placeholder-zinc-650"
                  />
                  <button
                    type="submit"
                    disabled={submittingKey}
                    className="flex items-center gap-1 px-4 py-2.5 bg-purple-650 hover:bg-purple-600 transition rounded-xl text-xs font-bold text-white shadow-[0_4px_12px_rgba(124,58,237,0.2)] disabled:opacity-50"
                  >
                    {submittingKey ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        <Plus className="h-4 w-4" />
                        Generate
                      </>
                    )}
                  </button>
                </form>

                {/* Display newly created key (Plaintext once!) */}
                {lastCreatedKey && (
                  <div className="p-4 bg-purple-950/20 border border-purple-500/15 rounded-xl space-y-2 animate-fadeIn relative">
                    <div className="flex items-center justify-between border-b border-purple-850/40 pb-2">
                      <span className="text-[10px] uppercase font-bold text-purple-400 flex items-center gap-1">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Credentials Created Successfully
                      </span>
                      <button 
                        onClick={() => setLastCreatedKey(null)}
                        className="text-[10px] text-zinc-500 hover:text-zinc-300 font-bold"
                      >
                        Dismiss
                      </button>
                    </div>
                    <span className="text-[10px] text-zinc-400 block leading-relaxed">
                      Copy this key. For security, we will only display this full credentials token <strong>once</strong>.
                    </span>
                    <div className="flex items-center justify-between gap-3 p-3 bg-zinc-950 rounded-lg border border-zinc-900 font-mono text-xs">
                      <span className="text-white truncate pr-2 select-all">{lastCreatedKey.api_key}</span>
                      <button
                        onClick={copyKeyToClipboard}
                        className="p-1.5 bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 text-zinc-400 hover:text-white rounded transition shrink-0"
                        title="Copy Key"
                      >
                        {copiedKeyText ? <Check className="h-3.5 w-3.5 text-emerald-450" /> : <Copy className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                  </div>
                )}

                {/* Key Listing Table */}
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between text-[10px] text-zinc-500 font-bold uppercase tracking-wider px-1">
                    <span>Active Keys list</span>
                    <button 
                      onClick={fetchAPIKeys} 
                      disabled={loadingKeys}
                      className="hover:text-purple-400 flex items-center gap-1 transition"
                    >
                      <RefreshCw className={`h-3 w-3 ${loadingKeys ? "animate-spin text-purple-500" : ""}`} />
                      Refresh
                    </button>
                  </div>

                  {loadingKeys ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin text-purple-500" />
                    </div>
                  ) : apiKeys.length === 0 ? (
                    <div className="text-center py-10 bg-zinc-955/30 border border-zinc-900 rounded-xl text-zinc-550 text-xs font-medium">
                      No active API keys found.
                    </div>
                  ) : (
                    <div className="bg-zinc-955/50 border border-zinc-900 rounded-xl divide-y divide-zinc-900 max-h-56 overflow-y-auto">
                      {apiKeys.map((key) => (
                        <div key={key.id} className="p-3.5 flex items-center justify-between gap-3 text-xs">
                          <div className="truncate">
                            <span className="text-white font-bold block truncate">{key.name}</span>
                            <span className="text-[10px] text-zinc-500 block font-mono mt-0.5">
                              Prefix: <strong className="text-zinc-400">{key.prefix}</strong> • Created: {new Date(key.created_at).toLocaleDateString()}
                            </span>
                          </div>

                          <div className="flex items-center gap-1.5 shrink-0">
                            <button
                              onClick={() => handleRotateKey(key.id)}
                              className="p-1.5 bg-zinc-900 border border-zinc-850 hover:bg-zinc-800 hover:text-purple-400 text-zinc-500 rounded-lg transition"
                              title="Rotate Key"
                            >
                              <RotateCw className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => handleRevokeKey(key.id)}
                              className="p-1.5 bg-zinc-900 border border-zinc-850 hover:bg-red-950/20 hover:border-red-900/30 hover:text-red-400 text-zinc-500 rounded-lg transition"
                              title="Revoke Key"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="text-[10px] text-zinc-500 font-mono border-t border-zinc-900/40 pt-4 mt-2">
            <span>Timing-attack resilient hash validation • SHA-256</span>
          </div>
        </section>

        {/* ==========================================
            B. CSV FILE EVENT UPLOADER SECTION
            ========================================== */}
        <section className="glassmorphism glow-border rounded-2xl p-6 flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <FileSpreadsheet className="h-4.5 w-4.5 text-indigo-400" />
              CSV Event log uploader
            </h2>
            <p className="text-xs text-zinc-450 leading-relaxed">
              Upload event records formatted in standard uploader CSV. Ideal for mock backfilling or data synchronization tasks.
            </p>

            {isReadOnlyViewer ? (
              <div className="p-5 bg-zinc-950/80 border border-zinc-900 rounded-xl flex items-start gap-3">
                <ShieldAlert className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <span className="text-xs font-bold text-white block">Ingress Restricted</span>
                  <span className="text-[11px] text-zinc-500 block leading-relaxed">
                    Viewers are blocked from manually backfilling or uploading events. Please consult an analyst or administrator to submit logs.
                  </span>
                </div>
              </div>
            ) : dataSources.length === 0 ? (
              /* No CSV Data Source found */
              <div className="p-6 bg-zinc-950 border border-zinc-900 rounded-xl text-center space-y-4">
                <span className="text-zinc-500 text-xs block leading-relaxed">
                  Before uploading CSV logs, we must provision a dedicated &quot;CSV Data Source&quot; inside the workspace database.
                </span>
                <button
                  onClick={handleCreateCSVSource}
                  disabled={loadingSources}
                  className="px-4 py-2 bg-indigo-650/15 hover:bg-indigo-650/25 border border-indigo-500/10 text-indigo-400 text-xs font-bold rounded-xl transition"
                >
                  {loadingSources ? "Provisioning..." : "Provision CSV Ingress Source"}
                </button>
              </div>
            ) : (
              /* Drag and Drop Uploader */
              <form onSubmit={handleUploadCSV} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Target Ingestion Source</label>
                  <select
                    value={selectedSourceId}
                    onChange={(e) => setSelectedSourceId(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-850 rounded-xl text-xs font-bold text-zinc-350 px-3.5 py-2.5 outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                    {dataSources.map((ds) => (
                      <option key={ds.id} value={ds.id}>
                        {ds.name} ({ds.type})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="relative border-2 border-dashed border-zinc-850 hover:border-indigo-550/40 bg-zinc-955/30 hover:bg-zinc-950/20 rounded-2xl transition duration-200 cursor-pointer">
                  <input
                    type="file"
                    required
                    accept=".csv"
                    onChange={handleFileChange}
                    className="absolute inset-0 z-10 w-full h-full opacity-0 cursor-pointer"
                  />
                  <div className="p-8 text-center flex flex-col items-center justify-center gap-2">
                    <UploadCloud className="h-8 w-8 text-indigo-400 animate-pulse-slow" />
                    <span className="text-xs font-bold text-white">
                      {csvFile ? csvFile.name : "Select or Drop Event Log CSV"}
                    </span>
                    <span className="text-[10px] text-zinc-500">
                      {csvFile ? `${(csvFile.size / 1024).toFixed(1)} KB` : "Max file size: 5MB • Formats: *.csv"}
                    </span>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={uploadingCsv || !csvFile}
                  className="w-full py-2.5 bg-indigo-650 hover:bg-indigo-600 transition rounded-xl text-xs font-bold text-white shadow-[0_4px_12px_rgba(99,102,241,0.2)] disabled:opacity-50 flex items-center justify-center gap-1.5"
                >
                  {uploadingCsv ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Queuing parsed database partitions...
                    </>
                  ) : (
                    <>
                      <FileSpreadsheet className="h-4.5 w-4.5" />
                      Ingest Event CSV
                    </>
                  )}
                </button>
              </form>
            )}

            {/* CSV Uploader results */}
            {uploadResult && (
              <div className={`p-4 rounded-xl text-xs space-y-1.5 animate-fadeIn ${
                uploadResult.error 
                  ? "bg-red-950/15 border border-red-900/25 text-red-300"
                  : "bg-emerald-950/15 border border-emerald-900/25 text-emerald-350"
              }`}>
                <span className="font-bold flex items-center gap-1.5">
                  <CheckCircle2 className={`h-4 w-4 ${uploadResult.error ? "text-red-400" : "text-emerald-400"}`} />
                  {uploadResult.error ? "Ingestion Failed" : "CSV Ingestion Succeeded"}
                </span>
                <span className="block text-[11px] leading-relaxed">
                  {uploadResult.error 
                    ? uploadResult.error 
                    : `Queued job. Parsed and batch-queued ${uploadResult.events_count} event records directly into db partitions.`}
                </span>
              </div>
            )}
          </div>

          <div className="text-[10px] text-zinc-500 font-mono border-t border-zinc-900/40 pt-4 mt-2 flex items-center justify-between">
            <span>Celery background bulk partition insert</span>
            <span className="text-purple-400 flex items-center gap-1 font-bold">
              <span className="h-1.5 w-1.5 rounded-full bg-purple-500 animate-pulse" />
              FastAPI queue
            </span>
          </div>
        </section>

      </div>

      {/* ==========================================
          3. DEVELOPER REST API WEBHOOK DOCUMENTATION
          ========================================== */}
      <section className="glassmorphism glow-border rounded-2xl p-6 space-y-5">
        <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Terminal className="h-4.5 w-4.5 text-indigo-400" />
            Webhook integration payload documentation
          </h2>
          <span className="text-[9px] uppercase bg-zinc-900 rounded px-2.5 py-1 text-zinc-400 font-bold border border-zinc-800">
            HTTP POST Ingest
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          <div className="lg:col-span-1 space-y-3.5">
            <div className="flex items-center gap-2">
              <Code className="h-4 w-4 text-purple-400" />
              <span className="text-xs font-bold text-white">X-API-Key Ingress Authorization</span>
            </div>
            <p className="text-[11px] text-zinc-450 leading-relaxed">
              Incorporate our unified endpoint inside your applications. Set the secure X-API-Key header and POST standard JSON payloads.
            </p>
            
            <div className="p-4 bg-zinc-950 border border-zinc-900 rounded-xl space-y-2">
              <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Ingestion Ingress link</span>
              <span className="text-xs text-indigo-400 font-mono truncate block">
                http://localhost:8000/api/v1/ingest
              </span>
            </div>

            <div className="p-4 bg-zinc-950 border border-zinc-900 rounded-xl flex items-start gap-2.5">
              <Info className="h-4.5 w-4.5 text-purple-400 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <span className="text-[10px] font-bold text-zinc-400 block uppercase">Sliding Rate Limits</span>
                <span className="text-[10px] text-zinc-550 block leading-relaxed">
                  Keys are bound to a Redis sliding rate limits bucket (100 requests / minute) to guarantee SLA bounds.
                </span>
              </div>
            </div>
          </div>

          <div className="lg:col-span-2 space-y-2">
            <span className="text-[10px] uppercase font-bold text-zinc-550 block">Ingestion Shell Script Sample</span>
            <div className="bg-zinc-950 border border-zinc-900 rounded-xl p-4 overflow-x-auto text-[11px] font-mono text-zinc-300 leading-relaxed shadow-inner">
              <pre>{apiSampleCode}</pre>
            </div>
          </div>
        </div>
      </section>

    </div>
  )
}

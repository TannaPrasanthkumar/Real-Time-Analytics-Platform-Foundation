"use client"

import { useEffect, useState } from "react"
import { useGlobalStore } from "@/store/global-store"
import { api } from "@/lib/api-client"
import {
  Database,
  Play,
  Loader2,
  RefreshCw,
  AlertTriangle,
  Table,
  ChevronDown,
  ChevronRight,
  Info,
  Clock,
  Lock,
  Cpu,
  Layers,
  Network,
  Trash2,
  ListFilter,
  CheckCircle2,
  FileCode,
  Search
} from "lucide-react"

// Types matching Backend Sandbox Pydantic schemas
interface SchemaColumn {
  name: string
  data_type: string
}

interface SchemaTable {
  table_name: string
  columns: SchemaColumn[]
}

interface SchemaResponse {
  tables: SchemaTable[]
}

interface QueryPlanNode {
  "Node Type": string
  "Relation Name"?: string
  "Alias"?: string
  "Startup Cost"?: number
  "Total Cost"?: number
  "Plan Rows"?: number
  "Plan Width"?: number
  "Actual Startup Time"?: number
  "Actual Total Time"?: number
  "Actual Rows"?: number
  "Actual Loops"?: number
  "Filter"?: string
  "Index Name"?: string
  "Join Type"?: string
  "Plans"?: QueryPlanNode[]
}

interface QueryPlanRoot {
  Plan: QueryPlanNode
  "Planning Time"?: number
  "Execution Time"?: number
}

interface SandboxQueryResponse {
  success: boolean
  columns: string[]
  rows: Record<string, any>[]
  execution_time_ms: number
  explain_plan: QueryPlanRoot[] | null
  error: string | null
}

export default function SQLSandboxPage() {
  const { organization, organizations } = useGlobalStore()

  // RBAC Access Control Check
  const activeRole = organizations.find((o) => o.organization.id === organization?.id)?.role || "viewer"
  const isAuthorized = activeRole === "owner" || activeRole === "admin" || activeRole === "analyst"

  // Schema State
  const [schema, setSchema] = useState<SchemaTable[]>([])
  const [schemaLoading, setSchemaLoading] = useState(false)
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({})
  const [schemaSearch, setSchemaSearch] = useState("")

  // Query Execution State
  const [sqlQuery, setSqlQuery] = useState<string>(
    "-- SQL Sandbox Playground\n-- Write SELECT queries on events or users tables\nSELECT \n  event_name,\n  count(*) as event_count\nFROM events \nGROUP BY event_name\nORDER BY event_count DESC;"
  )
  const [queryExecuting, setQueryExecuting] = useState(false)
  const [queryResponse, setQueryResponse] = useState<SandboxQueryResponse | null>(null)
  
  // Tabs for Results Panel
  const [activeTab, setActiveTab] = useState<"results" | "plan">("results")

  // Load Database Schema metadata definitions
  const fetchSchemaMetadata = async () => {
    if (!organization || !isAuthorized) return
    setSchemaLoading(true)
    try {
      const data = await api.get<SchemaResponse>(
        `/api/v1/organizations/${organization.id}/sandbox/schema`
      )
      setSchema(data.tables || [])
      // Expand the first table by default if available
      if (data.tables && data.tables.length > 0) {
        setExpandedTables({ [data.tables[0].table_name]: true })
      }
    } catch (err) {
      console.error("Failed to load schema layout explorer:", err)
    } finally {
      setSchemaLoading(false)
    }
  }

  useEffect(() => {
    if (organization) {
      fetchSchemaMetadata()
      setQueryResponse(null)
    }
  }, [organization, activeRole])

  const toggleTableExpand = (tableName: string) => {
    setExpandedTables((prev) => ({
      ...prev,
      [tableName]: !prev[tableName]
    }))
  }

  // Execute Sandbox Query
  const handleExecuteQuery = async (explain: boolean) => {
    if (!organization || !isAuthorized || queryExecuting) return
    setQueryExecuting(true)
    setQueryResponse(null)
    try {
      const payload = {
        sql: sqlQuery,
        explain: explain
      }
      const data = await api.post<SandboxQueryResponse>(
        `/api/v1/organizations/${organization.id}/sandbox/query`,
        payload
      )
      setQueryResponse(data)
      
      // If query was successful and explain = true, auto-switch to performance plan tab
      if (data.success && explain) {
        setActiveTab("plan")
      } else {
        setActiveTab("results")
      }
    } catch (err) {
      console.error("Failed to run sandbox custom query:", err)
      setQueryResponse({
        success: false,
        columns: [],
        rows: [],
        execution_time_ms: 0.0,
        explain_plan: null,
        error: err instanceof Error ? err.message : String(err)
      })
    } finally {
      setQueryExecuting(false)
    }
  }

  // Helper to color code Node Types inside query execution visualizers
  const getNodeColor = (nodeType: string) => {
    const type = nodeType.toLowerCase()
    if (type.includes("scan")) return "text-emerald-400 bg-emerald-950/20 border-emerald-900/30"
    if (type.includes("join")) return "text-blue-400 bg-blue-950/20 border-blue-900/30"
    if (type.includes("sort")) return "text-amber-400 bg-amber-950/20 border-amber-900/30"
    if (type.includes("aggregate") || type.includes("group") || type.includes("uniq")) {
      return "text-purple-400 bg-purple-950/20 border-purple-900/30"
    }
    return "text-indigo-400 bg-indigo-950/20 border-indigo-900/30"
  }

  // Recursive Plan Node Renderer Component
  const PlanNodeTree = ({ node, level = 0 }: { node: QueryPlanNode; level: number }) => {
    const isLeaf = !node.Plans || node.Plans.length === 0
    const colorClasses = getNodeColor(node["Node Type"])

    return (
      <div className="flex flex-col relative pl-6 border-l border-zinc-800/80 my-2">
        {/* Connection Line indicator */}
        <div className="absolute top-4 left-0 w-4 border-t border-zinc-800/80" />
        
        <div className="flex flex-col md:flex-row md:items-start gap-4 p-4 bg-zinc-950/40 rounded-xl border border-zinc-900 shadow-sm relative group hover:border-zinc-800 transition">
          {/* Main Node Identity Card */}
          <div className="space-y-1.5 flex-1 min-w-[200px]">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`px-2.5 py-0.5 rounded-lg text-[10px] font-bold border uppercase tracking-wider ${colorClasses}`}>
                {node["Node Type"]}
              </span>
              
              {node["Relation Name"] && (
                <span className="text-[11px] font-mono font-bold text-zinc-350 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-850">
                  on {node["Relation Name"]} {node["Alias"] ? `as ${node["Alias"]}` : ""}
                </span>
              )}

              {node["Index Name"] && (
                <span className="text-[11px] font-mono text-purple-400 bg-purple-950/15 px-1.5 py-0.5 rounded border border-purple-900/20">
                  using {node["Index Name"]}
                </span>
              )}
            </div>

            {node["Filter"] && (
              <div className="text-[10px] font-mono text-amber-500/90 leading-tight bg-amber-950/5 p-1.5 rounded border border-amber-950/15">
                <span className="font-bold uppercase tracking-wider text-[8px] block text-amber-550 mb-0.5">Filter Condition:</span>
                {node["Filter"]}
              </div>
            )}
          </div>

          {/* Quick Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-zinc-950/80 border border-zinc-900 p-2.5 rounded-xl text-[10px] font-mono font-bold text-zinc-450 shrink-0">
            <div>
              <span className="text-zinc-650 block text-[9px] uppercase tracking-wider mb-0.5">Cost</span>
              <span className="text-zinc-200">
                {node["Startup Cost"]} .. {node["Total Cost"]}
              </span>
            </div>
            <div>
              <span className="text-zinc-650 block text-[9px] uppercase tracking-wider mb-0.5">Plan Rows</span>
              <span className="text-zinc-200">{node["Plan Rows"]}</span>
            </div>
            {node["Actual Rows"] !== undefined && (
              <div>
                <span className="text-emerald-500/70 block text-[9px] uppercase tracking-wider mb-0.5">Act Rows</span>
                <span className="text-emerald-400 font-bold">{node["Actual Rows"]}</span>
              </div>
            )}
            {node["Actual Total Time"] !== undefined && (
              <div>
                <span className="text-indigo-400/80 block text-[9px] uppercase tracking-wider mb-0.5">Duration</span>
                <span className="text-indigo-400 font-bold">{node["Actual Total Time"]} ms</span>
              </div>
            )}
          </div>
        </div>

        {/* Recursive Children Plan execution mapping */}
        {node.Plans && node.Plans.map((child, idx) => (
          <PlanNodeTree key={idx} node={child} level={level + 1} />
        ))}
      </div>
    )
  }

  // Access Denied Screen for Viewers
  if (!isAuthorized) {
    return (
      <div className="space-y-8 max-w-5xl mx-auto">
        <header className="border-b border-zinc-900 pb-6">
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            SQL Query <span className="gradient-text">Sandbox</span>
          </h1>
          <p className="text-zinc-400 text-xs mt-1">
            Analyze time-series structures and execute real-time performance inspection queries securely on databases.
          </p>
        </header>

        <div className="relative py-24 px-8 bg-zinc-950/40 border border-zinc-900 rounded-3xl text-center overflow-hidden flex flex-col items-center justify-center space-y-4 shadow-2xl">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(124,58,237,0.06),transparent_70%)] pointer-events-none" />
          
          <div className="h-16 w-16 rounded-2xl bg-purple-950/20 border border-purple-500/10 flex items-center justify-center shadow-[0_4px_15px_rgba(124,58,237,0.1)] mb-2">
            <Lock className="h-8 w-8 text-purple-400 animate-pulse-slow" />
          </div>

          <div className="space-y-2 max-w-md">
            <h3 className="text-lg font-bold text-white tracking-tight">Elevated Clearance Required</h3>
            <p className="text-zinc-400 text-xs leading-relaxed">
              The Custom SQL Workbench Sandbox access is restricted to roles containing <strong>ANALYST</strong> clearance or above. Viewers are blocked from direct database querying schemas.
            </p>
          </div>

          <div className="pt-2 text-[10px] text-zinc-550 bg-zinc-900/40 px-3.5 py-2 rounded-xl border border-zinc-850 font-mono">
            Active Workspace Role: <span className="text-purple-400 font-bold uppercase">{activeRole}</span>
          </div>
        </div>
      </div>
    )
  }

  const filteredSchema = schema.filter((table) =>
    table.table_name.toLowerCase().includes(schemaSearch.toLowerCase()) ||
    table.columns.some((c) => c.name.toLowerCase().includes(schemaSearch.toLowerCase()))
  )

  return (
    <div className="space-y-8">
      {/* 1. HEADER PAGE BAR */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-900 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-purple-500 animate-pulse shadow-[0_0_8px_#8b5cf6]" />
            <span className="text-[10px] uppercase tracking-widest text-purple-400 font-bold flex items-center gap-1.5">
              <Cpu className="h-3.5 w-3.5 text-purple-400 animate-spin-slow" />
              SQL Workbench Playground
            </span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight mt-1 text-white">
            SQL Sandbox <span className="gradient-text">Studio</span>
          </h1>
          <p className="text-zinc-400 text-xs mt-1">
            Perform arbitrary read-only SQL queries on the active metrics database. Utilize safe multi-tier rollbacks and visual performance query plan analysis.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchSchemaMetadata}
            disabled={schemaLoading}
            className="p-2.5 bg-zinc-900 border border-zinc-800 rounded-xl hover:bg-zinc-850 transition text-zinc-400 disabled:opacity-50"
            title="Refresh Schema Tables Map"
          >
            <RefreshCw className={`h-4 w-4 ${schemaLoading ? "animate-spin text-purple-500" : ""}`} />
          </button>
        </div>
      </header>

      {/* 2. SPLIT WORKSPACE INTERFACE */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-8 items-start">
        
        {/* LEFT COLUMN: COLLAPSIBLE SCHEMA SCHEMA EXPLORER (1 Column) */}
        <div className="xl:col-span-1 bg-zinc-950/20 border border-zinc-900 rounded-2xl p-4 space-y-4 max-h-[680px] overflow-hidden flex flex-col shadow-inner">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-bold text-white flex items-center gap-1.5">
              <Table className="h-4 w-4 text-purple-400" />
              Database Tables
            </span>
            <span className="text-[9px] font-mono text-zinc-550 uppercase tracking-widest bg-zinc-900 px-1.5 py-0.5 rounded font-bold">
              public
            </span>
          </div>

          {/* Search box filters schema */}
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-550" />
            <input
              type="text"
              placeholder="Search tables or columns..."
              value={schemaSearch}
              onChange={(e) => setSchemaSearch(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-550 rounded-xl pl-9 pr-4 py-2 text-[11px] outline-none transition text-white placeholder-zinc-650"
            />
          </div>

          {/* Table list map */}
          <div className="flex-1 overflow-y-auto pr-1 space-y-2">
            {schemaLoading ? (
              <div className="flex flex-col items-center justify-center py-16 gap-2">
                <Loader2 className="h-6 w-6 animate-spin text-purple-500" />
                <span className="text-[10px] text-zinc-500 font-medium">Reflecting schema definitions...</span>
              </div>
            ) : filteredSchema.length === 0 ? (
              <div className="text-center py-16 text-zinc-550 text-[11px] font-medium leading-relaxed">
                No matching columns or tables found in active database catalog.
              </div>
            ) : (
              filteredSchema.map((tbl) => {
                const isExpanded = !!expandedTables[tbl.table_name]
                return (
                  <div key={tbl.table_name} className="border border-zinc-900/60 rounded-xl overflow-hidden bg-zinc-955/30 transition">
                    <button
                      onClick={() => toggleTableExpand(tbl.table_name)}
                      className="w-full flex items-center justify-between p-2.5 hover:bg-zinc-900/40 text-left transition"
                    >
                      <span className="text-xs font-bold text-zinc-200 truncate flex items-center gap-1.5">
                        <Database className="h-3.5 w-3.5 text-zinc-500" />
                        {tbl.table_name}
                      </span>
                      {isExpanded ? (
                        <ChevronDown className="h-3.5 w-3.5 text-zinc-500" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-zinc-500" />
                      )}
                    </button>

                    {isExpanded && (
                      <div className="border-t border-zinc-900 p-2 space-y-1 bg-zinc-950/20 max-h-48 overflow-y-auto font-mono text-[10px]">
                        {tbl.columns.map((col) => (
                          <div key={col.name} className="flex justify-between items-center px-1.5 py-1 rounded hover:bg-zinc-900/50">
                            <span className="text-zinc-300 font-medium truncate max-w-[70%]" title={col.name}>
                              {col.name}
                            </span>
                            <span className="text-[9px] text-purple-400/90 font-bold truncate max-w-[30%] shrink-0 align-right" title={col.data_type}>
                              {col.data_type}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: WORKBENCH QUERY WRITER & SPREADSHEET (3 Columns) */}
        <div className="xl:col-span-3 space-y-6">
          {/* Query Editor Panel */}
          <div className="glassmorphism glow-border rounded-2xl p-5 space-y-4 border-purple-500/5 bg-purple-950/2 relative shadow-[0_4px_15px_rgba(124,58,237,0.03)]">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-bold text-white flex items-center gap-1.5">
                <FileCode className="h-4 w-4 text-purple-400" />
                Query Editor
              </span>
              <span className="text-[10px] text-zinc-500 font-medium flex items-center gap-1">
                <Info className="h-3 w-3 text-purple-500" />
                Secure Read-Only Sandboxed Queries Only
              </span>
            </div>

            {/* Styled SQL textarea */}
            <div className="relative border border-zinc-900 rounded-xl overflow-hidden bg-zinc-955/80 font-mono text-xs">
              <textarea
                value={sqlQuery}
                onChange={(e) => setSqlQuery(e.target.value)}
                placeholder="-- Enter read-only SQL query here..."
                disabled={queryExecuting}
                className="w-full h-44 p-4 bg-transparent text-zinc-100 outline-none resize-y placeholder-zinc-700 leading-relaxed overflow-y-auto"
                spellCheck={false}
              />
            </div>

            {/* Controls panel */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2 border-t border-zinc-900/60">
              <div className="text-[10px] text-zinc-550 flex items-center gap-1 px-1">
                <Clock className="h-3.5 w-3.5" />
                Auto-rollback transaction isolations active
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setSqlQuery("")}
                  disabled={queryExecuting}
                  className="px-4 py-2.5 bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 hover:text-white rounded-xl text-xs font-bold text-zinc-400 transition disabled:opacity-50"
                >
                  Clear Editor
                </button>

                <button
                  onClick={() => handleExecuteQuery(true)}
                  disabled={queryExecuting}
                  className="flex items-center gap-1.5 px-4 py-2.5 bg-indigo-950/40 hover:bg-indigo-900/20 border border-indigo-500/20 text-indigo-400 transition rounded-xl text-xs font-bold disabled:opacity-50"
                  title="Return deep PostgreSQL JSON query execution path analysis"
                >
                  {queryExecuting ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Network className="h-3.5 w-3.5" />
                  )}
                  Explain Performance
                </button>

                <button
                  onClick={() => handleExecuteQuery(false)}
                  disabled={queryExecuting}
                  className="flex items-center gap-1.5 px-5 py-2.5 bg-purple-650 hover:bg-purple-600 transition rounded-xl text-xs font-bold text-white shadow-[0_4px_12px_rgba(124,58,237,0.25)] disabled:opacity-50"
                >
                  {queryExecuting ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Executing...
                    </>
                  ) : (
                    <>
                      <Play className="h-3.5 w-3.5 fill-current" />
                      Run SQL Query
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Results spreadsheet panel */}
          {queryExecuting && (
            <div className="flex flex-col items-center justify-center py-28 gap-3 bg-zinc-950/10 border border-zinc-900 rounded-3xl">
              <Loader2 className="h-9 w-9 animate-spin text-purple-500" />
              <span className="text-zinc-400 text-xs font-medium">Running secure sandboxed database transaction sweep...</span>
            </div>
          )}

          {!queryExecuting && queryResponse && (
            <div className="bg-zinc-950/20 border border-zinc-900 rounded-3xl overflow-hidden p-6 space-y-5">
              
              {/* Header metrics & error indicator */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-900 pb-4">
                <div className="flex items-center gap-2">
                  {queryResponse.success ? (
                    <>
                      <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                      <span className="text-xs font-bold text-white tracking-tight">Execution Completed Successfully</span>
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="h-5 w-5 text-red-400" />
                      <span className="text-xs font-bold text-red-400 tracking-tight">SQL Error Encountered</span>
                    </>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-4 text-[10px] font-mono font-bold text-zinc-500 bg-zinc-950/60 p-2 rounded-xl border border-zinc-900">
                  <div className="flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5" />
                    Latency: <span className="text-purple-400">{queryResponse.execution_time_ms.toFixed(2)} ms</span>
                  </div>
                  {queryResponse.success && !queryResponse.explain_plan && (
                    <div className="flex items-center gap-1">
                      <Layers className="h-3.5 w-3.5" />
                      Rows Extracted: <span className="text-emerald-400">{queryResponse.rows.length}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Action tabs for Success results */}
              {queryResponse.success && (
                <div className="flex gap-2.5 p-1 bg-zinc-950 border border-zinc-900 rounded-xl w-fit">
                  <button
                    onClick={() => setActiveTab("results")}
                    disabled={queryResponse.explain_plan !== null && queryResponse.columns.length === 0}
                    className={`px-4 py-2 text-xs font-bold rounded-lg transition ${
                      activeTab === "results"
                        ? "bg-purple-650 text-white"
                        : "text-zinc-400 hover:bg-zinc-900/60 hover:text-white disabled:opacity-50"
                    }`}
                  >
                    Raw Output Grid
                  </button>

                  <button
                    onClick={() => setActiveTab("plan")}
                    disabled={!queryResponse.explain_plan}
                    className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg transition ${
                      activeTab === "plan"
                        ? "bg-purple-650 text-white"
                        : "text-zinc-400 hover:bg-zinc-900/60 hover:text-white disabled:opacity-50"
                    }`}
                  >
                    <Network className="h-3.5 w-3.5" />
                    Query Execution Tree Plan
                  </button>
                </div>
              )}

              {/* Error Box display */}
              {!queryResponse.success && queryResponse.error && (
                <div className="bg-red-950/10 border border-red-900/20 p-4 rounded-2xl space-y-2 text-xs leading-relaxed">
                  <div className="text-red-400 font-bold uppercase tracking-wider flex items-center gap-1 text-[10px]">
                    <AlertTriangle className="h-4 w-4" />
                    PostgreSQL / Sandbox Engine Diagnostics
                  </div>
                  <pre className="text-zinc-300 font-mono text-[11px] whitespace-pre-wrap font-semibold leading-relaxed bg-black/30 p-3 rounded-xl border border-zinc-950 shadow-inner">
                    {queryResponse.error}
                  </pre>
                </div>
              )}

              {/* TAB 1: SPREADSHEET GRID OUTPUTS */}
              {queryResponse.success && activeTab === "results" && (
                <div className="space-y-4">
                  {queryResponse.rows.length === 0 ? (
                    <div className="text-center py-16 text-zinc-550 text-xs font-medium bg-zinc-950/20 border border-zinc-900 rounded-2xl leading-relaxed">
                      Statement executed successfully, but returned zero query records.
                    </div>
                  ) : (
                    <div className="border border-zinc-900 rounded-2xl overflow-hidden shadow-inner max-h-96 overflow-y-auto">
                      <table className="w-full text-left border-collapse text-xs">
                        <thead className="bg-zinc-950/80 sticky top-0 text-zinc-400 font-bold border-b border-zinc-900 backdrop-blur-sm z-10">
                          <tr>
                            {queryResponse.columns.map((col) => (
                              <th key={col} className="p-3.5 text-[11px] uppercase tracking-wider border-r border-zinc-900 last:border-0 font-mono">
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-900/60">
                          {queryResponse.rows.map((row, idx) => (
                            <tr key={idx} className="hover:bg-zinc-900/20 transition">
                              {queryResponse.columns.map((col) => {
                                const val = row[col]
                                return (
                                  <td key={col} className="p-3.5 border-r border-zinc-900/60 last:border-0 font-mono text-zinc-300 max-w-[200px] truncate" title={String(val)}>
                                    {val === null ? (
                                      <span className="text-zinc-650 italic">NULL</span>
                                    ) : typeof val === "boolean" ? (
                                      val ? (
                                        <span className="text-emerald-400 font-bold">TRUE</span>
                                      ) : (
                                        <span className="text-rose-400 font-bold">FALSE</span>
                                      )
                                    ) : typeof val === "object" ? (
                                      JSON.stringify(val)
                                    ) : (
                                      String(val)
                                    )}
                                  </td>
                                )
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: QUERY PLAN RECURSIVE TREE */}
              {queryResponse.success && activeTab === "plan" && queryResponse.explain_plan && (
                <div className="space-y-6">
                  {/* Summary plan metrics */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="bg-zinc-950/60 border border-zinc-900 p-4 rounded-2xl shadow-sm text-center">
                      <span className="text-zinc-550 block text-[9px] uppercase tracking-widest font-bold mb-1">Planning Overhead</span>
                      <span className="text-base font-extrabold text-white font-mono">
                        {queryResponse.explain_plan[0]["Planning Time"] !== undefined
                          ? `${queryResponse.explain_plan[0]["Planning Time"].toFixed(3)} ms`
                          : "N/A"}
                      </span>
                    </div>

                    <div className="bg-zinc-950/60 border border-zinc-900 p-4 rounded-2xl shadow-sm text-center">
                      <span className="text-zinc-550 block text-[9px] uppercase tracking-widest font-bold mb-1">Execution Overhead</span>
                      <span className="text-base font-extrabold text-purple-400 font-mono">
                        {queryResponse.explain_plan[0]["Execution Time"] !== undefined
                          ? `${queryResponse.explain_plan[0]["Execution Time"].toFixed(3)} ms`
                          : "N/A"}
                      </span>
                    </div>

                    <div className="bg-emerald-950/5 border border-emerald-900/10 p-4 rounded-2xl shadow-sm text-center">
                      <span className="text-emerald-500/70 block text-[9px] uppercase tracking-widest font-bold mb-1 flex items-center justify-center gap-1">
                        <Cpu className="h-3 w-3" />
                        Execution Bottleneck Root
                      </span>
                      <span className="text-xs font-bold text-emerald-400 truncate block">
                        {queryResponse.explain_plan[0].Plan["Node Type"]}
                      </span>
                    </div>
                  </div>

                  {/* Plan Tree rendering */}
                  <div className="bg-zinc-950/80 border border-zinc-900 rounded-3xl p-5 md:p-6 overflow-x-auto shadow-inner">
                    <div className="min-w-[600px] py-2">
                      <div className="flex items-center gap-2 mb-4 px-1 pb-3 border-b border-zinc-900/60">
                        <Network className="h-4.5 w-4.5 text-purple-400" />
                        <span className="text-xs font-bold text-white uppercase tracking-wider">PostgreSQL Node Hierarchy</span>
                      </div>
                      
                      <PlanNodeTree node={queryResponse.explain_plan[0].Plan} level={0} />
                    </div>
                  </div>
                </div>
              )}

            </div>
          )}

        </div>

      </div>

    </div>
  )
}

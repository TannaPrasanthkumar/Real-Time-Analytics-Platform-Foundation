/**
 * Type-safe API Client with correlation-id propagation and structured error boundary processing.
 */

export interface APIErrorResponse {
  success: boolean
  error: {
    code: string
    message: string
    details?: any
    correlation_id?: string
  }
}

export class APIClientError extends Error {
  code: string
  status: number
  details?: any
  correlationId?: string

  constructor(status: number, errorData: APIErrorResponse["error"]) {
    super(errorData.message)
    this.name = "APIClientError"
    this.status = status
    this.code = errorData.code
    this.details = errorData.details
    this.correlationId = errorData.correlation_id
  }
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${path}`
  
  // Resolve or generate correlation ID for tracking
  const correlationId = typeof crypto !== "undefined" 
    ? crypto.randomUUID() 
    : Math.random().toString(36).substring(2, 15)

  const headers = new Headers(options.headers)
  headers.set("Content-Type", "application/json")
  headers.set("x-correlation-id", correlationId)

  // Retrieve token from local storage (to be supported in Phase 2)
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token")
    if (token) {
      headers.set("Authorization", `Bearer ${token}`)
    }
  }

  const config: RequestInit = {
    ...options,
    headers,
  }

  try {
    const response = await fetch(url, config)
    
    if (response.status === 204) {
      return {} as T
    }

    const data = await response.json()

    if (!response.ok) {
      const errorResponse = data as APIErrorResponse
      throw new APIClientError(
        response.status,
        errorResponse.error || {
          code: "HTTP_ERROR",
          message: `Network response returned status code ${response.status}`,
          correlation_id: correlationId
        }
      )
    }

    return data as T
  } catch (error) {
    if (error instanceof APIClientError) {
      throw error
    }
    
    // Convert generic fetch/network errors into structured app client errors
    throw new APIClientError(500, {
      code: "NETWORK_DISCONNECTED",
      message: error instanceof Error ? error.message : "Failed to establish a network connection to API gateway.",
      correlation_id: correlationId
    })
  }
}

export const api = {
  get: <T>(path: string, options?: RequestInit) => request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body: any, options?: RequestInit) =>
    request<T>(path, { ...options, method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body: any, options?: RequestInit) =>
    request<T>(path, { ...options, method: "PUT", body: JSON.stringify(body) }),
  delete: <T>(path: string, options?: RequestInit) => request<T>(path, { ...options, method: "DELETE" }),
}

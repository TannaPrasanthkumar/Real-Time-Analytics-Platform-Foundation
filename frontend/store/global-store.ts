import { create } from "zustand"

export interface User {
  id: string
  email: string
  full_name: string | null
  is_superuser: boolean
}

export interface Organization {
  id: string
  name: string
  slug: string
  is_active: boolean
}

export interface Membership {
  organization: Organization
  role: "owner" | "admin" | "analyst" | "viewer"
}

interface GlobalState {
  // Authentication State
  user: User | null
  organization: Organization | null
  organizations: Membership[]
  isAuthenticated: boolean
  token: string | null
  
  // UI States
  sidebarOpen: boolean
  activeDashboardId: string | null
  
  // State Actions
  setAuth: (user: User, token: string) => void
  setOrganizations: (orgs: Membership[]) => void
  setOrganization: (org: Organization | null) => void
  clearAuth: () => void
  toggleSidebar: () => void
  setActiveDashboard: (id: string | null) => void
}

export const useGlobalStore = create<GlobalState>((set) => ({
  user: null,
  organization: null,
  organizations: [],
  isAuthenticated: false,
  token: null,
  sidebarOpen: true,
  activeDashboardId: null,

  setAuth: (user, token) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("token", token)
    }
    set({ user, token, isAuthenticated: true })
  },

  setOrganizations: (organizations) => {
    set({ organizations })
    // Automatically select the first organization if none is active
    set((state) => {
      if (!state.organization && organizations.length > 0) {
        return { organization: organizations[0].organization }
      }
      return {}
    })
  },

  setOrganization: (organization) => {
    set({ organization, activeDashboardId: null }) // Reset active dashboard when switching org
  },

  clearAuth: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("token")
    }
    set({ 
      user: null, 
      organization: null, 
      organizations: [], 
      token: null, 
      isAuthenticated: false,
      activeDashboardId: null 
    })
  },

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  
  setActiveDashboard: (id) => set({ activeDashboardId: id }),
}))

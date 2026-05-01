import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface Landlord {
  id: string
  email: string
  full_name: string
  avatar_url?: string
  subscription_tier: string
  ai_tokens_used: number
  ai_tokens_limit: number
}

interface AuthState {
  accessToken: string | null
  landlord: Landlord | null
  setAuth: (token: string, landlord: Landlord) => void
  updateLandlord: (landlord: Partial<Landlord>) => void
  logout: () => void
  isAuthenticated: () => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      landlord: null,
      setAuth: (token, landlord) => set({ accessToken: token, landlord }),
      updateLandlord: (partial) =>
        set((s) => ({ landlord: s.landlord ? { ...s.landlord, ...partial } : null })),
      logout: () => set({ accessToken: null, landlord: null }),
      isAuthenticated: () => !!get().accessToken && !!get().landlord,
    }),
    { name: 'nyumba-auth', partialize: (s) => ({ accessToken: s.accessToken, landlord: s.landlord }) }
  )
)

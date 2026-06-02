import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { getApiUrl } from '@/lib/config'

interface AuthState {
  isAuthenticated: boolean
  token: string | null
  user: { id: string; username: string; display_name: string; role: string; status: string } | null
  isLoading: boolean
  error: string | null
  lastAuthCheck: number | null
  isCheckingAuth: boolean
  hasHydrated: boolean
  authRequired: boolean | null
  setHasHydrated: (state: boolean) => void
  checkAuthRequired: () => Promise<boolean>
  login: (usernameOrPassword: string, password?: string) => Promise<boolean>
  register: (username: string, password: string, displayName: string) => Promise<{ success: boolean; message?: string }>
  logout: () => void
  checkAuth: () => Promise<boolean>
  updateProfile: (displayName: string) => Promise<boolean>
  changePassword: (oldPassword: string, newPassword: string) => Promise<{ success: boolean; message?: string }>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      isAuthenticated: false,
      token: null,
      user: null,
      isLoading: false,
      error: null,
      lastAuthCheck: null,
      isCheckingAuth: false,
      hasHydrated: false,
      authRequired: null,

      setHasHydrated: (state: boolean) => {
        set({ hasHydrated: state })
      },

      checkAuthRequired: async () => {
        try {
          const apiUrl = await getApiUrl()
          const response = await fetch(`${apiUrl}/api/auth/status`, {
            cache: 'no-store',
          })

          if (!response.ok) {
            throw new Error(`Auth status check failed: ${response.status}`)
          }

          const data = await response.json()
          const required = data.auth_enabled || false
          set({ authRequired: required })

          // If auth is not required, mark as authenticated
          if (!required) {
            set({ isAuthenticated: true, token: 'not-required' })
          }

          return required
        } catch (error) {
          console.error('Failed to check auth status:', error)

          // If it's a network error, set a more helpful error message
          if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
            set({
              error: 'Unable to connect to server. Please check if the API is running.',
              authRequired: null  // Don't assume auth is required if we can't connect
            })
          } else {
            // For other errors, default to requiring auth to be safe
            set({ authRequired: true })
          }

          // Re-throw the error so the UI can handle it
          throw error
        }
      },

      login: async (usernameOrPassword: string, password?: string) => {
        set({ isLoading: true, error: null })
        try {
          const apiUrl = await getApiUrl()

          // If no second parameter, treat it as legacy / backdoor-only password
          const body: Record<string, string> = {}
          if (password === undefined) {
            body.username = 'admin'
            body.password = usernameOrPassword
          } else {
            body.username = usernameOrPassword
            body.password = password
          }

          const response = await fetch(`${apiUrl}/api/auth/login`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
          })
          
          if (response.ok) {
            const data = await response.json()
            // Set auth-token cookie for server-side middleware access
            if (typeof document !== 'undefined') {
              document.cookie = `auth-token=${data.access_token}; path=/; max-age=${7 * 24 * 60 * 60}; SameSite=Lax`
            }
            set({ 
              isAuthenticated: true, 
              token: data.access_token, 
              user: data.user,
              isLoading: false,
              lastAuthCheck: Date.now(),
              error: null
            })
            return true
          } else {
            let errorMessage = 'Authentication failed'
            try {
              const errData = await response.json()
              errorMessage = errData.detail || errorMessage
            } catch {}
            
            if (response.status === 401 && errorMessage === 'Authentication failed') {
              errorMessage = 'Invalid username or password. Please try again.'
            } else if (response.status === 403 && errorMessage === 'Authentication failed') {
              errorMessage = 'Access denied. Please check your credentials.'
            } else if (response.status >= 500) {
              errorMessage = 'Server error. Please try again later.'
            }
            
            set({ 
              error: errorMessage,
              isLoading: false,
              isAuthenticated: false,
              token: null,
              user: null
            })
            return false
          }
        } catch (error) {
          console.error('Network error during auth:', error)
          let errorMessage = 'Authentication failed'
          
          if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
            errorMessage = 'Unable to connect to server. Please check if the API is running.'
          } else if (error instanceof Error) {
            errorMessage = `Network error: ${error.message}`
          } else {
            errorMessage = 'An unexpected error occurred during authentication'
          }
          
          set({ 
            error: errorMessage,
            isLoading: false,
            isAuthenticated: false,
            token: null,
            user: null
          })
          return false
        }
      },

      register: async (username: string, password: string, displayName: string) => {
        set({ isLoading: true, error: null })
        try {
          const apiUrl = await getApiUrl()

          const response = await fetch(`${apiUrl}/api/auth/register`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              username,
              password,
              display_name: displayName
            })
          })

          if (response.ok) {
            set({ isLoading: false, error: null })
            return { success: true }
          } else {
            let errorMessage = 'Registration failed'
            try {
              const errData = await response.json()
              errorMessage = errData.detail || errorMessage
            } catch {}

            set({ isLoading: false })
            return { success: false, message: errorMessage }
          }
        } catch (error) {
          console.error('Network error during registration:', error)
          let errorMessage = 'Registration failed'
          if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
            errorMessage = 'Unable to connect to server. Please check if the API is running.'
          } else if (error instanceof Error) {
            errorMessage = `Network error: ${error.message}`
          }
          set({ isLoading: false })
          return { success: false, message: errorMessage }
        }
      },
      
      logout: async () => {
        // Best-effort: notify server to log out
        try {
          const apiUrl = await getApiUrl()
          const token = get().token
          await fetch(`${apiUrl}/api/auth/logout`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          })
        } catch {
          // Ignore network errors during logout
        }

        // Clear auth-token cookie
        if (typeof document !== 'undefined') {
          document.cookie = 'auth-token=; path=/; max-age=0'
        }
        set({ 
          isAuthenticated: false, 
          token: null, 
          user: null,
          error: null 
        })
      },
      
      checkAuth: async () => {
        const state = get()
        const { token, lastAuthCheck, isCheckingAuth, isAuthenticated } = state

        // If already checking, return current auth state
        if (isCheckingAuth) {
          return isAuthenticated
        }

        // If no token, not authenticated
        if (!token) {
          return false
        }

        // If we checked recently (within 30 seconds) and are authenticated, skip
        const now = Date.now()
        if (isAuthenticated && lastAuthCheck && (now - lastAuthCheck) < 30000) {
          return true
        }

        set({ isCheckingAuth: true })

        try {
          const apiUrl = await getApiUrl()

          const response = await fetch(`${apiUrl}/api/notebooks`, {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          })
          
          if (response.ok) {
            set({ 
              isAuthenticated: true, 
              lastAuthCheck: now,
              isCheckingAuth: false 
            })
            return true
          } else {
            set({
              isAuthenticated: false,
              token: null,
              lastAuthCheck: null,
              isCheckingAuth: false
            })
            return false
          }
        } catch (error) {
          console.error('checkAuth error:', error)
          set({
            isAuthenticated: false,
            token: null,
            lastAuthCheck: null,
            isCheckingAuth: false
          })
          return false
        }
      },

      updateProfile: async (displayName: string) => {
        try {
          const apiUrl = await getApiUrl()
          const token = get().token
          const response = await fetch(`${apiUrl}/api/auth/me`, {
            method: 'PUT',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ display_name: displayName })
          })
          if (response.ok) {
            const data = await response.json()
            set({ user: { ...get().user!, display_name: data.display_name } })
            return true
          }
          return false
        } catch {
          return false
        }
      },

      changePassword: async (oldPassword: string, newPassword: string) => {
        try {
          const apiUrl = await getApiUrl()
          const token = get().token
          const response = await fetch(`${apiUrl}/api/auth/me/password`, {
            method: 'PUT',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
          })
          if (response.ok) {
            return { success: true }
          }
          const errData = await response.json().catch(() => ({}))
          return { success: false, message: errData.detail || '修改失败' }
        } catch {
          return { success: false, message: '网络连接失败' }
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        isAuthenticated: state.isAuthenticated,
        user: state.user
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true)
      }
    }
  )
)
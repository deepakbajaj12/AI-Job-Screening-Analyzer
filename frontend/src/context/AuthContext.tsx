import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { initializeApp } from 'firebase/app'
import { getAuth, GoogleAuthProvider, onAuthStateChanged, signInWithPopup, signOut as fbSignOut } from 'firebase/auth'

type Ctx = {
  user: { uid: string; email?: string | null } | null
  token: string | null
  signIn: () => Promise<void>
  signOut: () => Promise<void>
}

const Context = createContext<Ctx>({ user: null, token: null, signIn: async () => {}, signOut: async () => {} })

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
}

let appInited = false
let auth: ReturnType<typeof getAuth> | null = null
function ensureFirebase() {
  if (appInited) return
  if (firebaseConfig.apiKey) {
    const app = initializeApp(firebaseConfig)
    auth = getAuth(app)
  }
  appInited = true
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Ctx['user']>(null)
  const [token, setToken] = useState<string | null>(null)

  useEffect(() => {
    ensureFirebase()
    if (!auth) {
      // Dev bypass: provide dummy token if enabled
      if (import.meta.env.VITE_DEV_BYPASS === '1') {
        setUser({ uid: 'dev-user', email: 'dev@example.com' })
        setToken('dev')
      }
      return
    }
    const unsub = onAuthStateChanged(auth, async (u) => {
      setUser(u ? { uid: u.uid, email: u.email } : null)
      setToken(u ? await u.getIdToken() : null)
    })
    return () => unsub()
  }, [])

  const value = useMemo<Ctx>(() => ({
    user,
    token,
    signIn: async () => {
      ensureFirebase()
      if (!auth) {
        if (import.meta.env.VITE_DEV_BYPASS === '1') {
          setUser({ uid: 'dev-user', email: 'dev@example.com' })
          setToken('dev')
        }
        return
      }
      await signInWithPopup(auth, new GoogleAuthProvider())
    },
    signOut: async () => {
      ensureFirebase()
      if (!auth) {
        setUser(null)
        setToken(null)
        return
      }
      await fbSignOut(auth)
    }
  }), [user, token])

  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function useAuth() { return useContext(Context) }

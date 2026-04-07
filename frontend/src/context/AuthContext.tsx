// AUTHENTICATION CONTEXT: Firebase authentication state management (login/logout/user info) accessible across all components
import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { initializeApp } from 'firebase/app'
import {
  ConfirmationResult,
  getAuth,
  GoogleAuthProvider,
  onIdTokenChanged,
  RecaptchaVerifier,
  signInWithEmailAndPassword,
  signInWithPhoneNumber,
  signInWithPopup,
  signOut as fbSignOut
} from 'firebase/auth'
import { postLoginWelcome } from '../api/client'

type Ctx = {
  user: { uid: string; email?: string | null; phoneNumber?: string | null } | null
  token: string | null
  authMessage: string | null
  signIn: () => Promise<void>
  signInWithEmail: (email: string, password: string) => Promise<void>
  sendPhoneOtp: (phoneNumber: string) => Promise<void>
  verifyPhoneOtp: (otp: string) => Promise<void>
  signOut: () => Promise<void>
}

const Context = createContext<Ctx>({
  user: null,
  token: null,
  authMessage: null,
  signIn: async () => {},
  signInWithEmail: async () => {},
  sendPhoneOtp: async () => {},
  verifyPhoneOtp: async () => {},
  signOut: async () => {}
})

declare global {
  interface Window {
    recaptchaVerifier?: RecaptchaVerifier
  }
}

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
}

const CANONICAL_APP_URL = (import.meta.env.VITE_CANONICAL_APP_URL || 'https://ai-job-screening-analyzer.vercel.app').replace(/\/$/, '')

function getCanonicalRedirectUrl() {
  try {
    const target = new URL(CANONICAL_APP_URL)
    const current = window.location
    if (current.hostname !== target.hostname) {
      return `${target.origin}${current.pathname}${current.search}${current.hash}`
    }
  } catch {
    // Invalid canonical URL should not block auth flow.
  }
  return null
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
  const [authMessage, setAuthMessage] = useState<string | null>(null)
  const [phoneConfirmation, setPhoneConfirmation] = useState<ConfirmationResult | null>(null)
  const welcomedUidRef = useRef<string | null>(null)

  const ensureRecaptcha = () => {
    ensureFirebase()
    if (!auth) throw new Error('Firebase auth is not available')
    if (!window.recaptchaVerifier) {
      window.recaptchaVerifier = new RecaptchaVerifier(auth, 'recaptcha-container', {
        size: 'invisible'
      })
    }
    return window.recaptchaVerifier
  }

  useEffect(() => {
    // Dev bypass takes priority
    if (import.meta.env.VITE_DEV_BYPASS === '1') {
      setUser({ uid: 'dev-user', email: 'dev@example.com' })
      setToken('dev')
      return
    }

    ensureFirebase()
    if (!auth) {
      return
    }
    const unsub = onIdTokenChanged(auth, async (u) => {
      if (!u) {
        setUser(null)
        setToken(null)
        welcomedUidRef.current = null
        return
      }

      const idToken = await u.getIdToken()
      setUser({ uid: u.uid, email: u.email, phoneNumber: u.phoneNumber })
      setToken(idToken)

      if (welcomedUidRef.current !== u.uid) {
        try {
          const welcome = await postLoginWelcome(idToken, {
            email: u.email,
            displayName: u.displayName,
            phoneNumber: u.phoneNumber
          })
          if (welcome.welcomeEmailSent && u.email) {
            setAuthMessage(`Welcome email sent to ${u.email}`)
          }
          welcomedUidRef.current = u.uid
        } catch (err) {
          console.warn('Post-login welcome notification failed:', err)
        }
      }
    })
    return () => unsub()
  }, [])

  useEffect(() => {
    if (import.meta.env.VITE_DEV_BYPASS === '1') return
    ensureFirebase()
    if (!auth) return

    // Keep token fresh for long-lived sessions to avoid 401/expired-token failures.
    const timer = setInterval(async () => {
      const current = auth?.currentUser
      if (!current) return
      try {
        const fresh = await current.getIdToken(true)
        setToken(fresh)
      } catch (err) {
        console.warn('Token refresh failed:', err)
      }
    }, 10 * 60 * 1000)

    return () => clearInterval(timer)
  }, [])

  const value = useMemo<Ctx>(() => ({
    user,
    token,
    authMessage,
    signIn: async () => {
      if (import.meta.env.VITE_DEV_BYPASS === '1') {
        setUser({ uid: 'dev-user', email: 'dev@example.com' })
        setToken('dev')
        console.log('Dev bypass: auto signed in')
        return
      }
      ensureFirebase()
      if (!auth) {
        console.warn('Firebase not configured. Set VITE_FIREBASE_API_KEY or enable VITE_DEV_BYPASS=1')
        alert('Sign in not configured. Please enable dev bypass or add Firebase credentials.')
        return
      }

      const redirectUrl = getCanonicalRedirectUrl()
      if (redirectUrl) {
        setAuthMessage('Redirecting to secure login domain...')
        window.location.assign(redirectUrl)
        return
      }

      try {
        setAuthMessage(null)
        console.log('Starting Google Sign-In with Firebase...')
        const result = await signInWithPopup(auth, new GoogleAuthProvider())
        console.log('Sign-in successful:', result.user.email)
      } catch (error: any) {
        console.error('Sign in failed - Full error:', error)
        console.error('Error code:', error.code)
        console.error('Error message:', error.message)
        console.error('Firebase config:', { apiKey: firebaseConfig.apiKey ? '***set***' : 'missing', authDomain: firebaseConfig.authDomain, projectId: firebaseConfig.projectId })
        if (error?.code === 'auth/unauthorized-domain') {
          setAuthMessage(`This URL is not allowed by Firebase. Open ${CANONICAL_APP_URL} to sign in.`)
        }
        alert(`Sign in failed: ${error.message || error.code || 'Unknown error'}. Check console for details.`)
      }
    },
    signInWithEmail: async (email: string, password: string) => {
      ensureFirebase()
      if (!auth) {
        alert('Email login is not configured. Please add Firebase credentials.')
        return
      }
      setAuthMessage(null)
      await signInWithEmailAndPassword(auth, email, password)
    },
    sendPhoneOtp: async (phoneNumber: string) => {
      ensureFirebase()
      if (!auth) {
        alert('Phone login is not configured. Please add Firebase credentials.')
        return
      }
      setAuthMessage(null)
      const verifier = ensureRecaptcha()
      try {
        const confirmation = await signInWithPhoneNumber(auth, phoneNumber, verifier)
        setPhoneConfirmation(confirmation)
        setAuthMessage('OTP sent to your phone number')
      } catch (err) {
        // Clear the cached verifier so a fresh one is created on the next attempt.
        // A used or failed verifier cannot be reused.
        if (window.recaptchaVerifier) {
          window.recaptchaVerifier.clear()
          window.recaptchaVerifier = undefined
        }
        throw err
      }
    },
    verifyPhoneOtp: async (otp: string) => {
      if (!phoneConfirmation) {
        throw new Error('Request OTP first')
      }
      setAuthMessage(null)
      await phoneConfirmation.confirm(otp)
      setPhoneConfirmation(null)
    },
    signOut: async () => {
      if (import.meta.env.VITE_DEV_BYPASS === '1') {
        setUser(null)
        setToken(null)
        return
      }
      ensureFirebase()
      if (!auth) {
        setUser(null)
        setToken(null)
        return
      }
      await fbSignOut(auth)
    }
  }), [authMessage, phoneConfirmation, token, user])

  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function useAuth() { return useContext(Context) }

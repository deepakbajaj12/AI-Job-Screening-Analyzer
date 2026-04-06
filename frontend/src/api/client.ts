// API CLIENT: Centralized HTTP client with retry logic, error handling, and all analysis, coaching, and recruiter endpoints
export const API_BASE = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? 'http://localhost:5000' : 'https://ai-job-screening-analyzer.onrender.com')

export class ApiError extends Error {
  status: number
  code?: string
  retryAfterSeconds?: number

  constructor(message: string, status: number, code?: string, retryAfterSeconds?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.retryAfterSeconds = retryAfterSeconds
  }
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function readErrorPayload(res: Response): Promise<{ message: string, code?: string, retryAfterSeconds?: number }> {
  try {
    const data = await res.json()
    const message = data?.message || data?.error || `Request failed: ${res.status}`
    const code = data?.error
    const retryAfterSeconds = Number(data?.retryAfterSeconds)
    return {
      message,
      code,
      retryAfterSeconds: Number.isFinite(retryAfterSeconds) ? retryAfterSeconds : undefined,
    }
  } catch {
    return { message: `Request failed: ${res.status}` }
  }
}

async function fetchJsonWithRetry(
  url: string,
  init: RequestInit,
  options?: { retries?: number, baseDelayMs?: number }
) {
  const retries = options?.retries ?? 2
  const baseDelayMs = options?.baseDelayMs ?? 500

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, init)
      if (res.ok) return res.json()

      const payload = await readErrorPayload(res)
      const retryable = res.status === 429 || res.status === 502 || res.status === 503 || res.status === 504
      if (retryable && attempt < retries) {
        const retryDelay = payload.retryAfterSeconds
          ? payload.retryAfterSeconds * 1000
          : Math.round(baseDelayMs * Math.pow(2, attempt))
        await sleep(retryDelay)
        continue
      }

      throw new ApiError(payload.message, res.status, payload.code, payload.retryAfterSeconds)
    } catch (err: any) {
      if (attempt >= retries) throw err
      // Network errors are retried with exponential backoff.
      if (err instanceof ApiError) throw err
      await sleep(Math.round(baseDelayMs * Math.pow(2, attempt)))
    }
  }

  throw new ApiError('Request failed after retries', 0)
}


async function pollJob(jobId: string, maxWaitMs = 300000, initialDelayMs = 1000) {
  let attempts = 0
  let delayMs = initialDelayMs
  const startTime = Date.now()
  
  while (Date.now() - startTime < maxWaitMs) {
    await new Promise(r => setTimeout(r, delayMs))
    
    try {
      const res = await fetch(`${API_BASE}/status/${jobId}`)
      if (res.ok) {
        const data = await res.json()
        if (data.status === 'finished' || data.status === 'completed') return data.result
        if (data.status === 'failed') throw new Error(data.error || 'Analysis failed')
        if (data.status === 'queued' || data.status === 'started') {
          // /analyze uses async queueing; if /status is stale, try Celery task status path too.
          try {
            const taskRes = await fetch(`${API_BASE}/tasks/${jobId}`)
            if (taskRes.ok) {
              const taskData = await taskRes.json()
              const state = String(taskData.state || '').toUpperCase()
              if (state === 'SUCCESS') return taskData.result
              if (state === 'FAILURE' || state === 'REVOKED') {
                throw new Error(taskData.error || 'Analysis failed')
              }
            }
          } catch {
            // Ignore fallback polling errors and continue normal polling loop.
          }
        }
        if (data.status === 'unknown') {
          // Job was cleaned up from Redis - this is normal for completed jobs
          if (data.result) return data.result
          throw new Error('Job completed but result is no longer available. Please try again.')
        }
        // If status is "queued" or "started", we keep waiting
      } else if (res.status === 404) {
        // Job not found - stop polling immediately instead of waiting for timeout
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.message || 'Job not found. It may have expired.')
      }
    } catch (error: any) {
      // Don't retry on job-specific errors, only on network errors
      if (error.message.includes('Job')) {
        throw error
      }
      // Network error, retry with exponential backoff
      if (error.message.includes('fetch')) {
        // Continue polling on network errors
      } else if (!error.message.includes('fetch')) {
        throw error
      }
    }
    
    // Exponential backoff: cap at 5 seconds between attempts
    delayMs = Math.min(delayMs * 1.5, 5000)
    attempts++
  }
  
  throw new Error(`Analysis timed out after ${maxWaitMs / 1000}s. Please check back later.`)
}

async function pollTask(taskId: string, maxWaitMs = 300000, initialDelayMs = 1000) {
  let delayMs = initialDelayMs
  const startTime = Date.now()

  while (Date.now() - startTime < maxWaitMs) {
    await new Promise(r => setTimeout(r, delayMs))

    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`)
      if (res.ok) {
        const data = await res.json()
        const state = String(data.state || '').toUpperCase()

        if (state === 'SUCCESS') return data.result
        if (state === 'FAILURE' || state === 'REVOKED') throw new Error(data.error || 'Task failed')
        // PENDING/RECEIVED/STARTED/RETRY -> keep polling
      } else if (res.status === 404) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.message || 'Task not found. It may have expired.')
      }
    } catch (error: any) {
      if (error.message.includes('Task')) throw error
      if (!error.message.includes('fetch')) throw error
      // Network errors are retried by continuing polling.
    }

    delayMs = Math.min(delayMs * 1.5, 5000)
  }

  throw new Error(`Task timed out after ${maxWaitMs / 1000}s. Please check back later.`)
}

export async function analyzeJobSeeker(token: string | null, payload: { resume: File, jobDescription: string }) {
  const form = new FormData()
  form.append('mode', 'jobSeeker')
  form.append('resume', payload.resume)
  form.append('jobDescription', payload.jobDescription)
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form
  })
  if (!res.ok) throw new Error(`Analyze failed: ${res.status}`)
  const data = await res.json()
  
  // Handle async RQ job response
  if (data.job_id) {
    return pollJob(data.job_id)
  }
  // Handle sync response or legacy
  if (data.result) {
    return data.result
  }
  return data
}

export async function analyzeRecruiter(token: string | null, payload: { resume: File, jobDescription: File, recruiterEmail: string }) {
  const form = new FormData()
  form.append('mode', 'recruiter')
  form.append('resume', payload.resume)
  form.append('job_description', payload.jobDescription)
  form.append('recruiterEmail', payload.recruiterEmail)
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form
  })
  if (!res.ok) throw new Error(`Analyze failed: ${res.status}`)
  const data = await res.json()
  
  if (data.job_id) {
    return pollJob(data.job_id)
  }
  if (data.result) {
    return data.result
  }
  return data
}

export async function getHealth(signal?: AbortSignal) {
  const res = await fetch(`${API_BASE}/health`, { signal })
  if (!res.ok) throw new Error('Health check failed')
  return res.json()
}

export async function getVersion(signal?: AbortSignal) {
  const res = await fetch(`${API_BASE}/version`, { signal })
  if (!res.ok) throw new Error('Version check failed')
  return res.json()
}

export async function postLoginWelcome(
  token: string,
  payload: { email?: string | null, displayName?: string | null, phoneNumber?: string | null }
) {
  const res = await fetch(`${API_BASE}/auth/post-login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  })
  if (!res.ok) throw new Error(`Post login failed: ${res.status}`)
  return res.json() as Promise<{ ok: boolean, welcomeEmailSent: boolean, reason?: string }>
}

// Auth-protected coaching APIs (token required; dev mode may accept dummy token)
export async function coachingSaveVersion(token: string, payload: { resume: File, jobDescription?: File | string }) {
  const form = new FormData()
  form.append('resume', payload.resume)
  if (typeof payload.jobDescription === 'string') {
    form.append('jobDescription', payload.jobDescription)
  } else if (payload.jobDescription instanceof File) {
    form.append('job_description', payload.jobDescription)
  }
  const res = await fetch(`${API_BASE}/coaching/save-version`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form
  })
  if (!res.ok) throw new Error(`Save version failed: ${res.status}`)
  return res.json()
}

export async function coachingProgress(token: string) {
  const res = await fetch(`${API_BASE}/coaching/progress`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!res.ok) throw new Error(`Progress failed: ${res.status}`)
  return res.json()
}

export async function coachingStudyPack(token: string) {
  const res = await fetch(`${API_BASE}/coaching/study-pack`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!res.ok) throw new Error(`Study pack failed: ${res.status}`)
  return res.json()
}

export async function coachingInterviewQuestions(token: string, targetRole: string) {
  const url = new URL(`${API_BASE}/coaching/interview-questions`)
  url.searchParams.set('targetRole', targetRole)
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!res.ok) throw new Error(`Interview questions failed: ${res.status}`)
  return res.json()
}

export async function coachingDiff(token: string, prev: number, curr: number) {
  const url = new URL(`${API_BASE}/coaching/diff`)
  url.searchParams.set('prev', String(prev))
  url.searchParams.set('curr', String(curr))
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!res.ok) throw new Error(`Diff failed: ${res.status}`)
  return res.json()
}

export async function generateCoverLetter(token: string | null, payload: { resume: File, jobDescription: string }) {
  const form = new FormData()
  form.append('resume', payload.resume)
  form.append('jobDescription', payload.jobDescription)
  const res = await fetch(`${API_BASE}/generate-cover-letter`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form
  })
  if (!res.ok) throw new Error(`Cover letter generation failed: ${res.status}`)
  return res.json()
}

export async function generateInterviewQuestions(token: string | null, payload: { resume: File, jobDescription: string }) {
  const form = new FormData()
  form.append('resume', payload.resume)
  form.append('jobDescription', payload.jobDescription)
  const res = await fetch(`${API_BASE}/generate-interview-questions`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form
  })
  if (!res.ok) throw new Error(`Question generation failed: ${res.status}`)
  return res.json()
}

export async function analyzeSkills(token: string | null, payload: { resume: File, jobDescription: string }) {
  const form = new FormData()
  form.append('resume', payload.resume)
  form.append('jobDescription', payload.jobDescription)
  const res = await fetch(`${API_BASE}/analyze-skills`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form
  })
  if (!res.ok) throw new Error(`Skill analysis failed: ${res.status}`)
  return res.json()
}

export async function generateEmail(token: string | null, payload: { type: string, candidateName: string, jobTitle: string }) {
  return fetchJsonWithRetry(`${API_BASE}/generate-email`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  }, { retries: 2, baseDelayMs: 600 })
}

export async function mockInterview(token: string | null, payload: { history: any[], message: string, jobContext: string }) {
  const res = await fetch(`${API_BASE}/mock-interview`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  })
  if (!res.ok) throw new Error(`Mock interview failed: ${res.status}`)
  return res.json()
}

export async function generateLinkedInProfile(token: string | null, payload: { resume: File }) {
  const form = new FormData()
  form.append('resume', payload.resume)
  const res = await fetch(`${API_BASE}/generate-linkedin-profile`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form
  })
  if (!res.ok) throw new Error(`LinkedIn profile generation failed: ${res.status}`)
  return res.json()
}

export async function analyzeMockInterview(token: string | null, payload: { history: any[], jobContext: string }) {
  const res = await fetch(`${API_BASE}/analyze-mock-interview`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  })
  if (!res.ok) throw new Error(`Interview analysis failed: ${res.status}`)
  return res.json()
}

export async function estimateSalary(token: string | null, payload: { resume: File, jobDescription: string }) {
  const form = new FormData()
  form.append('resume', payload.resume)
  form.append('jobDescription', payload.jobDescription)
  const res = await fetch(`${API_BASE}/estimate-salary`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form
  })
  if (!res.ok) throw new Error(`Salary estimation failed: ${res.status}`)
  const data = await res.json()
  
  // Salary endpoint is Celery-backed; poll via /tasks.
  if (data.job_id) {
    return pollTask(data.job_id)
  }
  // Handle sync response fallback
  if (data.result) {
    return data.result
  }
  return data
}

export async function tailorResume(token: string | null, payload: { resume: File, jobDescription: string }) {
  const form = new FormData()
  form.append('resume', payload.resume)
  form.append('jobDescription', payload.jobDescription)
  const res = await fetch(`${API_BASE}/tailor-resume`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form
  })
  if (!res.ok) throw new Error(`Resume tailoring failed: ${res.status}`)
  const data = await res.json()
  
  // Tailor endpoint is Celery-backed; poll via /tasks.
  if (data.job_id) {
    return pollTask(data.job_id)
  }
  // Handle sync response fallback
  if (data.result) {
    return data.result
  }
  return data
}

export async function generateCareerPath(token: string | null, payload: { resume: File }) {
  const form = new FormData()
  form.append('resume', payload.resume)
  const res = await fetch(`${API_BASE}/generate-career-path`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form
  })
  if (!res.ok) throw new Error(`Career path generation failed: ${res.status}`)
  const data = await res.json()
  
  // Career path endpoint is Celery-backed; poll via /tasks.
  if (data.job_id) {
    return pollTask(data.job_id)
  }
  // Handle sync response fallback
  if (data.result) {
    return data.result
  }
  return data
}

export async function generateJobDescription(token: string | null, payload: { title: string, skills: string, experience: string }) {
  return fetchJsonWithRetry(`${API_BASE}/generate-job-description`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  }, { retries: 2, baseDelayMs: 600 })
}

export async function resumeHealthCheck(token: string | null, payload: { resume: File }) {
  const form = new FormData()
  form.append('resume', payload.resume)
  const res = await fetch(`${API_BASE}/resume-health-check`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form
  })
  if (!res.ok) throw new Error(`Resume health check failed: ${res.status}`)
  return res.json()
}

export async function generateBooleanSearch(token: string | null, payload: { jobDescription: string }) {
  return fetchJsonWithRetry(`${API_BASE}/generate-boolean-search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  }, { retries: 2, baseDelayMs: 600 })
}

export async function getHistory(token: string) {
  const res = await fetch(`${API_BASE}/history`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!res.ok) throw new Error(`History fetch failed: ${res.status}`)
  return res.json()
}

export async function generateNetworkingMessage(token: string | null, payload: { targetRole: string, company: string, recipientName: string, messageType: string }) {
  return fetchJsonWithRetry(`${API_BASE}/generate-networking-message`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  }, { retries: 2, baseDelayMs: 600 })
}

export type RecruiterTemplateSummary = {
  id: string
  kind: 'email' | 'job_description'
  title: string
  createdAt: string
  updatedAt: string
  latestVersion: number
  preview: string
}

export type RecruiterTemplateVersion = {
  version: number
  createdAt: string
  content: any
  metadata?: Record<string, any>
}

export type RecruiterTemplate = {
  id: string
  kind: 'email' | 'job_description'
  title: string
  createdAt: string
  updatedAt: string
  versions: RecruiterTemplateVersion[]
}

function buildPdfEndpointCandidates(path: string): string[] {
  const cleanBase = API_BASE.replace(/\/+$/, '')
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  const hasApiSuffix = /\/api$/i.test(cleanBase)

  const candidates = [
    `${cleanBase}${cleanPath}`,
    hasApiSuffix
      ? `${cleanBase.replace(/\/api$/i, '')}${cleanPath}`
      : `${cleanBase}/api${cleanPath}`,
  ]

  return Array.from(new Set(candidates))
}

async function fetchPdfWithFallback(path: string, init: RequestInit): Promise<Response> {
  const candidates = buildPdfEndpointCandidates(path)
  let lastResponse: Response | null = null

  for (const url of candidates) {
    const res = await fetch(url, init)
    if (res.ok) return res
    lastResponse = res
    if (res.status !== 404) return res
  }

  return lastResponse as Response
}

export async function listRecruiterTemplates(token: string | null, kind?: 'email' | 'job_description') {
  const url = new URL(`${API_BASE}/recruiter/templates`)
  if (kind) url.searchParams.set('kind', kind)
  const res = await fetch(url.toString(), {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  })
  if (!res.ok) {
    const payload = await readErrorPayload(res)
    throw new ApiError(payload.message, res.status, payload.code, payload.retryAfterSeconds)
  }
  return res.json() as Promise<{ templates: RecruiterTemplateSummary[] }>
}

export async function getRecruiterTemplate(token: string | null, templateId: string) {
  const res = await fetch(`${API_BASE}/recruiter/templates/${templateId}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  })
  if (!res.ok) {
    const payload = await readErrorPayload(res)
    throw new ApiError(payload.message, res.status, payload.code, payload.retryAfterSeconds)
  }
  return res.json() as Promise<{ template: RecruiterTemplate }>
}

export async function saveRecruiterTemplate(
  token: string | null,
  payload: {
    kind: 'email' | 'job_description'
    title: string
    content: any
    metadata?: Record<string, any>
    templateId?: string
  }
) {
  return fetchJsonWithRetry(`${API_BASE}/recruiter/templates`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  }, { retries: 1, baseDelayMs: 500 }) as Promise<{ template: RecruiterTemplate }>
}

// =============================
// PDF Download Functions
// =============================

export async function downloadAnalysisPdf(
  token: string | null,
  result: any,
  mode: 'jobSeeker' | 'recruiter' = 'jobSeeker',
  candidateName: string = 'Candidate'
) {
  const res = await fetchPdfWithFallback('/download/analysis-pdf', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify({
      result,
      mode,
      candidateName
    })
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: `Download failed: ${res.status}` }))
    throw new ApiError(error.error || 'Download failed', res.status)
  }

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `report-${new Date().toISOString().slice(0, 10)}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export async function downloadCoverLetterPdf(
  token: string | null,
  coverLetter: string,
  candidateName: string = ''
) {
  const res = await fetchPdfWithFallback('/download/cover-letter-pdf', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify({
      coverLetter,
      candidateName
    })
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: `Download failed: ${res.status}` }))
    throw new ApiError(error.error || 'Download failed', res.status)
  }

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `cover-letter-${new Date().toISOString().slice(0, 10)}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export async function downloadCoachingReportPdf(
  token: string | null,
  data: any,
  reportType: 'progress' | 'study_pack' | 'interview' = 'progress'
) {
  const res = await fetchPdfWithFallback('/download/coaching-pdf', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify({
      data,
      type: reportType
    })
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: `Download failed: ${res.status}` }))
    throw new ApiError(error.error || 'Download failed', res.status)
  }

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `coaching-${reportType}-${new Date().toISOString().slice(0, 10)}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}


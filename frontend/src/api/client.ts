export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'

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
  return res.json()
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
  return res.json()
}

export async function getHealth() {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error('Health check failed')
  return res.json()
}

export async function getVersion() {
  const res = await fetch(`${API_BASE}/version`)
  if (!res.ok) throw new Error('Version check failed')
  return res.json()
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
  const res = await fetch(`${API_BASE}/generate-email`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  })
  if (!res.ok) throw new Error(`Email generation failed: ${res.status}`)
  return res.json()
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
  return res.json()
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
  return res.json()
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
  return res.json()
}

export async function generateJobDescription(token: string | null, payload: { title: string, skills: string, experience: string }) {
  const res = await fetch(`${API_BASE}/generate-job-description`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  })
  if (!res.ok) throw new Error(`JD generation failed: ${res.status}`)
  return res.json()
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
  const res = await fetch(`${API_BASE}/generate-boolean-search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  })
  if (!res.ok) throw new Error(`Boolean search generation failed: ${res.status}`)
  return res.json()
}

export async function generateNetworkingMessage(token: string | null, payload: { targetRole: string, company: string, recipientName: string, messageType: string }) {
  const res = await fetch(`${API_BASE}/generate-networking-message`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  })
  if (!res.ok) throw new Error(`Networking message generation failed: ${res.status}`)
  return res.json()
}


import { Line } from 'react-chartjs-2'
import { useState } from 'react'
import { Chart as ChartJS, LineElement, PointElement, LinearScale, Title, Tooltip, Legend, CategoryScale } from 'chart.js'

ChartJS.register(LineElement, PointElement, LinearScale, Title, Tooltip, Legend, CategoryScale)

type Version = {
  version: number
  metrics?: { wordCount?: number; skillCoverageRatio?: number }
}

export default function MetricsChart({ versions }: { versions: Version[] }) {
  if (!versions || versions.length === 0) return null
  const labels = versions.map(v => `v${v.version}`)
  const wordCounts = versions.map(v => v.metrics?.wordCount ?? null)
  const coverages = versions.map(v => v.metrics?.skillCoverageRatio ?? null)
  const [showWordCount, setShowWordCount] = useState(true)
  const [showCoverage, setShowCoverage] = useState(true)

  const data = {
    labels,
    datasets: [
      showWordCount ? {
        label: 'Word Count',
        data: wordCounts,
        borderColor: '#4f8cff',
        backgroundColor: 'rgba(79,140,255,0.2)',
        tension: 0.2
      } : undefined,
      showCoverage ? {
        label: 'Skill Coverage',
        data: coverages,
        borderColor: '#97f1b2',
        backgroundColor: 'rgba(151,241,178,0.2)',
        tension: 0.2
      } : undefined
    ].filter(Boolean)
  }

  const options = {
    responsive: true,
    plugins: { legend: { position: 'bottom' as const } },
    scales: { y: { beginAtZero: true } }
  }

  return (
    <div className="card">
      <h3>Version Metrics</h3>
      <div style={{ display:'flex', gap:12, marginBottom:12 }}>
        <label><input type="checkbox" checked={showWordCount} onChange={e => setShowWordCount(e.target.checked)} /> Word Count</label>
        <label><input type="checkbox" checked={showCoverage} onChange={e => setShowCoverage(e.target.checked)} /> Skill Coverage</label>
      </div>
      <Line data={data} options={options} />
    </div>
  )
}

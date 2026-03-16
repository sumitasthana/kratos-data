import { useState } from 'react'

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

const API = '/api'

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', 'X-User-ID': 'demo-user' },
    ...opts,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Minimal shared components
// ---------------------------------------------------------------------------

function StatusBadge({ text, type }) {
  const cls = {
    idle:    'text-gray-400',
    working: 'text-amber-500 animate-pulse',
    ready:   'text-emerald-600',
    error:   'text-red-500',
  }[type] || 'text-gray-400'
  return <span className={`text-sm font-medium ${cls}`}>{text}</span>
}

function DataTable({ columns, rows }) {
  if (!columns || !rows || rows.length === 0) return null
  return (
    <div className="overflow-x-auto rounded border border-gray-200">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            {columns.map(c => (
              <th key={c} className="px-3 py-2 text-left font-semibold text-gray-600 whitespace-nowrap">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
              {columns.map(c => (
                <td key={c} className="px-3 py-2 text-gray-700 whitespace-nowrap font-mono">
                  {String(row[c] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Quality Panel
// ---------------------------------------------------------------------------

const QUALITY_ICON  = { pass: '\u{1F7E2}', warn: '\u{1F7E1}', fail: '\u{1F534}' }
const QUALITY_COLOR = {
  pass: 'text-emerald-700',
  warn: 'text-amber-600',
  fail: 'text-red-600',
}
const DIM_BG = {
  pass: '',
  warn: 'bg-amber-50',
  fail: 'bg-red-50',
}

function QualityPanel({ quality }) {
  if (!quality) return null

  const [review, setReview]       = useState(null)
  const [reviewing, setReviewing] = useState(false)
  const [reviewErr, setReviewErr] = useState('')

  async function handleAiReview() {
    setReviewing(true)
    setReviewErr('')
    setReview(null)
    try {
      const r = await apiFetch('/quality/review', {
        method: 'POST',
        body: JSON.stringify({ quality_report: quality }),
      })
      setReview(r)
    } catch (e) {
      setReviewErr(e.message)
    } finally {
      setReviewing(false)
    }
  }

  const VERDICT_COLOR = {
    'Data is healthy':           'text-emerald-700',
    'Data needs attention':      'text-amber-600',
    'Data has critical issues':  'text-red-600',
  }

  return (
    <section className="mb-8">
      <div className="flex items-center gap-3 mb-3">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">
          Data Quality
        </h2>
        <span className={`text-xs font-semibold ${QUALITY_COLOR[quality.overall] || 'text-gray-500'}`}>
          {QUALITY_ICON[quality.overall]} {quality.summary_line}
        </span>
        <button
          onClick={handleAiReview}
          disabled={reviewing}
          className="ml-auto text-xs px-3 py-1 border border-gray-300 rounded-md
                     text-gray-600 hover:bg-gray-50 active:scale-95 transition-all
                     disabled:opacity-40"
        >
          {reviewing ? 'Reviewing…' : '✦ AI Review'}
        </button>
      </div>
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        {quality.dimensions.map((dim, i) => (
          <div
            key={dim.name}
            className={`px-4 py-3 ${
              i > 0 ? 'border-t border-gray-100' : ''
            } ${DIM_BG[dim.status] || ''}`}
          >
            <div className="flex items-center gap-3">
              <span className="text-base">{QUALITY_ICON[dim.status]}</span>
              <span className="w-32 text-sm font-medium text-gray-700">{dim.name}</span>
              <span className="text-sm text-gray-600">{dim.value}</span>
              <span className="ml-auto text-xs text-gray-400">threshold: {dim.threshold}</span>
            </div>
            {dim.details && dim.details.length > 0 && (
              <div className="mt-2 ml-9 space-y-1">
                {dim.details.map((d, di) => (
                  <p key={di} className="text-xs text-gray-500 leading-relaxed">
                    {d.recommendation}
                  </p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* AI Review result */}
      {reviewErr && (
        <p className="mt-3 text-xs text-red-500">{reviewErr}</p>
      )}
      {review && (
        <div className="mt-4 border border-gray-200 rounded-lg p-5 bg-gray-50 space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">AI Verdict</span>
            <span className={`text-sm font-semibold ${VERDICT_COLOR[review.verdict] || 'text-gray-700'}`}>
              {review.verdict}
            </span>
            {review.config_drift_detected && (
              <span className="ml-auto text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                Config drift detected
              </span>
            )}
          </div>

          <p className="text-sm text-gray-700 leading-relaxed">{review.executive_summary}</p>

          {review.config_drift_explanation && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
              {review.config_drift_explanation}
            </p>
          )}

          {review.dimension_reviews?.some(d => d.diagnosis) && (
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Dimension Diagnoses</p>
              <div className="space-y-2">
                {review.dimension_reviews
                  .filter(d => d.diagnosis)
                  .sort((a, b) => a.priority - b.priority)
                  .map((d, i) => (
                    <div key={i} className="flex gap-2 text-xs text-gray-600">
                      <span className="shrink-0">{QUALITY_ICON[d.status]}</span>
                      <span>
                        <strong>{d.name}</strong>
                        {d.is_false_positive && (
                          <span className="ml-1 text-amber-600 font-medium">(likely false positive)</span>
                        )}
                        {' — '}{d.diagnosis}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {review.top_recommendations?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Top Recommendations</p>
              <ol className="list-decimal list-inside space-y-1">
                {review.top_recommendations.map((rec, i) => (
                  <li key={i} className="text-xs text-gray-600 leading-relaxed">{rec}</li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Page 1: Generate
// ---------------------------------------------------------------------------

function GeneratePage({ onGenerated }) {
  const [status, setStatus] = useState({ text: 'Ready', type: 'idle' })

  async function handleGenerate() {
    setStatus({ text: 'Generating...', type: 'working' })
    const validatingTimer = setTimeout(
      () => setStatus({ text: 'Validating...', type: 'working' }),
      800
    )
    try {
      const data = await apiFetch('/generate', { method: 'POST' })
      clearTimeout(validatingTimer)
      setStatus({ text: 'Ready', type: 'idle' })
      onGenerated(data)
    } catch (e) {
      clearTimeout(validatingTimer)
      setStatus({ text: e.message, type: 'error' })
    }
  }

  return (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center gap-8 px-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Kratos Data</h1>
        <p className="text-sm text-gray-400 mt-1">FDIC Part 370 / Part 330 — Atomic Deposit System</p>
      </div>

      <button
        onClick={handleGenerate}
        disabled={status.type === 'working'}
        className="px-10 py-4 bg-gray-900 text-white text-base font-semibold rounded-xl
                   hover:bg-gray-700 active:scale-95 transition-all
                   disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
      >
        Generate Data
      </button>

      <StatusBadge text={status.text} type={status.type} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page 2: Preview + Download + Records
// ---------------------------------------------------------------------------

function PreviewPage({ data, onBack }) {
  const [toast, setToast]           = useState('')
  const [records, setRecords]       = useState(null)
  const [recLoading, setRecLoading] = useState(false)
  const [recError, setRecError]     = useState('')

  const hasFail = data.quality_report?.overall === 'fail'

  function showToast(msg) {
    setToast(msg)
    setTimeout(() => setToast(''), 2500)
  }

  function handleDownload() {
    const url = `${API}/generate/${data.token}/csv`
    const a   = document.createElement('a')
    a.href    = url
    a.download = `kratos_data_${data.generated_at}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    showToast('Download started')
  }

  async function handleViewRecords() {
    setRecLoading(true)
    setRecError('')
    try {
      const r = await apiFetch('/records?limit=100')
      setRecords(r)
    } catch (e) {
      setRecError(e.message)
    } finally {
      setRecLoading(false)
    }
  }

  async function handleRefresh() {
    setRecLoading(true)
    setRecError('')
    try {
      const r = await apiFetch('/records?limit=100')
      setRecords(r)
    } catch (e) {
      setRecError(e.message)
    } finally {
      setRecLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-white px-6 py-10 max-w-6xl mx-auto">

      {/* Toast */}
      {toast && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 bg-gray-900 text-white text-sm px-5 py-2 rounded-full shadow-md z-50">
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-bold text-gray-900 tracking-tight">Kratos Data</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            {data.total_rows.toLocaleString()} rows &times; {data.columns.length} columns &middot; {data.generated_at}
          </p>
        </div>
        <button
          onClick={onBack}
          className="text-sm text-gray-400 hover:text-gray-700 underline underline-offset-2"
        >
          &larr; Back
        </button>
      </div>

      {/* Preview */}
      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Preview &mdash; first {data.preview_rows.length} rows
        </h2>
        <DataTable columns={data.columns} rows={data.preview_rows} />
      </section>

      {/* Quality Panel */}
      <QualityPanel quality={data.quality_report} />

      {/* CSV quality warning */}
      {hasFail && (
        <p className="mb-3 text-sm text-red-600 font-medium">
          Quality issues detected &mdash; review recommendations before downloading.
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-3 mb-10">
        <button
          onClick={handleDownload}
          className="px-6 py-2.5 bg-gray-900 text-white text-sm font-medium rounded-lg
                     hover:bg-gray-700 active:scale-95 transition-all shadow-sm"
        >
          Download CSV
        </button>
        <button
          onClick={handleViewRecords}
          disabled={recLoading}
          className="px-6 py-2.5 border border-gray-300 text-gray-700 text-sm font-medium
                     rounded-lg hover:bg-gray-50 active:scale-95 transition-all
                     disabled:opacity-40"
        >
          {recLoading ? 'Loading...' : 'View Stored Records'}
        </button>
      </div>

      {/* Stored records */}
      {(records || recError) && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">
                Stored Records {records ? `— ${records.total} rows` : ''}
              </h2>
              {records?.quality_summary && (
                <p className="text-xs text-gray-400 mt-0.5">{records.quality_summary}</p>
              )}
            </div>
            {records && (
              <button
                onClick={handleRefresh}
                disabled={recLoading}
                className="text-xs text-gray-400 hover:text-gray-700 underline underline-offset-2"
              >
                {recLoading ? 'Refreshing...' : 'Refresh'}
              </button>
            )}
          </div>
          {recError && <p className="text-sm text-red-500">{recError}</p>}
          {records && <DataTable columns={records.columns} rows={records.rows} />}
        </section>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------

export default function App() {
  const [generated, setGenerated] = useState(null)

  if (generated) {
    return <PreviewPage data={generated} onBack={() => setGenerated(null)} />
  }
  return <GeneratePage onGenerated={setGenerated} />
}
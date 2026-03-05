import { useState } from 'react'

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

const API = '/api'
const HEADERS = { 'Content-Type': 'application/json', 'X-User-ID': 'demo-user' }

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: HEADERS,
    ...opts,
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = json?.detail
      ? typeof json.detail === 'string'
        ? json.detail
        : JSON.stringify(json.detail)
      : `HTTP ${res.status}`
    throw new Error(msg)
  }
  return json
}

function fmt(val) {
  if (val == null) return '—'
  if (typeof val === 'number') return val.toLocaleString()
  return String(val)
}

function fmtUSD(val) {
  if (val == null) return '—'
  return Number(val).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

// ---------------------------------------------------------------------------
// Small UI atoms
// ---------------------------------------------------------------------------

function Banner({ type, children }) {
  const styles = {
    success: 'bg-green-50 border border-green-300 text-green-800',
    error:   'bg-red-50 border border-red-300 text-red-800',
    info:    'bg-blue-50 border border-blue-300 text-blue-800',
  }
  return (
    <div className={`rounded-lg p-4 text-sm font-medium mt-4 ${styles[type] ?? styles.info}`}>
      {children}
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
        {label}
      </label>
      {children}
    </div>
  )
}

const inputCls =
  'border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 w-full'

function Input({ ...props }) {
  return <input className={inputCls} {...props} />
}

function Select({ children, ...props }) {
  return (
    <select className={inputCls} {...props}>
      {children}
    </select>
  )
}

function Button({ loading, children, ...props }) {
  return (
    <button
      className="mt-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition-colors"
      disabled={loading}
      {...props}
    >
      {loading ? 'Working…' : children}
    </button>
  )
}

function InfoRow({ label, value, highlight }) {
  return (
    <div className="flex justify-between py-1 border-b border-gray-100 last:border-0">
      <span className="text-xs text-gray-500 font-medium">{label}</span>
      <span className={`text-sm font-semibold ${highlight ?? 'text-gray-800'}`}>{value}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 1 — Create Party
// ---------------------------------------------------------------------------

function CreatePartyTab({ onPartyCreated }) {
  const [f, setF] = useState({
    given: '', family: '', ssn: '', dob: '', city: '', state: '',
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const update = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const body = {
        party_type:               'Individual',
        party_status:             'Active',
        individual_name_given:    f.given,
        individual_name_family:   f.family,
        individual_ssn:           f.ssn.replace(/\D/g, ''),
        individual_date_of_birth: f.dob || null,
        address_city:             f.city || null,
        address_state_province:   f.state || null,
        address_country:          'US',
        created_by:               'demo-user',
      }
      const data = await apiFetch('/parties', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      setResult(data)
      onPartyCreated(data.party_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-xl">
      <h2 className="text-lg font-bold text-gray-800 mb-1">Create Individual Party</h2>
      <p className="text-xs text-gray-500 mb-5">
        Per FinCEN CIP (31 U.S.C. § 5318): customer identification before account opening.
      </p>
      <form onSubmit={submit} className="grid grid-cols-2 gap-4">
        <Field label="Given Name *">
          <Input value={f.given} onChange={update('given')} placeholder="Alice" required />
        </Field>
        <Field label="Family Name *">
          <Input value={f.family} onChange={update('family')} placeholder="Walker" required />
        </Field>
        <Field label="SSN (9 digits) *">
          <Input
            value={f.ssn}
            onChange={update('ssn')}
            placeholder="123456789"
            maxLength={9}
            pattern="\d{9}"
            title="Exactly 9 digits"
            required
            type="password"
            autoComplete="off"
          />
        </Field>
        <Field label="Date of Birth">
          <Input value={f.dob} onChange={update('dob')} type="date" />
        </Field>
        <Field label="City">
          <Input value={f.city} onChange={update('city')} placeholder="New York" />
        </Field>
        <Field label="State (2-letter)">
          <Input value={f.state} onChange={update('state')} placeholder="NY" maxLength={2} />
        </Field>
        <div className="col-span-2">
          <Button loading={loading} type="submit">Create Party</Button>
        </div>
      </form>

      {result && (
        <Banner type="success">
          <p className="font-bold text-base mb-1">
            Party created: {result.individual_name_given} {result.individual_name_family}
          </p>
          <p className="text-xs break-all">Party ID: <span className="font-mono">{result.party_id}</span></p>
          <p className="text-xs mt-1 text-green-600">
            ✓ This Party ID has been pre-filled in the "Open Account" tab.
          </p>
        </Banner>
      )}
      {error && <Banner type="error">{error}</Banner>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 2 — Open Account
// ---------------------------------------------------------------------------

const ACCOUNT_TYPE_MAP = {
  Savings:   'Savings',
  Checking:  'Checking',
  'Money Market': 'Money Market',
  'Certificate of Deposit': 'Certificate of Deposit',
  IRA:       'Individual Retirement Account',
  Trust:     'Trust Account',
  Government:'Government Account',
  Business:  'Business Account',
}

function OpenAccountTab({ prefillPartyId }) {
  const today = new Date().toISOString().slice(0, 10)
  const [f, setF] = useState({
    partyId: prefillPartyId || '',
    acctNum: '',
    acctType: 'Savings',
    balance: '10000.00',
    openDate: today,
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // Keep partyId in sync when parent passes new value
  if (prefillPartyId && f.partyId !== prefillPartyId && f.partyId === '') {
    setF((p) => ({ ...p, partyId: prefillPartyId }))
  }

  const update = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const accountType = ACCOUNT_TYPE_MAP[f.acctType] ?? f.acctType
      // Step 1 — create account (creates ownership + ORC + insurance internally)
      const acct = await apiFetch('/accounts', {
        method: 'POST',
        body: JSON.stringify({
          account_number:           f.acctNum,
          account_type:             accountType,
          account_open_date:        f.openDate,
          primary_owner_party_id:   f.partyId,
          current_balance:          parseFloat(f.balance),
          current_balance_date:     f.openDate,
          interest_rate_percentage: 0.025,
          minimum_balance:          0,
        }),
      })
      // Step 2 — fetch insurance calculation
      const ins = await apiFetch(`/accounts/${acct.account_id}/insurance`)
      setResult({ acct, ins })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const { acct, ins } = result ?? {}
  const fullyInsured = ins && Number(ins.calculated_uninsured_amount) === 0

  return (
    <div className="max-w-xl">
      <h2 className="text-lg font-bold text-gray-800 mb-1">Open Deposit Account</h2>
      <p className="text-xs text-gray-500 mb-5">
        Per FDIC Part 370 § 370.3(b): ORC is auto-assigned and coverage calculated at opening.
      </p>
      <form onSubmit={submit} className="grid grid-cols-2 gap-4">
        <Field label="Party ID (owner) *">
          <Input
            value={f.partyId}
            onChange={update('partyId')}
            placeholder="UUID from Create Party"
            required
          />
        </Field>
        <Field label="Account Number *">
          <Input
            value={f.acctNum}
            onChange={update('acctNum')}
            placeholder="CHK-000123"
            required
            maxLength={20}
          />
        </Field>
        <Field label="Account Type *">
          <Select value={f.acctType} onChange={update('acctType')}>
            {Object.keys(ACCOUNT_TYPE_MAP).map((k) => (
              <option key={k} value={k}>{k}</option>
            ))}
          </Select>
        </Field>
        <Field label="Opening Balance ($)">
          <Input
            value={f.balance}
            onChange={update('balance')}
            type="number"
            min="0"
            step="0.01"
          />
        </Field>
        <Field label="Open Date">
          <Input value={f.openDate} onChange={update('openDate')} type="date" />
        </Field>
        <div className="col-span-2">
          <Button loading={loading} type="submit">Open Account &amp; Calculate Coverage</Button>
        </div>
      </form>

      {acct && ins && (
        <Banner type={fullyInsured ? 'success' : 'info'}>
          <p className="font-bold text-base mb-3">
            Account opened {fullyInsured ? '✓ Fully Insured' : '⚠ Partially Insured'}
          </p>
          <div className="space-y-1">
            <InfoRow label="Account ID"   value={acct.account_id} />
            <InfoRow label="Account No."  value={acct.account_number} />
            <InfoRow label="Type"         value={acct.account_type} />
            <InfoRow label="ORC Code"     value={acct.orc_code} />
            <InfoRow label="Balance"      value={fmtUSD(acct.current_balance)} />
            <InfoRow
              label="Insured Amount"
              value={fmtUSD(ins.calculated_insured_amount)}
              highlight="text-green-700"
            />
            <InfoRow
              label="Uninsured Amount"
              value={fmtUSD(ins.calculated_uninsured_amount)}
              highlight={!fullyInsured ? 'text-yellow-700' : 'text-gray-800'}
            />
          </div>
        </Banner>
      )}
      {error && <Banner type="error">{error}</Banner>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 3 — Insurance Summary
// ---------------------------------------------------------------------------

function InsuranceSummaryTab() {
  const [accountId, setAccountId] = useState('')
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [acctData, setAcctData] = useState(null)
  const [error, setError] = useState(null)

  async function fetch_(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setData(null)
    setAcctData(null)
    try {
      const [ins, acct] = await Promise.all([
        apiFetch(`/accounts/${accountId}/insurance`),
        apiFetch(`/accounts/${accountId}`),
      ])
      setData(ins)
      setAcctData(acct)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fullyInsured = data && Number(data.calculated_uninsured_amount) === 0
  const partiallyInsured = data && !fullyInsured && Number(data.calculated_insured_amount) > 0

  return (
    <div className="max-w-xl">
      <h2 className="text-lg font-bold text-gray-800 mb-1">Insurance Summary</h2>
      <p className="text-xs text-gray-500 mb-5">
        Per FDIC Part 370 § 370.3: coverage must be determinable on demand.
      </p>
      <form onSubmit={fetch_} className="flex gap-3 items-end">
        <Field label="Account ID (UUID)">
          <Input
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            pattern="[0-9a-fA-F-]{36}"
            required
            style={{ width: '340px' }}
          />
        </Field>
        <Button loading={loading} type="submit">Fetch</Button>
      </form>

      {data && acctData && (
        <div className={`mt-5 rounded-xl border-2 p-5 ${
          fullyInsured
            ? 'border-green-300 bg-green-50'
            : partiallyInsured
            ? 'border-yellow-300 bg-yellow-50'
            : 'border-red-300 bg-red-50'
        }`}>
          <div className="flex items-center justify-between mb-4">
            <span className="font-bold text-gray-800 text-base">
              {acctData.account_number}
            </span>
            <span className={`text-xs font-semibold px-3 py-1 rounded-full ${
              fullyInsured
                ? 'bg-green-200 text-green-800'
                : partiallyInsured
                ? 'bg-yellow-200 text-yellow-800'
                : 'bg-red-200 text-red-800'
            }`}>
              {fullyInsured ? 'FULLY INSURED' : partiallyInsured ? 'PARTIALLY INSURED' : 'UNINSURED'}
            </span>
          </div>
          <div className="space-y-1">
            <InfoRow label="Account Type"    value={acctData.account_type} />
            <InfoRow label="ORC Code"        value={data.input_orc} />
            <InfoRow label="Current Balance" value={fmtUSD(acctData.current_balance)} />
            <InfoRow label="Owners"          value={data.input_owner_count} />
            {data.beneficiary_count != null && (
              <InfoRow label="Beneficiaries" value={data.beneficiary_count} />
            )}
            <InfoRow
              label="Insured Amount"
              value={fmtUSD(data.calculated_insured_amount)}
              highlight="text-green-700"
            />
            <InfoRow
              label="Uninsured Amount"
              value={fmtUSD(data.calculated_uninsured_amount)}
              highlight={!fullyInsured ? 'text-yellow-700' : 'text-gray-400'}
            />
            <InfoRow label="Test Result"   value={data.calculation_test_result} />
            <InfoRow label="Calc Date"     value={data.calculation_date} />
            {data.calculation_basis_description && (
              <div className="pt-2 text-xs text-gray-500 italic">
                {data.calculation_basis_description}
              </div>
            )}
          </div>
        </div>
      )}
      {error && <Banner type="error">{error}</Banner>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 4 — Audit Log
// ---------------------------------------------------------------------------

const AUDIT_TABLES = ['party', 'account', 'account_ownership',
  'account_regulatory_classification', 'deposit_insurance_calculation']

function AuditLogTab() {
  const [tableName, setTableName] = useState('party')
  const [recordId, setRecordId] = useState('')
  const [loading, setLoading] = useState(false)
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)

  async function fetch_(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setRows(null)
    try {
      const data = await apiFetch(`/audit-log/${tableName}/${recordId}`)
      setRows(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 className="text-lg font-bold text-gray-800 mb-1">Audit Log</h2>
      <p className="text-xs text-gray-500 mb-5">
        Per FDIC Part 370 § 370.3 &amp; 12 U.S.C. § 1831p-1: all data changes are captured.
      </p>
      <form onSubmit={fetch_} className="flex flex-wrap gap-3 items-end">
        <Field label="Table">
          <Select value={tableName} onChange={(e) => setTableName(e.target.value)} style={{ width: '220px' }}>
            {AUDIT_TABLES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </Select>
        </Field>
        <Field label="Record ID (UUID)">
          <Input
            value={recordId}
            onChange={(e) => setRecordId(e.target.value)}
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            pattern="[0-9a-fA-F-]{36}"
            required
            style={{ width: '340px' }}
          />
        </Field>
        <Button loading={loading} type="submit">Fetch Log</Button>
      </form>

      {rows !== null && (
        <div className="mt-5">
          {rows.length === 0 ? (
            <Banner type="info">No audit log entries found for this record.</Banner>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full text-xs">
                <thead className="bg-gray-50 text-gray-500 uppercase tracking-wide">
                  <tr>
                    {['Event Time','Operation','Column','Old Value','New Value','Changed By'].map((h) => (
                      <th key={h} className="px-3 py-2 text-left font-semibold whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {rows.map((r) => (
                    <tr key={r.audit_log_id} className="hover:bg-gray-50">
                      <td className="px-3 py-2 whitespace-nowrap text-gray-500 font-mono">
                        {new Date(r.changed_date).toLocaleString()}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded-full font-semibold ${
                          r.change_type === 'INSERT'
                            ? 'bg-green-100 text-green-700'
                            : r.change_type === 'UPDATE'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-red-100 text-red-700'
                        }`}>
                          {r.change_type}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-mono text-gray-700">{fmt(r.column_name)}</td>
                      <td className="px-3 py-2 text-gray-500 max-w-xs truncate" title={r.old_value ?? ''}>
                        {fmt(r.old_value)}
                      </td>
                      <td className="px-3 py-2 text-gray-800 max-w-xs truncate" title={r.new_value ?? ''}>
                        {fmt(r.new_value)}
                      </td>
                      <td className="px-3 py-2 text-gray-600">{fmt(r.changed_by)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-gray-400 px-3 py-2 border-t border-gray-100">
                {rows.length} row{rows.length !== 1 ? 's' : ''} — newest first
              </p>
            </div>
          )}
        </div>
      )}
      {error && <Banner type="error">{error}</Banner>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Root App
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'party',     label: '1  Create Party' },
  { id: 'account',   label: '2  Open Account' },
  { id: 'insurance', label: '3  Insurance Summary' },
  { id: 'audit',     label: '4  Audit Log' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('party')
  const [lastPartyId, setLastPartyId] = useState('')

  function handlePartyCreated(id) {
    setLastPartyId(id)
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-indigo-700 text-white shadow-lg">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Kratos Data</h1>
            <p className="text-xs text-indigo-200 mt-0.5">
              FDIC Part 370 / Part 330 — Atomic Deposit System
            </p>
          </div>
          <span className="text-xs bg-indigo-800 px-3 py-1 rounded-full text-indigo-200 font-mono">
            demo-user
          </span>
        </div>
      </header>

      {/* Tab bar */}
      <div className="max-w-5xl mx-auto px-6 mt-6">
        <div className="flex gap-1 bg-white rounded-xl p-1 shadow-sm border border-gray-200 w-fit">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                activeTab === t.id
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          {activeTab === 'party' && (
            <CreatePartyTab onPartyCreated={handlePartyCreated} />
          )}
          {activeTab === 'account' && (
            <OpenAccountTab prefillPartyId={lastPartyId} />
          )}
          {activeTab === 'insurance' && <InsuranceSummaryTab />}
          {activeTab === 'audit'     && <AuditLogTab />}
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center text-xs text-gray-400 py-6">
        Kratos Data — FDIC Part 370 Compliant Demo &nbsp;·&nbsp; API on{' '}
        <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer"
           className="text-indigo-500 hover:underline">
          localhost:8000/docs
        </a>
      </footer>
    </div>
  )
}

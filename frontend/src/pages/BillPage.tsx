import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, money, type Bill, type Share } from '../api'
import { Button, Card, ErrorNote, Page, Spinner } from '../components/ui'

const POLL_MS = 4000

export default function BillPage() {
  const { billId = '' } = useParams()
  const [bill, setBill] = useState<Bill | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(() => api.bill(billId).then(setBill).catch((err) => setError(err.message)), [billId])
  useEffect(() => { load() }, [load])

  // watch for friends paying while there is anything left to collect
  const waiting = bill?.shares.some((share) => share.status === 'pending')
  useEffect(() => {
    if (!waiting) return
    const timer = setInterval(load, POLL_MS)
    return () => clearInterval(timer)
  }, [waiting, load])

  if (!bill) return <Page>{error ? <ErrorNote message={error} /> : <Spinner label="Loading bill…" />}</Page>
  return (
    <Page>
      <div className="grid gap-5">
        <ReceiptCard bill={bill} />
        <SplitForm bill={bill} onSplit={setBill} />
        {bill.shares.length > 0 && <Shares bill={bill} />}
      </div>
    </Page>
  )
}

function ReceiptCard({ bill }: { bill: Bill }) {
  const { receipt } = bill
  const [open, setOpen] = useState(false)
  const shown = open ? receipt.items : receipt.items.slice(0, 4)
  return (
    <Card>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-2xl font-extrabold">{receipt.merchant}</h2>
        <span className="text-2xl font-bold">{money(receipt.total, bill.currency)}</span>
      </div>
      <ul className="mt-4 divide-y divide-ink/5 text-sm">
        {shown.map((item, index) => (
          <li key={index} className="flex justify-between gap-4 py-2">
            <span>{item.quantity !== 1 && <span className="text-ink/50">{item.quantity}× </span>}{item.name}</span>
            <span className="tabular-nums">{money(item.line_total, bill.currency)}</span>
          </li>
        ))}
      </ul>
      {receipt.items.length > 4 && (
        <button onClick={() => setOpen(!open)} className="mt-1 text-sm font-semibold text-brand">
          {open ? 'Show less' : `Show all ${receipt.items.length} items`}
        </button>
      )}
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-ink/60">
        <span>Tax {money(receipt.tax, bill.currency)}</span>
        <span>Tip {money(receipt.tip, bill.currency)}</span>
        {receipt.currency !== bill.currency && <span>Collected in {bill.currency} (PayPal doesn't settle {receipt.currency})</span>}
      </div>
      {receipt.warnings.map((warning) => (
        <p key={warning} className="mt-3 rounded-2xl bg-amber-50 px-4 py-2 text-sm text-amber-800">⚠️ {warning}</p>
      ))}
    </Card>
  )
}

function SplitForm({ bill, onSplit }: { bill: Bill; onSplit: (bill: Bill) => void }) {
  const [people, setPeople] = useState<string[]>(bill.people.length ? bill.people : [])
  const [name, setName] = useState('')
  const [payer, setPayer] = useState(bill.payer ?? '')
  const [payeeEmail, setPayeeEmail] = useState(bill.payee_email ?? '')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const locked = bill.shares.some((share) => share.status === 'paid')
  const split = bill.shares.length > 0

  function addPerson() {
    const clean = name.trim()
    if (clean && !people.some((p) => p.toLowerCase() === clean.toLowerCase())) setPeople([...people, clean])
    if (!payer && clean) setPayer(clean)
    setName('')
  }

  async function submit() {
    setBusy(true)
    setError('')
    const story = message.trim() ? [...bill.story, message.trim()] : bill.story
    try {
      onSplit(await api.split(bill.id, { people, payer, payee_email: payeeEmail || null, story }))
      setMessage('')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (locked) return null
  return (
    <Card>
      <h3 className="text-lg font-bold">{split ? 'Something not right? Just say so.' : 'Who was there?'}</h3>
      {!split && (
        <>
          <div className="mt-3 flex flex-wrap gap-2">
            {people.map((person) => (
              <span key={person} className="flex items-center gap-1 rounded-full bg-brand-soft px-3 py-1.5 text-sm font-medium">
                {person}
                <button aria-label={`Remove ${person}`} className="text-ink/40 hover:text-ink" onClick={() => setPeople(people.filter((p) => p !== person))}>×</button>
              </span>
            ))}
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ',') { event.preventDefault(); addPerson() } }}
              onBlur={addPerson}
              placeholder="Add a name + Enter"
              className="min-w-40 flex-1 rounded-full border border-ink/10 px-4 py-1.5 text-sm outline-none focus:border-brand"
            />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              <span className="font-medium">Who paid the bill?</span>
              <select value={payer} onChange={(event) => setPayer(event.target.value)} className="mt-1 w-full rounded-2xl border border-ink/10 bg-white px-3 py-2.5">
                <option value="" disabled>Pick a person</option>
                {people.map((person) => <option key={person}>{person}</option>)}
              </select>
            </label>
            <label className="text-sm">
              <span className="font-medium">Their PayPal email <span className="text-ink/50">(money goes here)</span></span>
              <input value={payeeEmail} onChange={(event) => setPayeeEmail(event.target.value)} type="email" placeholder="optional"
                className="mt-1 w-full rounded-2xl border border-ink/10 px-3 py-2.5 outline-none focus:border-brand" />
            </label>
          </div>
        </>
      )}
      {split && bill.story.length > 0 && (
        <ul className="mt-3 space-y-2">
          {bill.story.map((line, index) => (
            <li key={index} className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-brand px-4 py-2 text-sm text-white">{line}</li>
          ))}
        </ul>
      )}
      <textarea
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        rows={split ? 2 : 3}
        placeholder={split ? 'e.g. “Actually Mia didn’t have any wine” or “Add a 15% tip”' : 'e.g. “I had the pasta, Raj got the steak, we all shared the wine and bread”'}
        className="mt-4 w-full rounded-2xl border border-ink/10 px-4 py-3 outline-none focus:border-brand"
      />
      {error && <div className="mt-3"><ErrorNote message={error} /></div>}
      <div className="mt-3 flex items-center gap-4">
        <Button onClick={submit} disabled={busy || people.length < 2 || !payer || (split && !message.trim())}>
          {split ? 'Update the split' : 'Split it ✨'}
        </Button>
        {busy && <Spinner label="Working out who owes what…" />}
      </div>
    </Card>
  )
}

function Shares({ bill }: { bill: Bill }) {
  const owing = bill.shares.filter((share) => share.status !== 'payer')
  const total = owing.reduce((sum, share) => sum + share.amount, 0)
  const collected = owing.filter((share) => share.status === 'paid').reduce((sum, share) => sum + share.amount, 0)
  const percent = total ? Math.round((collected / total) * 100) : 100
  return (
    <>
      {bill.plan && (
        <Card className="bg-brand-soft/60">
          <div className="text-sm font-semibold text-brand">How I split it</div>
          <p className="mt-1">{bill.plan.summary}</p>
          {bill.plan.questions.map((question) => (
            <p key={question} className="mt-2 rounded-2xl bg-white px-4 py-2 text-sm">🤔 {question}</p>
          ))}
        </Card>
      )}
      <Card>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-lg font-bold">{bill.payer} gets back</h3>
          <span className="text-sm text-ink/60">{money(collected, bill.currency)} of {money(total, bill.currency)} collected</span>
        </div>
        <div className="mt-3 h-3 overflow-hidden rounded-full bg-ink/5">
          <div className="h-full rounded-full bg-mint transition-all duration-700" style={{ width: `${percent}%` }} />
        </div>
      </Card>
      <div className="grid gap-4 sm:grid-cols-2">
        {bill.shares.map((share) => <ShareCard key={share.id} share={share} currency={bill.currency} />)}
      </div>
    </>
  )
}

function ShareCard({ share, currency }: { share: Share; currency: string }) {
  const [copied, setCopied] = useState(false)
  const link = `${window.location.origin}/pay/${share.id}`

  function copy() {
    navigator.clipboard.writeText(`${share.note}\nPay your ${money(share.amount, currency)} here: ${link}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Card className={share.status === 'paid' ? 'ring-2 ring-mint' : ''}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-bold">{share.person}</div>
          <StatusBadge status={share.status} />
        </div>
        <div className="text-2xl font-bold tabular-nums">{money(share.amount, currency)}</div>
      </div>
      <ul className="mt-3 space-y-1 text-sm">
        {share.items.map((item, index) => (
          <li key={index} className="flex justify-between gap-3" title={item.reason}>
            <span className="text-ink/80">{item.name}{item.shared_with.length > 0 && <span className="text-ink/40"> · shared</span>}</span>
            <span className="tabular-nums">{money(item.amount, currency)}</span>
          </li>
        ))}
        <li className="flex justify-between gap-3 text-ink/50">
          <span>Tax, tip & extras</span>
          <span className="tabular-nums">{money(share.extras, currency)}</span>
        </li>
      </ul>
      {share.note && <p className="mt-3 text-sm italic text-ink/60">“{share.note}”</p>}
      {share.status === 'pending' && (
        <div className="mt-4 flex gap-2">
          <button onClick={copy} className="flex-1 rounded-2xl bg-ink px-3 py-2 text-sm font-semibold text-white">
            {copied ? 'Copied!' : 'Copy pay link'}
          </button>
          <a href={link} target="_blank" rel="noreferrer" className="rounded-2xl border border-ink/10 px-3 py-2 text-sm font-semibold">Open</a>
        </div>
      )}
    </Card>
  )
}

function StatusBadge({ status }: { status: Share['status'] }) {
  const styles = { paid: 'bg-mint/15 text-mint', pending: 'bg-amber-100 text-amber-800', payer: 'bg-brand-soft text-brand' }
  const labels = { paid: '✓ Paid', pending: 'Waiting', payer: 'Paid the bill' }
  return <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${styles[status]}`}>{labels[status]}</span>
}

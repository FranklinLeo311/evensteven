import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Card, ErrorNote, Page, Spinner } from '../components/ui'

const STEPS = [
  ['📸', 'Snap the receipt', 'AI reads every line, the tax and the tip.'],
  ['💬', 'Say who had what', '“I had the pasta, Raj and Mia shared the wine.”'],
  ['💸', 'Everyone pays with PayPal', 'Each friend gets a link for their exact share.'],
]

export default function HomePage() {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function upload(file: File) {
    setBusy(true)
    setError('')
    try {
      const bill = await api.uploadReceipt(file)
      navigate(`/bill/${bill.id}`)
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  async function useSample() {
    const blob = await (await fetch('/sample-receipt.png')).blob()
    upload(new File([blob], 'sample-receipt.png', { type: 'image/png' }))
  }

  return (
    <Page>
      <div className="py-8 text-center sm:py-12">
        <h1 className="font-display text-4xl font-extrabold leading-tight sm:text-6xl">
          Split the bill<br />by just <span className="text-brand">talking</span>.
        </h1>
        <p className="mx-auto mt-4 max-w-md text-lg text-ink/70">
          No spreadsheets, no awkward maths. Tell EvenSteven what everyone ate and it collects the money through PayPal.
        </p>
      </div>

      <Card className="text-center">
        {busy ? (
          <div className="flex justify-center py-10"><Spinner label="Reading your receipt…" /></div>
        ) : (
          <>
            <label className="block cursor-pointer rounded-2xl border-2 border-dashed border-brand/30 bg-brand-soft/40 px-4 py-10 transition hover:border-brand">
              <div className="text-5xl">🧾</div>
              <div className="mt-3 text-lg font-semibold">Upload or take a photo of the receipt</div>
              <div className="text-sm text-ink/60">JPG, PNG, WEBP or PDF</div>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,application/pdf"
                className="hidden"
                onChange={(event) => event.target.files?.[0] && upload(event.target.files[0])}
              />
            </label>
            <button onClick={useSample} className="mt-4 text-sm font-semibold text-brand hover:underline">
              No receipt handy? Try a sample one
            </button>
          </>
        )}
        {error && <div className="mt-4"><ErrorNote message={error} /></div>}
      </Card>

      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {STEPS.map(([icon, title, text]) => (
          <div key={title} className="rounded-3xl bg-white/60 p-5">
            <div className="text-3xl">{icon}</div>
            <div className="mt-2 font-semibold">{title}</div>
            <div className="text-sm text-ink/60">{text}</div>
          </div>
        ))}
      </div>
    </Page>
  )
}

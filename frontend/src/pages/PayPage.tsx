import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, money, type AppConfig, type ShareView } from '../api'
import PayPalButtons from '../components/PayPalButtons'
import { Card, ErrorNote, Page, Spinner } from '../components/ui'

export default function PayPage() {
  const { shareId = '' } = useParams()
  const [view, setView] = useState<ShareView | null>(null)
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.share(shareId), api.config()])
      .then(([shareView, appConfig]) => { setView(shareView); setConfig(appConfig) })
      .catch((err) => setError(err.message))
  }, [shareId])

  if (!view || !config) return <Page>{error ? <ErrorNote message={error} /> : <Spinner label="Loading…" />}</Page>
  const { share, currency, merchant, payer } = view

  async function createOrder() {
    setError('')
    try {
      return (await api.createOrder(share.id)).order_id
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function approve(orderId: string) {
    try {
      await api.capture(share.id, orderId)
      setView({ ...view!, share: { ...share, status: 'paid' } })
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <Page>
      <Card className="mx-auto max-w-md text-center">
        <div className="text-sm text-ink/60">Hi {share.person} 👋</div>
        <h1 className="mt-1 font-display text-2xl font-extrabold">{payer} covered {merchant}</h1>
        {share.note && <p className="mt-2 italic text-ink/70">“{share.note}”</p>}
        <div className="my-6 text-5xl font-extrabold tabular-nums">{money(share.amount, currency)}</div>
        <ul className="mb-6 space-y-1 text-left text-sm">
          {share.items.map((item, index) => (
            <li key={index} className="flex justify-between gap-3">
              <span>{item.name}{item.shared_with.length > 0 && <span className="text-ink/40"> · with {item.shared_with.join(', ')}</span>}</span>
              <span className="tabular-nums">{money(item.amount, currency)}</span>
            </li>
          ))}
          <li className="flex justify-between gap-3 text-ink/50">
            <span>Your share of tax, tip & extras</span>
            <span className="tabular-nums">{money(share.extras, currency)}</span>
          </li>
        </ul>
        {share.status === 'paid' && (
          <div className="rounded-2xl bg-mint/10 px-4 py-6">
            <div className="text-4xl">🎉</div>
            <div className="mt-2 text-lg font-bold text-mint">Paid — you're all square with {payer}!</div>
          </div>
        )}
        {share.status === 'payer' && <p className="text-ink/60">You paid the bill, so there is nothing to pay here.</p>}
        {share.status === 'pending' && (
          config.paypal_ready
            ? <PayPalButtons clientId={config.paypal_client_id} currency={currency} createOrder={createOrder} onApprove={approve} />
            : <ErrorNote message="PayPal isn't set up on this server yet." />
        )}
        {error && <div className="mt-3"><ErrorNote message={error} /></div>}
      </Card>
    </Page>
  )
}

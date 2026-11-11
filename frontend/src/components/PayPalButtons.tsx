import { useEffect, useRef, useState } from 'react'

interface PayPalNamespace {
  Buttons: (options: {
    style?: Record<string, string>
    createOrder: () => Promise<string>
    onApprove: (data: { orderID: string }) => Promise<void>
    onError: (error: unknown) => void
  }) => { render: (element: HTMLElement) => Promise<void>; close?: () => void }
}

declare global {
  interface Window { paypal?: PayPalNamespace }
}

const loaded = new Map<string, Promise<void>>()

/** Load the PayPal JS SDK once per client id + currency. */
function loadSdk(clientId: string, currency: string) {
  const src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=${currency}&intent=capture&components=buttons`
  if (!loaded.has(src)) {
    loaded.set(src, new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = src
      script.onload = () => resolve()
      script.onerror = () => reject(new Error('Could not load PayPal'))
      document.head.appendChild(script)
    }))
  }
  return loaded.get(src)!
}

interface Props {
  clientId: string
  currency: string
  createOrder: () => Promise<string>
  onApprove: (orderId: string) => Promise<void>
}

export default function PayPalButtons({ clientId, currency, createOrder, onApprove }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const [error, setError] = useState('')
  // keep the latest callbacks without re-rendering the buttons
  const handlers = useRef({ createOrder, onApprove })
  handlers.current = { createOrder, onApprove }

  useEffect(() => {
    let buttons: ReturnType<PayPalNamespace['Buttons']> | undefined
    let cancelled = false
    loadSdk(clientId, currency)
      .then(() => {
        if (cancelled || !container.current || !window.paypal) return
        container.current.innerHTML = ''
        buttons = window.paypal.Buttons({
          style: { shape: 'pill', layout: 'vertical', label: 'pay' },
          createOrder: () => handlers.current.createOrder(),
          onApprove: (data) => handlers.current.onApprove(data.orderID),
          onError: (err) => setError(err instanceof Error ? err.message : 'PayPal could not finish the payment'),
        })
        return buttons.render(container.current)
      })
      .catch((err) => setError(err.message))
    return () => {
      cancelled = true
      buttons?.close?.()
    }
  }, [clientId, currency])

  return (
    <div>
      <div ref={container} />
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  )
}

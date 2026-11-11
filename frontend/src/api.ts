/** Types and calls for the EvenSteven API. */

export interface ReceiptItem { name: string; quantity: number; line_total: number }
export interface Receipt { merchant: string; currency: string; items: ReceiptItem[]; tax: number; tip: number; total: number; warnings: string[] }
export interface ShareLine { name: string; amount: number; shared_with: string[]; reason: string }
export interface Share {
  id: string; bill_id: string; person: string; amount: number; status: 'pending' | 'paid' | 'payer'
  order_id: string | null; paid_at: string | null; items: ShareLine[]; items_total: number; extras: number; note: string
}
export interface SplitPlan { questions: string[]; summary: string; tip_override: number | null }
export interface Bill {
  id: string; currency: string; receipt: Receipt; people: string[]; payer: string | null; payee_email: string | null
  story: string[]; plan: SplitPlan | null; shares: Share[]
}
export interface AppConfig { paypal_client_id: string; public_url: string; ai_ready: boolean; paypal_ready: boolean }
export interface ShareView { share: Share; merchant: string; currency: string; payer: string }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `Request failed (${response.status})`)
  }
  return response.json()
}

const postJson = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  config: () => request<AppConfig>('/api/config'),
  uploadReceipt: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Bill>('/api/bills', { method: 'POST', body: form })
  },
  bill: (billId: string) => request<Bill>(`/api/bills/${billId}`),
  split: (billId: string, body: { people: string[]; payer: string; payee_email: string | null; story: string[] }) =>
    postJson<Bill>(`/api/bills/${billId}/split`, body),
  share: (shareId: string) => request<ShareView>(`/api/shares/${shareId}`),
  createOrder: (shareId: string) => postJson<{ order_id: string }>(`/api/shares/${shareId}/order`, {}),
  capture: (shareId: string, orderId: string) => postJson<{ status: string }>(`/api/shares/${shareId}/capture`, { order_id: orderId }),
}

export function money(amount: number, currency: string) {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount)
}

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

// phone photos are often 3-8 MB; the AI reads 1600 px just as well, and hosts cap uploads (Vercel: 4.5 MB)
const MAX_IMAGE_SIDE = 1600
const SHRINK_ABOVE_BYTES = 1.5 * 1024 * 1024

/** Large photos scaled down to MAX_IMAGE_SIDE as JPEG before upload; PDFs and small images unchanged. */
async function shrinkImage(file: File): Promise<File> {
  if (!file.type.startsWith('image/') || file.size <= SHRINK_ABOVE_BYTES) return file
  try {
    const bitmap = await createImageBitmap(file)
    const scale = Math.min(1, MAX_IMAGE_SIDE / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.88))
    return blob ? new File([blob], file.name.replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' }) : file
  } catch {
    return file
  }
}

export const api = {
  config: () => request<AppConfig>('/api/config'),
  uploadReceipt: async (file: File) => {
    const form = new FormData()
    form.append('file', await shrinkImage(file))
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

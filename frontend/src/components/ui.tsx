import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function Page({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto min-h-screen max-w-3xl px-4 pb-16">
      <header className="flex items-center justify-between py-5">
        <Link to="/" className="font-display text-2xl font-extrabold tracking-tight">
          Even<span className="text-brand">Steven</span>
        </Link>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-ink/60 shadow-sm">PayPal sandbox</span>
      </header>
      {children}
    </div>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-3xl bg-white p-5 shadow-sm ring-1 ring-ink/5 sm:p-6 ${className}`}>{children}</section>
}

export function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 text-ink/70">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-brand border-t-transparent" />
      {label}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return <p className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">{message}</p>
}

export function Button({ children, className = '', ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`rounded-2xl bg-brand px-5 py-3 font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {children}
    </button>
  )
}

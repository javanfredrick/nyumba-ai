import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { CreditCard, CheckCircle, AlertTriangle, Clock, Search } from 'lucide-react'
import { useState } from 'react'
import { format } from 'date-fns'
import api from '@/lib/api'

const STATUS_BADGE: Record<string, string> = {
  completed: 'badge-success',
  flagged:   'badge-warning',
  pending:   'badge-info',
  refunded:  'badge-danger',
}

const STATUS_ICON: Record<string, any> = {
  completed: CheckCircle,
  flagged:   AlertTriangle,
  pending:   Clock,
}

export default function PaymentsPage() {
  const [filter, setFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { data: payments = [], isLoading } = useQuery({
    queryKey: ['payments', statusFilter],
    queryFn: () =>
      api.get('/mpesa/payments', { params: { status: statusFilter || undefined, limit: 100 } }).then((r) => r.data),
  })

  const filtered = payments.filter((p: any) =>
    !filter ||
    p.mpesa_receipt_number.toLowerCase().includes(filter.toLowerCase()) ||
    p.bill_ref_number.toLowerCase().includes(filter.toLowerCase()) ||
    p.msisdn.includes(filter)
  )

  const formatKES = (n: number) =>
    new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(n)

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Payments</h1>
          <p className="text-slate-400 text-sm mt-0.5">All M-Pesa transactions — auto-reconciled by AI</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <CreditCard size={15} />
          {payments.length} transactions
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            className="input pl-9"
            placeholder="Search receipt, account, or phone..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <select
          className="input sm:w-44"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All Status</option>
          <option value="completed">Completed</option>
          <option value="flagged">Flagged</option>
          <option value="pending">Pending</option>
        </select>
      </div>

      {/* Table */}
      <div className="glass overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-slate-500">
            <CreditCard size={32} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">No payments found</p>
            <p className="text-xs mt-1">Payments appear here once M-Pesa sends a callback</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10">
                {['Receipt', 'Account', 'Phone', 'Amount', 'Date', 'Status'].map((h) => (
                  <th key={h} className="px-5 py-3.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filtered.map((p: any, i: number) => {
                const Icon = STATUS_ICON[p.status] ?? Clock
                return (
                  <motion.tr
                    key={p.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="hover:bg-white/3 transition-colors group"
                  >
                    <td className="px-5 py-3.5">
                      <span className="font-mono text-xs text-brand-400">{p.mpesa_receipt_number}</span>
                    </td>
                    <td className="px-5 py-3.5 text-slate-300 font-medium">{p.bill_ref_number}</td>
                    <td className="px-5 py-3.5 text-slate-400 font-mono text-xs">{p.msisdn}</td>
                    <td className="px-5 py-3.5 text-white font-semibold">{formatKES(Number(p.amount))}</td>
                    <td className="px-5 py-3.5 text-slate-500 text-xs">
                      {format(new Date(p.transaction_date), 'dd MMM yyyy HH:mm')}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={STATUS_BADGE[p.status] ?? 'badge-info'}>
                        <Icon size={10} />
                        {p.status}
                      </span>
                    </td>
                  </motion.tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

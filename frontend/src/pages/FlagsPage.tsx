import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, CheckCircle, Bot, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import { format } from 'date-fns'
import toast from 'react-hot-toast'
import api from '@/lib/api'

export default function FlagsPage() {
  const qc = useQueryClient()
  const [expanded, setExpanded] = useState<string | null>(null)
  const [notes, setNotes] = useState<Record<string, string>>({})

  const { data: flags = [], isLoading } = useQuery({
    queryKey: ['flags'],
    queryFn: () => api.get('/mpesa/flags?resolved=false').then((r) => r.data),
  })

  const resolve = useMutation({
    mutationFn: ({ id, note }: { id: string; note: string }) =>
      api.post(`/mpesa/flags/${id}/resolve`, { resolution_notes: note }),
    onSuccess: () => {
      toast.success('Flag resolved successfully')
      qc.invalidateQueries({ queryKey: ['flags'] })
      qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
    onError: () => toast.error('Failed to resolve flag'),
  })

  const formatKES = (n: number) =>
    new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(n)

  const REASON_LABELS: Record<string, string> = {
    unmatched_account: 'Unknown Account Number',
    unmatched_phone:   'Unknown Phone Number',
    amount_mismatch:   'Amount Mismatch',
    duplicate:         'Duplicate Payment',
    manual_entry:      'Manual Entry Detected',
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Flagged Payments</h1>
          <p className="text-slate-400 text-sm mt-0.5">AI-flagged transactions requiring your review</p>
        </div>
        <span className="badge-warning">
          <AlertTriangle size={11} />
          {flags.length} pending
        </span>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-48">
          <div className="w-7 h-7 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : flags.length === 0 ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass text-center py-20">
          <CheckCircle size={40} className="mx-auto mb-3 text-brand-400 opacity-70" />
          <p className="text-white font-medium">All clear!</p>
          <p className="text-slate-500 text-sm mt-1">No flagged payments to review</p>
        </motion.div>
      ) : (
        <div className="space-y-3">
          <AnimatePresence>
            {flags.map((flag: any, i: number) => (
              <motion.div
                key={flag.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ delay: i * 0.05 }}
                className="glass overflow-hidden"
              >
                {/* Header row */}
                <div
                  className="flex items-center gap-4 p-5 cursor-pointer hover:bg-white/3 transition-colors"
                  onClick={() => setExpanded(expanded === flag.id ? null : flag.id)}
                >
                  <div className="w-9 h-9 rounded-xl bg-amber-500/10 flex items-center justify-center shrink-0">
                    <AlertTriangle size={16} className="text-amber-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs text-brand-400">{flag.payment?.mpesa_receipt_number}</span>
                      <span className="badge-warning text-[10px]">{REASON_LABELS[flag.reason] ?? flag.reason}</span>
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-xs text-slate-400">
                      <span>KES {Number(flag.payment?.amount).toLocaleString()}</span>
                      <span>{flag.payment?.msisdn}</span>
                      <span>Account: <span className="text-slate-300 font-medium">{flag.payment?.bill_ref_number}</span></span>
                      <span>{flag.payment?.transaction_date ? format(new Date(flag.payment.transaction_date), 'dd MMM HH:mm') : ''}</span>
                    </div>
                  </div>
                  {expanded === flag.id ? <ChevronUp size={16} className="text-slate-500" /> : <ChevronDown size={16} className="text-slate-500" />}
                </div>

                {/* Expanded AI explanation + resolve */}
                <AnimatePresence>
                  {expanded === flag.id && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25 }}
                      className="overflow-hidden border-t border-white/10"
                    >
                      <div className="p-5 space-y-4">
                        {/* AI explanation */}
                        {flag.ai_explanation && (
                          <div className="flex gap-3 p-4 rounded-xl bg-indigo-500/5 border border-indigo-500/15">
                            <Bot size={15} className="text-indigo-400 shrink-0 mt-0.5" />
                            <div>
                              <p className="text-xs font-medium text-indigo-300 mb-1">AI Explanation</p>
                              <p className="text-sm text-slate-300 leading-relaxed">{flag.ai_explanation}</p>
                            </div>
                          </div>
                        )}

                        {/* Resolve form */}
                        <div className="space-y-3">
                          <label className="label">Resolution Notes</label>
                          <textarea
                            className="input resize-none h-20"
                            placeholder="Describe how this payment was resolved (e.g. 'Manually matched to Unit A3 — tenant used old account number')"
                            value={notes[flag.id] ?? ''}
                            onChange={(e) => setNotes((n) => ({ ...n, [flag.id]: e.target.value }))}
                          />
                          <div className="flex items-center gap-3">
                            <button
                              className="btn-primary"
                              disabled={!notes[flag.id]?.trim() || resolve.isPending}
                              onClick={() => resolve.mutate({ id: flag.id, note: notes[flag.id] })}
                            >
                              <CheckCircle size={14} />
                              Mark Resolved
                            </button>
                            <p className="text-xs text-slate-500">This will move the payment to Completed status</p>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}

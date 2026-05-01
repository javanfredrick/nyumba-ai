import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Users, Plus, Phone, Mail, IdCard, Loader2, X } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import api from '@/lib/api'

const schema = z.object({
  full_name:   z.string().min(2),
  phone:       z.string().regex(/^(2547|2541)\d{8}$/, 'Format: 2547XXXXXXXX'),
  email:       z.string().email().optional().or(z.literal('')),
  national_id: z.string().optional(),
})
type FormData = z.infer<typeof schema>

export default function TenantsPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const { data: tenants = [], isLoading } = useQuery({
    queryKey: ['tenants'],
    queryFn: () => api.get('/tenants').then((r) => r.data),
  })

  const create = useMutation({
    mutationFn: (data: FormData) => api.post('/tenants', data),
    onSuccess: () => {
      toast.success('Tenant added!')
      qc.invalidateQueries({ queryKey: ['tenants'] })
      qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
      reset(); setShowForm(false)
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to add tenant'),
  })

  const deactivate = useMutation({
    mutationFn: (id: string) => api.delete(`/tenants/${id}`),
    onSuccess: () => {
      toast.success('Tenant deactivated')
      qc.invalidateQueries({ queryKey: ['tenants'] })
    },
    onError: () => toast.error('Failed to deactivate tenant'),
  })

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Tenants</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            Phone numbers must match M-Pesa MSISDN format
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">{tenants.length} tenants</span>
          <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
            <Plus size={15} /> Add Tenant
          </button>
        </div>
      </div>

      {/* Add form */}
      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="glass p-6">
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-sm font-semibold text-white">New Tenant</h2>
                <button onClick={() => { setShowForm(false); reset() }} className="btn-ghost p-1.5">
                  <X size={14} />
                </button>
              </div>
              <form onSubmit={handleSubmit((d) => create.mutate(d))} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="label">Full Name *</label>
                  <input className="input" placeholder="John Kamau" {...register('full_name')} />
                  {errors.full_name && <p className="text-xs text-red-400 mt-1">{errors.full_name.message}</p>}
                </div>
                <div>
                  <label className="label">M-Pesa Phone * (MSISDN)</label>
                  <input className="input font-mono" placeholder="254712345678" {...register('phone')} />
                  {errors.phone && <p className="text-xs text-red-400 mt-1">{errors.phone.message}</p>}
                  <p className="text-[10px] text-slate-600 mt-1">Must match their M-Pesa registered number</p>
                </div>
                <div>
                  <label className="label">Email</label>
                  <input className="input" placeholder="john@email.com" {...register('email')} />
                </div>
                <div>
                  <label className="label">National ID</label>
                  <input className="input font-mono" placeholder="12345678" {...register('national_id')} />
                </div>
                <div className="sm:col-span-2 flex gap-3">
                  <button type="submit" className="btn-primary" disabled={isSubmitting}>
                    {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                    Add Tenant
                  </button>
                  <button type="button" className="btn-ghost" onClick={() => { setShowForm(false); reset() }}>
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Tenants grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-48">
          <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : tenants.length === 0 ? (
        <div className="glass text-center py-20">
          <Users size={40} className="mx-auto mb-3 text-slate-600" />
          <p className="text-white font-medium">No tenants yet</p>
          <p className="text-slate-500 text-sm mt-1">Add tenants so the AI can match M-Pesa payments to them</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {tenants.map((t: any, i: number) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className="glass p-5 group"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-10 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center">
                  <span className="text-sm font-bold text-brand-400">
                    {t.full_name.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase()}
                  </span>
                </div>
                <button
                  onClick={() => {
                    if (confirm(`Deactivate ${t.full_name}?`)) deactivate.mutate(t.id)
                  }}
                  className="opacity-0 group-hover:opacity-100 btn-danger p-1.5 text-[11px] transition-opacity"
                >
                  <X size={12} />
                </button>
              </div>

              <h3 className="font-semibold text-white mb-3">{t.full_name}</h3>

              <div className="space-y-1.5">
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <Phone size={11} className="text-slate-600" />
                  <span className="font-mono">{t.phone}</span>
                </div>
                {t.email && (
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <Mail size={11} className="text-slate-600" />
                    <span className="truncate">{t.email}</span>
                  </div>
                )}
                {t.national_id && (
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <IdCard size={11} className="text-slate-600" />
                    <span className="font-mono">{t.national_id}</span>
                  </div>
                )}
              </div>

              <div className="mt-4 pt-3 border-t border-white/5">
                <span className={t.is_active ? 'badge-success' : 'badge-danger'}>
                  {t.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}

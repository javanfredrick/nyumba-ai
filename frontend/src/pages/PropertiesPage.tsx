import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Building2, Home, Plus, MapPin, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import toast from 'react-hot-toast'
import api from '@/lib/api'

export default function PropertiesPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const { register, handleSubmit, reset, formState: { isSubmitting, errors } } = useForm()

  const { data: properties = [], isLoading } = useQuery({
    queryKey: ['properties'],
    queryFn: () => api.get('/properties').then((r) => r.data),
  })

  const create = useMutation({
    mutationFn: (data: any) => api.post('/properties', data),
    onSuccess: () => {
      toast.success('Property created!')
      qc.invalidateQueries({ queryKey: ['properties'] })
      reset(); setShowForm(false)
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to create property'),
  })

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Properties</h1>
          <p className="text-slate-400 text-sm mt-0.5">Manage your property portfolio</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          <Plus size={15} /> Add Property
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="glass p-6">
          <h2 className="text-sm font-semibold text-white mb-4">New Property</h2>
          <form onSubmit={handleSubmit((d) => create.mutate(d))} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Property Name *</label>
              <input className="input" placeholder="Sunset Apartments" {...register('name', { required: true })} />
            </div>
            <div>
              <label className="label">City</label>
              <input className="input" defaultValue="Nairobi" {...register('city')} />
            </div>
            <div className="sm:col-span-2">
              <label className="label">Address *</label>
              <input className="input" placeholder="123 Kiambu Road, Nairobi" {...register('address', { required: true })} />
            </div>
            <div className="sm:col-span-2">
              <label className="label">Description</label>
              <textarea className="input resize-none h-20" placeholder="Optional description..." {...register('description')} />
            </div>
            <div className="sm:col-span-2 flex gap-3">
              <button type="submit" className="btn-primary" disabled={isSubmitting}>
                {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                Create Property
              </button>
              <button type="button" className="btn-ghost" onClick={() => { setShowForm(false); reset() }}>Cancel</button>
            </div>
          </form>
        </motion.div>
      )}

      {/* Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-48">
          <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : properties.length === 0 ? (
        <div className="glass text-center py-20">
          <Building2 size={40} className="mx-auto mb-3 text-slate-600" />
          <p className="text-white font-medium">No properties yet</p>
          <p className="text-slate-500 text-sm mt-1">Add your first property to get started</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {properties.map((p: any, i: number) => (
            <motion.div
              key={p.id}
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.05 }}
              className="glass-hover p-5 cursor-pointer"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center">
                  <Building2 size={18} className="text-brand-400" />
                </div>
                <span className={`badge-${p.is_active ? 'success' : 'danger'} text-[10px]`}>
                  {p.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              <h3 className="font-semibold text-white mb-1">{p.name}</h3>
              <p className="flex items-center gap-1.5 text-xs text-slate-500 mb-4">
                <MapPin size={11} /> {p.address}, {p.city}
              </p>
              <div className="flex items-center gap-1 text-xs text-slate-400">
                <Home size={12} />
                <span>{p.unit_count ?? 0} units</span>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}

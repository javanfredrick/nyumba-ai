import { useQuery, useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { CreditCard, Zap, Crown, Rocket, Building2, CheckCircle, ExternalLink, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { useAuthStore } from '@/stores/authStore'
import api from '@/lib/api'
import clsx from 'clsx'

const PLANS = [
  {
    id: 'starter',
    name: 'Starter',
    price: 'KES 2,500',
    period: '/month',
    icon: Building2,
    color: 'slate',
    features: [
      'Up to 10 units',
      '100K AI tokens/month',
      'M-Pesa auto-reconciliation',
      'Basic dashboard',
      'Email support',
    ],
  },
  {
    id: 'growth',
    name: 'Growth',
    price: 'KES 7,500',
    period: '/month',
    icon: Rocket,
    color: 'brand',
    popular: true,
    features: [
      'Up to 50 units',
      '500K AI tokens/month',
      'M-Pesa auto-reconciliation',
      'Advanced analytics',
      'Mortgage tracking',
      'Priority support',
    ],
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: 'KES 20,000',
    period: '/month',
    icon: Crown,
    color: 'amber',
    features: [
      'Unlimited units',
      '5M AI tokens/month',
      'Custom M-Pesa shortcode',
      'Multi-property analytics',
      'API access',
      'Dedicated support',
    ],
  },
]

export default function BillingPage() {
  const landlord = useAuthStore((s) => s.landlord)

  const { data: status } = useQuery({
    queryKey: ['billing-status'],
    queryFn: () => api.get('/billing/status').then((r) => r.data),
  })

  const subscribe = useMutation({
    mutationFn: (tier: string) => api.post(`/billing/subscribe/${tier}`).then((r) => r.data),
    onSuccess: (data) => {
      window.location.href = data.checkout_url
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Subscription failed'),
  })

  const portal = useMutation({
    mutationFn: () => api.post('/billing/portal').then((r) => r.data),
    onSuccess: (data) => { window.location.href = data.portal_url },
    onError: () => toast.error('Could not open billing portal'),
  })

  const tokenPct = landlord
    ? Math.min(100, (landlord.ai_tokens_used / landlord.ai_tokens_limit) * 100)
    : 0

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Billing & Subscription</h1>
        <p className="text-slate-400 text-sm mt-0.5">Manage your plan and AI token usage</p>
      </div>

      {/* Current usage */}
      <div className="glass p-6 space-y-5">
        <h2 className="text-sm font-semibold text-white">Current Usage</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-slate-500 mb-1">Current Plan</p>
            <p className="text-lg font-bold text-white capitalize">{landlord?.subscription_tier}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">AI Tokens Used</p>
            <p className="text-lg font-bold text-white">
              {((landlord?.ai_tokens_used ?? 0) / 1000).toFixed(1)}k
              <span className="text-slate-500 text-sm font-normal">
                {' '}/ {((landlord?.ai_tokens_limit ?? 100000) / 1000).toFixed(0)}k
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">Cost per 1K tokens</p>
            <p className="text-lg font-bold text-white">KES 0.50</p>
          </div>
        </div>

        {/* Token bar */}
        <div>
          <div className="flex justify-between text-xs text-slate-500 mb-1.5">
            <span className="flex items-center gap-1"><Zap size={10} /> Token usage</span>
            <span>{tokenPct.toFixed(1)}%</span>
          </div>
          <div className="h-2 rounded-full bg-white/10 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${tokenPct}%` }}
              transition={{ duration: 1 }}
              className={clsx(
                'h-full rounded-full',
                tokenPct > 90 ? 'bg-red-500' : tokenPct > 70 ? 'bg-amber-500' : 'bg-brand-500'
              )}
            />
          </div>
        </div>

        {/* Manage portal */}
        {status?.subscription_id && (
          <button
            onClick={() => portal.mutate()}
            disabled={portal.isPending}
            className="btn-ghost text-sm"
          >
            {portal.isPending ? <Loader2 size={14} className="animate-spin" /> : <ExternalLink size={14} />}
            Manage Subscription on Stripe
          </button>
        )}
      </div>

      {/* Plans */}
      <div>
        <h2 className="text-sm font-semibold text-white mb-4">Available Plans</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {PLANS.map((plan, i) => {
            const Icon = plan.icon
            const isCurrent = landlord?.subscription_tier === plan.id
            return (
              <motion.div
                key={plan.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                className={clsx(
                  'glass p-6 relative flex flex-col',
                  plan.popular && 'border-brand-500/40',
                  isCurrent && 'border-brand-500/60'
                )}
              >
                {plan.popular && !isCurrent && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="bg-brand-500 text-white text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-wider shadow-glow">
                      Most Popular
                    </span>
                  </div>
                )}
                {isCurrent && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="bg-slate-700 text-slate-300 text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-wider border border-white/10">
                      Current Plan
                    </span>
                  </div>
                )}

                <div className={`w-10 h-10 rounded-xl bg-${plan.color}-500/10 border border-${plan.color}-500/20 flex items-center justify-center mb-4`}>
                  <Icon size={18} className={`text-${plan.color}-400`} />
                </div>

                <h3 className="text-base font-bold text-white mb-1">{plan.name}</h3>
                <div className="mb-5">
                  <span className="text-2xl font-bold text-white">{plan.price}</span>
                  <span className="text-slate-500 text-sm">{plan.period}</span>
                </div>

                <ul className="space-y-2 flex-1 mb-6">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-xs text-slate-400">
                      <CheckCircle size={12} className="text-brand-500 shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => !isCurrent && subscribe.mutate(plan.id)}
                  disabled={isCurrent || subscribe.isPending}
                  className={clsx(
                    'w-full py-2.5 rounded-xl text-sm font-semibold transition-all duration-200',
                    isCurrent
                      ? 'bg-white/5 text-slate-500 cursor-default border border-white/10'
                      : 'btn-primary justify-center'
                  )}
                >
                  {subscribe.isPending && subscribe.variables === plan.id
                    ? <Loader2 size={14} className="animate-spin mx-auto" />
                    : isCurrent ? 'Current Plan' : `Upgrade to ${plan.name}`
                  }
                </button>
              </motion.div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

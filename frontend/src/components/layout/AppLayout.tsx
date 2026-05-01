import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard, Building2, Users, CreditCard, AlertTriangle,
  Bot, LogOut, ChevronRight, Zap, Receipt,
} from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import clsx from 'clsx'

const navItems = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/properties', icon: Building2,        label: 'Properties' },
  { to: '/tenants',    icon: Users,             label: 'Tenants' },
  { to: '/payments',   icon: CreditCard,        label: 'Payments' },
  { to: '/flags',      icon: AlertTriangle,     label: 'Flagged' },
  { to: '/assistant',  icon: Bot,               label: 'AI Assistant' },
  { to: '/billing',    icon: Receipt,           label: 'Billing' },
]

export default function AppLayout() {
  const { landlord, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => { logout(); navigate('/login') }

  const tierColor = {
    starter:    'text-slate-400',
    growth:     'text-blue-400',
    enterprise: 'text-amber-400',
  }[landlord?.subscription_tier ?? 'starter']

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Sidebar ─────────────────────────────────────────────────── */}
      <motion.aside
        initial={{ x: -60, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.35 }}
        className="w-64 flex flex-col glass border-r border-white/10 rounded-none shrink-0"
      >
        {/* Logo */}
        <div className="px-6 py-5 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center shadow-glow">
              <Building2 size={16} className="text-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-white tracking-tight">NyumbaAI</p>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest">Property OS</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to}>
              {({ isActive }) => (
                <motion.div
                  whileHover={{ x: 3 }}
                  className={clsx(
                    'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 group',
                    isActive
                      ? 'bg-brand-500/15 text-brand-400 border border-brand-500/25'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                  )}
                >
                  <Icon size={16} className={isActive ? 'text-brand-400' : 'text-slate-500 group-hover:text-slate-300'} />
                  {label}
                  {isActive && <ChevronRight size={12} className="ml-auto text-brand-500" />}
                </motion.div>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User footer */}
        <div className="px-3 py-4 border-t border-white/10 space-y-3">
          {/* AI token meter */}
          {landlord && (
            <div className="px-2">
              <div className="flex items-center justify-between mb-1.5">
                <span className="flex items-center gap-1 text-[11px] text-slate-500">
                  <Zap size={10} /> AI Tokens
                </span>
                <span className="text-[11px] text-slate-400">
                  {(landlord.ai_tokens_used / 1000).toFixed(0)}k / {(landlord.ai_tokens_limit / 1000).toFixed(0)}k
                </span>
              </div>
              <div className="h-1 rounded-full bg-white/10 overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(100, (landlord.ai_tokens_used / landlord.ai_tokens_limit) * 100)}%` }}
                  transition={{ duration: 0.8, delay: 0.3 }}
                  className="h-full rounded-full bg-brand-500"
                />
              </div>
            </div>
          )}

          {/* Profile */}
          <div className="flex items-center gap-3 px-2">
            <div className="w-8 h-8 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center shrink-0">
              {landlord?.avatar_url
                ? <img src={landlord.avatar_url} className="w-full h-full rounded-full object-cover" alt="" />
                : <span className="text-xs font-bold text-brand-400">{landlord?.full_name?.[0]}</span>
              }
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-200 truncate">{landlord?.full_name}</p>
              <p className={`text-[10px] capitalize font-medium ${tierColor}`}>{landlord?.subscription_tier}</p>
            </div>
            <button onClick={handleLogout} className="p-1.5 rounded-lg hover:bg-white/10 text-slate-500 hover:text-red-400 transition-colors">
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </motion.aside>

      {/* ── Main content ─────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto">
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="min-h-full p-6"
        >
          <Outlet />
        </motion.div>
      </main>
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Building2, Home, Users, TrendingUp,
  AlertTriangle, CheckCircle, Zap, DollarSign,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts'
import api from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'

const COLORS = ['#22c55e', '#334155']

function StatCard({ icon: Icon, label, value, sub, color = 'brand' }: any) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="stat-card"
    >
      <div className={`w-9 h-9 rounded-xl flex items-center justify-center mb-3 bg-${color}-500/10`}>
        <Icon size={18} className={`text-${color}-400`} />
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-xs text-slate-400">{label}</p>
      {sub && <p className="text-[11px] text-slate-500 mt-0.5">{sub}</p>}
    </motion.div>
  )
}

const mockTrend = [
  { month: 'Jan', collected: 142000, expected: 160000 },
  { month: 'Feb', collected: 155000, expected: 160000 },
  { month: 'Mar', collected: 148000, expected: 165000 },
  { month: 'Apr', collected: 170000, expected: 170000 },
  { month: 'May', collected: 163000, expected: 175000 },
  { month: 'Jun', collected: 180000, expected: 180000 },
]

export default function DashboardPage() {
  const landlord = useAuthStore((s) => s.landlord)
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => api.get('/dashboard/stats').then((r) => r.data),
  })

  const formatKES = (n: number) =>
    new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(n)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const occupancyData = [
    { name: 'Occupied', value: stats?.occupied_units ?? 0 },
    { name: 'Vacant',   value: stats?.vacant_units ?? 0 },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">
          Good morning, {landlord?.full_name?.split(' ')[0]} 👋
        </h1>
        <p className="text-slate-400 text-sm mt-1">Here's your property portfolio overview.</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Building2}    label="Total Properties"  value={stats?.total_properties ?? 0} />
        <StatCard icon={Home}         label="Units"             value={`${stats?.occupied_units ?? 0}/${stats?.total_units ?? 0}`} sub="Occupied / Total" />
        <StatCard icon={Users}        label="Active Tenants"    value={stats?.total_tenants ?? 0} />
        <StatCard icon={AlertTriangle} label="Pending Flags"   value={stats?.pending_flags ?? 0} color="amber" />
      </div>

      {/* Revenue cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="glass p-5 col-span-1">
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Expected This Month</p>
          <p className="text-3xl font-bold text-white">{formatKES(stats?.monthly_expected_revenue ?? 0)}</p>
          <p className="text-xs text-slate-500 mt-1">Based on occupied units</p>
        </div>
        <div className="glass p-5 col-span-1">
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Collected This Month</p>
          <p className="text-3xl font-bold text-brand-400">{formatKES(stats?.monthly_collected_revenue ?? 0)}</p>
          <div className="mt-3 h-1.5 rounded-full bg-white/10 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${stats?.collection_rate ?? 0}%` }}
              transition={{ duration: 1, delay: 0.3 }}
              className="h-full rounded-full bg-brand-500"
            />
          </div>
          <p className="text-xs text-slate-400 mt-1">{stats?.collection_rate ?? 0}% collection rate</p>
        </div>
        <div className="glass p-5 col-span-1 flex flex-col">
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-3">Occupancy</p>
          <div className="flex items-center gap-4 flex-1">
            <PieChart width={80} height={80}>
              <Pie data={occupancyData} cx={35} cy={35} innerRadius={24} outerRadius={36} dataKey="value" strokeWidth={0}>
                {occupancyData.map((_, i) => <Cell key={i} fill={COLORS[i]} />)}
              </Pie>
            </PieChart>
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs"><div className="w-2 h-2 rounded-full bg-brand-500" /><span className="text-slate-300">{stats?.occupied_units} Occupied</span></div>
              <div className="flex items-center gap-2 text-xs"><div className="w-2 h-2 rounded-full bg-slate-600" /><span className="text-slate-400">{stats?.vacant_units} Vacant</span></div>
            </div>
          </div>
        </div>
      </div>

      {/* Revenue trend chart */}
      <div className="glass p-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-sm font-semibold text-white">Revenue Trend</h2>
            <p className="text-xs text-slate-500">Expected vs Collected (KES)</p>
          </div>
          <TrendingUp size={16} className="text-brand-400" />
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={mockTrend}>
            <defs>
              <linearGradient id="collected" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#22c55e" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="expected" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="month" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v/1000}k`} />
            <Tooltip
              contentStyle={{ background: '#0d1526', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, fontSize: 12 }}
              formatter={(v: number) => [formatKES(v), '']}
            />
            <Area type="monotone" dataKey="expected"  stroke="#6366f1" strokeWidth={2} fill="url(#expected)" strokeDasharray="4 4" />
            <Area type="monotone" dataKey="collected" stroke="#22c55e" strokeWidth={2} fill="url(#collected)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* AI token usage */}
      <div className="glass p-5 flex items-center gap-5">
        <div className="w-10 h-10 rounded-xl bg-brand-500/10 flex items-center justify-center shrink-0">
          <Zap size={18} className="text-brand-400" />
        </div>
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1.5">
            <p className="text-sm font-medium text-white">AI Token Usage</p>
            <span className="text-xs text-slate-400">
              {((stats?.ai_tokens_used ?? 0) / 1000).toFixed(0)}k / {((stats?.ai_tokens_limit ?? 100000) / 1000).toFixed(0)}k
            </span>
          </div>
          <div className="h-2 rounded-full bg-white/10 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(100, ((stats?.ai_tokens_used ?? 0) / (stats?.ai_tokens_limit ?? 100000)) * 100)}%` }}
              transition={{ duration: 1, delay: 0.5 }}
              className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-400"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

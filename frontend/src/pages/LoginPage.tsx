import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Building2, Mail, Lock, Loader2, Chrome } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'

const schema = z.object({
  email:    z.string().email('Invalid email'),
  password: z.string().min(8, 'Min 8 characters'),
})
type FormData = z.infer<typeof schema>

const registerSchema = schema.extend({
  full_name: z.string().min(2, 'Name required'),
  confirm:   z.string(),
}).refine((d) => d.password === d.confirm, { message: "Passwords don't match", path: ['confirm'] })
type RegisterData = z.infer<typeof registerSchema>

export default function LoginPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  const loginForm = useForm<FormData>({ resolver: zodResolver(schema) })
  const registerForm = useForm<RegisterData>({ resolver: zodResolver(registerSchema) })

  const onLogin = async (data: FormData) => {
    try {
      const res = await api.post('/auth/login', data)
      const me = await api.get('/auth/me', { headers: { Authorization: `Bearer ${res.data.access_token}` } })
      setAuth(res.data.access_token, me.data)
      navigate('/dashboard')
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Login failed')
    }
  }

  const onRegister = async (data: RegisterData) => {
    try {
      const { confirm, ...body } = data
      const res = await api.post('/auth/register', body)
      const me = await api.get('/auth/me', { headers: { Authorization: `Bearer ${res.data.access_token}` } })
      setAuth(res.data.access_token, me.data)
      navigate('/dashboard')
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Registration failed')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      {/* Background blobs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="glass w-full max-w-md p-8 relative"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-brand-500/20 border border-brand-500/30 flex items-center justify-center mx-auto mb-4 shadow-glow">
            <Building2 size={28} className="text-brand-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">NyumbaAI</h1>
          <p className="text-slate-400 text-sm mt-1">Intelligent Property Management</p>
        </div>

        {/* Tabs */}
        <div className="flex rounded-xl bg-white/5 p-1 mb-6">
          {(['login', 'register'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-200 capitalize ${
                mode === m ? 'bg-brand-500 text-white shadow-glow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {m === 'login' ? 'Sign In' : 'Sign Up'}
            </button>
          ))}
        </div>

        {/* Login Form */}
        {mode === 'login' && (
          <motion.form
            key="login"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            onSubmit={loginForm.handleSubmit(onLogin)}
            className="space-y-4"
          >
            <div>
              <label className="label">Email</label>
              <div className="relative">
                <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input className="input pl-9" placeholder="you@example.com" {...loginForm.register('email')} />
              </div>
              {loginForm.formState.errors.email && <p className="text-xs text-red-400 mt-1">{loginForm.formState.errors.email.message}</p>}
            </div>
            <div>
              <label className="label">Password</label>
              <div className="relative">
                <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input type="password" className="input pl-9" placeholder="••••••••" {...loginForm.register('password')} />
              </div>
              {loginForm.formState.errors.password && <p className="text-xs text-red-400 mt-1">{loginForm.formState.errors.password.message}</p>}
            </div>
            <button type="submit" className="btn-primary w-full justify-center" disabled={loginForm.formState.isSubmitting}>
              {loginForm.formState.isSubmitting ? <Loader2 size={16} className="animate-spin" /> : 'Sign In'}
            </button>
          </motion.form>
        )}

        {/* Register Form */}
        {mode === 'register' && (
          <motion.form
            key="register"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            onSubmit={registerForm.handleSubmit(onRegister)}
            className="space-y-4"
          >
            <div>
              <label className="label">Full Name</label>
              <input className="input" placeholder="John Kamau" {...registerForm.register('full_name')} />
              {registerForm.formState.errors.full_name && <p className="text-xs text-red-400 mt-1">{registerForm.formState.errors.full_name.message}</p>}
            </div>
            <div>
              <label className="label">Email</label>
              <input className="input" placeholder="you@example.com" {...registerForm.register('email')} />
              {registerForm.formState.errors.email && <p className="text-xs text-red-400 mt-1">{registerForm.formState.errors.email.message}</p>}
            </div>
            <div>
              <label className="label">Password</label>
              <input type="password" className="input" placeholder="Min 8 characters" {...registerForm.register('password')} />
            </div>
            <div>
              <label className="label">Confirm Password</label>
              <input type="password" className="input" placeholder="Repeat password" {...registerForm.register('confirm')} />
              {registerForm.formState.errors.confirm && <p className="text-xs text-red-400 mt-1">{registerForm.formState.errors.confirm.message}</p>}
            </div>
            <button type="submit" className="btn-primary w-full justify-center" disabled={registerForm.formState.isSubmitting}>
              {registerForm.formState.isSubmitting ? <Loader2 size={16} className="animate-spin" /> : 'Create Account'}
            </button>
          </motion.form>
        )}

        {/* Divider */}
        <div className="flex items-center gap-3 my-5">
          <div className="flex-1 h-px bg-white/10" />
          <span className="text-xs text-slate-500">or continue with</span>
          <div className="flex-1 h-px bg-white/10" />
        </div>

        {/* Google */}
        <a
          href="/api/v1/auth/google"
          className="flex items-center justify-center gap-3 w-full py-2.5 rounded-xl border border-white/10 bg-white/5 text-slate-300 text-sm font-medium hover:bg-white/10 transition-all duration-200"
        >
          <Chrome size={16} />
          Google
        </a>
      </motion.div>
    </div>
  )
}

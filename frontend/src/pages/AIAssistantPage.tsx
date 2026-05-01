import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bot, Send, User, Loader2, Zap, RefreshCw } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import api from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import clsx from 'clsx'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  tokens?: number
  cost?: number
}

const SUGGESTIONS = [
  'Which tenants are overdue this month?',
  'Show me all flagged payments',
  'What is my total collected rent for June?',
  'List all vacant units',
]

export default function AIAssistantPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const landlord = useAuthStore((s) => s.landlord)
  const updateLandlord = useAuthStore((s) => s.updateLandlord)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const query = useMutation({
    mutationFn: (question: string) =>
      api.post('/ai/query', { question }).then((r) => r.data),
    onSuccess: (data, question) => {
      setMessages((m) => [
        ...m,
        {
          id: Date.now().toString(),
          role: 'assistant',
          content: data.answer,
          tokens: data.tokens_used,
          cost: data.cost_kes,
        },
      ])
      // Update token count in sidebar
      if (landlord) {
        updateLandlord({ ai_tokens_used: landlord.ai_tokens_used + (data.tokens_used ?? 0) })
      }
    },
    onError: (e: any) => {
      const msg = e.response?.data?.detail || 'AI query failed'
      toast.error(msg)
      setMessages((m) => [
        ...m,
        { id: Date.now().toString(), role: 'assistant', content: `⚠️ ${msg}` },
      ])
    },
  })

  const sendMessage = (text?: string) => {
    const q = (text ?? input).trim()
    if (!q) return
    setMessages((m) => [...m, { id: Date.now().toString(), role: 'user', content: q }])
    setInput('')
    query.mutate(q)
  }

  const seed = useMutation({
    mutationFn: () => api.post('/ai/seed').then((r) => r.data),
    onSuccess: (d) => toast.success(d.message),
    onError: () => toast.error('Seeding failed'),
  })

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
            <Bot size={18} className="text-indigo-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">AI Assistant</h1>
            <p className="text-slate-500 text-xs">Powered by Gemini 1.5 Flash + RAG</p>
          </div>
        </div>
        <button
          onClick={() => seed.mutate()}
          disabled={seed.isPending}
          className="btn-ghost text-xs"
          title="Re-index your data"
        >
          <RefreshCw size={13} className={seed.isPending ? 'animate-spin' : ''} />
          Refresh Index
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 pb-4">
        {messages.length === 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-12">
            <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-4">
              <Bot size={28} className="text-indigo-400" />
            </div>
            <p className="text-white font-medium mb-1">Ask me anything about your properties</p>
            <p className="text-slate-500 text-sm mb-8">I have access to your tenants, payments, units, and more.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-lg mx-auto">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  className="glass-hover text-left p-3 text-xs text-slate-400 hover:text-slate-200 rounded-xl transition-all"
                >
                  {s}
                </button>
              ))}
            </div>
          </motion.div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={clsx('flex gap-3', msg.role === 'user' ? 'flex-row-reverse' : 'flex-row')}
            >
              {/* Avatar */}
              <div className={clsx(
                'w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-white',
                msg.role === 'user' ? 'bg-brand-500/20 border border-brand-500/30' : 'bg-indigo-500/20 border border-indigo-500/30'
              )}>
                {msg.role === 'user'
                  ? <User size={14} className="text-brand-400" />
                  : <Bot size={14} className="text-indigo-400" />
                }
              </div>

              {/* Bubble */}
              <div className={clsx(
                'max-w-xl rounded-2xl px-4 py-3 text-sm leading-relaxed',
                msg.role === 'user'
                  ? 'bg-brand-500/15 border border-brand-500/20 text-slate-200 rounded-tr-sm'
                  : 'glass text-slate-200 rounded-tl-sm'
              )}>
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.tokens && (
                  <p className="flex items-center gap-1 text-[10px] text-slate-600 mt-2">
                    <Zap size={9} /> {msg.tokens} tokens · KES {msg.cost?.toFixed(3)}
                  </p>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Typing indicator */}
        {query.isPending && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
            <div className="w-8 h-8 rounded-xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
              <Bot size={14} className="text-indigo-400" />
            </div>
            <div className="glass px-4 py-3 rounded-2xl rounded-tl-sm">
              <Loader2 size={14} className="animate-spin text-indigo-400" />
            </div>
          </motion.div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 pt-3 border-t border-white/10">
        <div className="flex gap-3">
          <input
            className="input flex-1"
            placeholder="Ask about your tenants, payments, or units..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
            disabled={query.isPending}
          />
          <button
            className="btn-primary shrink-0"
            onClick={() => sendMessage()}
            disabled={!input.trim() || query.isPending}
          >
            <Send size={15} />
          </button>
        </div>
        <p className="text-[10px] text-slate-600 mt-2 text-center">
          AI responses are based on your indexed property data. Always verify critical financial decisions.
        </p>
      </div>
    </div>
  )
}

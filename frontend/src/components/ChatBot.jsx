import React, { useState, useRef, useEffect } from 'react'
import { postAiChat } from '../api/client'

const EXAMPLES = [
  'Which region has the highest projected production?',
  'Summarize the Permian Basin investment opportunity.',
  'Compare Eagle Ford vs Bakken attractiveness.',
  'What happens to Permian revenue if WTI drops to $55?',
  'Which regions are declining in output?',
  'Rank all 5 regions for long-term investment.',
]

function format(text) {
  return text
    .replace(/\[DATA\]/g,      '<span class="badge-data">DATA</span>')
    .replace(/\[INFERENCE\]/g, '<span class="badge-inf">INFERENCE</span>')
    .replace(/\*\*(.*?)\*\*/g, '<strong style="color:#F9FAFB;font-weight:700">$1</strong>')
    .replace(/\n/g, '<br/>')
}

const SparkIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" stroke="white" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

export default function ChatBot({ scoresData, selectedYear, commodity, wtiPrice = 72, hhPrice = 2.5 }) {
  const [open,     setOpen]     = useState(false)
  const [messages, setMessages] = useState([])
  const [input,    setInput]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState(null)
  const [unread,   setUnread]   = useState(0)
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  useEffect(() => {
    if (open) { setUnread(0); setTimeout(() => inputRef.current?.focus(), 80) }
  }, [open])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    if (!open && messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
      setUnread(u => u + 1)
    }
  }, [messages, open])

  const send = async (text) => {
    const msg = (text || input).trim()
    if (!msg || loading) return
    const userMsg = { role: 'user', content: msg }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    setError(null)
    try {
      const res = await postAiChat({ messages: [...messages, userMsg], selected_year: selectedYear, commodity, wti_price: wtiPrice, hh_price: hhPrice })
      setMessages(prev => [...prev, { role: 'assistant', content: res.answer }])
    } catch (e) {
      const d = e.response?.data?.detail || e.message || ''
      if (d.includes('GROQ_API_KEY')) setError('Groq API key not configured.')
      else if (d.includes('429') || d.includes('rate_limit')) setError('Rate limit — please wait a moment.')
      else setError(d || 'Request failed. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* ── Badge styles injected once ────────────────────────── */}
      <style>{`
        .badge-data { background:rgba(16,185,129,0.12); color:#10B981; padding:1px 6px; border-radius:4px; font-size:0.7em; font-weight:700; border:1px solid rgba(16,185,129,0.25); letter-spacing:.04em; }
        .badge-inf  { background:rgba(245,158,11,0.1);  color:#F59E0B; padding:1px 6px; border-radius:4px; font-size:0.7em; font-weight:700; border:1px solid rgba(245,158,11,0.25);  letter-spacing:.04em; }
        .chat-input-wrap:focus-within { border-color: rgba(99,102,241,0.55) !important; box-shadow: 0 0 0 3px rgba(99,102,241,0.1) !important; }
        .ex-btn:hover { background:rgba(99,102,241,0.1)!important; color:#A5B4FC!important; border-color:rgba(99,102,241,0.2)!important; }
        .clear-btn:hover { color:#EF4444!important; border-color:rgba(239,68,68,0.3)!important; }
      `}</style>

      {/* ── Floating trigger ──────────────────────────────────── */}
      <button
        onClick={() => setOpen(o => !o)}
        className={!open ? 'chat-btn-glow' : ''}
        title={open ? 'Close AI Analyst' : 'Open AI Analyst'}
        style={{
          position: 'fixed', bottom: 22, right: 22, zIndex: 1000,
          width: 50, height: 50, borderRadius: '50%',
          background: open
            ? 'rgba(99,102,241,0.9)'
            : 'linear-gradient(135deg,#6366F1 0%,#06B6D4 100%)',
          border: 'none',
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'transform 0.2s cubic-bezier(0.34,1.56,0.64,1), background 0.2s',
          transform: open ? 'rotate(45deg) scale(0.95)' : 'scale(1)',
        }}
      >
        {open ? (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 2L12 12M12 2L2 12" stroke="white" strokeWidth="2" strokeLinecap="round"/>
          </svg>
        ) : <SparkIcon />}
        {!open && unread > 0 && (
          <span style={{
            position: 'absolute', top: -2, right: -2,
            background: '#EF4444', color: '#fff', borderRadius: '50%',
            minWidth: 17, height: 17, fontSize: '0.58rem', fontWeight: 800,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            border: '2px solid #060608', padding: '0 3px',
          }}>{unread}</span>
        )}
      </button>

      {/* ── Chat panel ────────────────────────────────────────── */}
      {open && (
        <div
          className="chat-pop"
          style={{
            position: 'fixed', bottom: 84, right: 22, zIndex: 999,
            width: 376, height: 580,
            background: 'rgba(8,9,14,0.97)',
            backdropFilter: 'blur(40px)',
            WebkitBackdropFilter: 'blur(40px)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 16,
            boxShadow: '0 0 0 1px rgba(99,102,241,0.1), 0 40px 80px rgba(0,0,0,0.9), inset 0 1px 0 rgba(255,255,255,0.04)',
            display: 'flex', flexDirection: 'column',
            overflow: 'hidden',
            fontFamily: "'Inter', -apple-system, system-ui, sans-serif",
          }}
        >
          {/* Top accent line */}
          <div style={{ height: 1, background: 'linear-gradient(90deg,transparent,rgba(99,102,241,0.6) 30%,rgba(6,182,212,0.5) 70%,transparent)', flexShrink: 0 }} />

          {/* Header */}
          <div style={{
            padding: '0.75rem 0.95rem',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            display: 'flex', alignItems: 'center', gap: 10,
            background: 'rgba(255,255,255,0.02)',
            flexShrink: 0,
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 9, flexShrink: 0,
              background: 'linear-gradient(135deg,#6366F1,#06B6D4)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 16px rgba(99,102,241,0.5)',
            }}><SparkIcon /></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#F9FAFB', letterSpacing: '-0.01em' }}>OilPulse AI</div>
              <div style={{ fontSize: '0.62rem', color: '#10B981', display: 'flex', alignItems: 'center', gap: 4, marginTop: 1 }}>
                <span className="live-dot" style={{ width: 4, height: 4, borderRadius: '50%', background: '#10B981', display: 'inline-block' }} />
                Live data · Energy analyst
              </div>
            </div>
            {messages.length > 0 && (
              <button
                className="clear-btn"
                onClick={() => setMessages([])}
                title="Clear"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', color: '#374151', cursor: 'pointer', borderRadius: 7, width: 26, height: 26, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'all 0.15s' }}
              >
                <svg width="11" height="11" viewBox="0 0 11 11" fill="none"><path d="M1 2.5h9M3.5 2.5V1.5C3.5 1.22 3.72 1 4 1h3c.28 0 .5.22.5.5v1M2 2.5l.5 7c0 .28.22.5.5.5h5c.28 0 .5-.22.5-.5l.5-7" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/></svg>
              </button>
            )}
          </div>

          {/* Messages */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '0.8rem', display: 'flex', flexDirection: 'column', gap: 8 }}>

            {/* Empty state */}
            {messages.length === 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ textAlign: 'center', padding: '0.25rem 0 0.5rem' }}>
                  <div style={{
                    width: 44, height: 44, borderRadius: 12, margin: '0 auto 10px',
                    background: 'linear-gradient(135deg,rgba(99,102,241,0.15),rgba(6,182,212,0.08))',
                    border: '1px solid rgba(99,102,241,0.2)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: '0 0 20px rgba(99,102,241,0.1)',
                  }}><SparkIcon /></div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#9CA3AF', marginBottom: 3 }}>
                    Ask about the U.S. energy market
                  </div>
                  <div style={{ fontSize: '0.67rem', color: '#4B5563' }}>
                    Powered by live EIA production &amp; forecast data
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {EXAMPLES.map((q, i) => (
                    <button
                      key={i}
                      className="ex-btn"
                      onClick={() => send(q)}
                      style={{
                        background: 'rgba(255,255,255,0.02)', color: '#4B5563',
                        border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8,
                        padding: '6px 10px', fontSize: '0.72rem', cursor: 'pointer',
                        textAlign: 'left', transition: 'all 0.15s', lineHeight: 1.5,
                      }}
                    >{q}</button>
                  ))}
                </div>
              </div>
            )}

            {/* Bubbles */}
            {messages.map((m, i) => (
              <div key={i} className="msg-in" style={{
                display: 'flex', gap: 7,
                justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
                alignItems: 'flex-end',
              }}>
                {m.role === 'assistant' && (
                  <div style={{
                    width: 24, height: 24, borderRadius: 7, flexShrink: 0,
                    background: 'linear-gradient(135deg,#6366F1,#06B6D4)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: '0 0 10px rgba(99,102,241,0.4)', fontSize: '0.7rem',
                  }}>
                    <svg width="11" height="11" viewBox="0 0 20 20" fill="none"><path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  </div>
                )}
                <div style={{
                  maxWidth: '82%',
                  padding: '0.55rem 0.8rem',
                  background: m.role === 'user' ? 'rgba(99,102,241,0.16)' : 'rgba(255,255,255,0.04)',
                  border: m.role === 'user' ? '1px solid rgba(99,102,241,0.28)' : '1px solid rgba(255,255,255,0.07)',
                  borderRadius: m.role === 'user' ? '12px 12px 3px 12px' : '3px 12px 12px 12px',
                  fontSize: '0.78rem',
                  color: m.role === 'user' ? '#C7D2FE' : '#9CA3AF',
                  lineHeight: 1.65,
                }}>
                  {m.role === 'assistant'
                    ? <div dangerouslySetInnerHTML={{ __html: format(m.content) }} />
                    : m.content
                  }
                </div>
              </div>
            ))}

            {/* Typing */}
            {loading && (
              <div style={{ display: 'flex', gap: 7, alignItems: 'flex-end' }}>
                <div style={{ width: 24, height: 24, borderRadius: 7, background: 'linear-gradient(135deg,#6366F1,#06B6D4)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <svg width="11" height="11" viewBox="0 0 20 20" fill="none"><path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </div>
                <div style={{ padding: '0.55rem 0.8rem', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '3px 12px 12px 12px', display: 'flex', gap: 4, alignItems: 'center' }}>
                  {[1,2,3].map(n => (
                    <span key={n} className={`td-${n}`} style={{ width: 4, height: 4, borderRadius: '50%', background: '#6366F1', display: 'inline-block' }} />
                  ))}
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.18)', borderRadius: 9, padding: '0.5rem 0.75rem', color: '#FCA5A5', fontSize: '0.72rem', lineHeight: 1.5 }}>
                ⚠ {error}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', padding: '0.6rem 0.7rem', background: 'rgba(255,255,255,0.015)', flexShrink: 0 }}>
            <div
              className="chat-input-wrap"
              style={{
                display: 'flex', gap: 6, alignItems: 'center',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.09)',
                borderRadius: 10, padding: '7px 7px 7px 12px',
                transition: 'border-color 0.15s, box-shadow 0.15s',
              }}
            >
              <input
                ref={inputRef}
                type="text" value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
                placeholder="Ask about basins, forecasts, prices…"
                style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: '#F9FAFB', fontSize: '0.78rem', fontFamily: 'inherit', lineHeight: 1.5 }}
              />
              <button
                onClick={() => send()}
                disabled={loading || !input.trim()}
                style={{
                  width: 28, height: 28, borderRadius: 7, border: 'none',
                  cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
                  background: loading || !input.trim()
                    ? 'rgba(255,255,255,0.05)'
                    : 'linear-gradient(135deg,#6366F1,#06B6D4)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0, transition: 'all 0.15s',
                  boxShadow: !loading && input.trim() ? '0 0 10px rgba(99,102,241,0.4)' : 'none',
                }}
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M6 10.5V1.5M6 1.5L2 5.5M6 1.5L10 5.5"
                    stroke={!loading && input.trim() ? 'white' : '#374151'}
                    strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
            <div style={{ textAlign: 'center', marginTop: 5, fontSize: '0.58rem', color: '#374151', letterSpacing: '0.03em' }}>
              Enter to send · OilPulse AI Analyst
            </div>
          </div>
        </div>
      )}
    </>
  )
}

import React, { useState, useRef, useEffect } from 'react'
import { postAiChat } from '../../api/client'
import GlassCard from '../GlassCard'
import SectionHeader from '../SectionHeader'

const EXAMPLES = [
  'Which region has the highest projected production?',
  'Summarize the investment opportunity in the Permian Basin.',
  'Compare Eagle Ford vs Bakken for investment attractiveness.',
  'Which regions are declining and should be avoided?',
  'What is the SARIMA forecast accuracy for oil production?',
  'Which region has the highest revenue potential and why?',
  'What happens to Permian revenue if WTI drops to $55/bbl?',
  'Rank all 5 regions for a long-term 5-year investment.',
]

export default function AITab({ scoresData, selectedYear, commodity }) {
  const [messages, setMessages] = useState([])
  const [input,    setInput]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (text) => {
    if (!text.trim() || loading) return
    const userMsg = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    setError(null)
    try {
      const allMsgs = [...messages, userMsg]
      const res = await postAiChat({ messages: allMsgs, selected_year: selectedYear, commodity })
      setMessages(prev => [...prev, { role: 'assistant', content: res.answer }])
    } catch (e) {
      const msg = e.response?.data?.detail || e.message
      if (msg?.includes('OPENAI_API_KEY')) {
        setError('OpenAI API key not configured. Set OPENAI_API_KEY in your .env file.')
      } else {
        setError(`AI error: ${msg}`)
      }
    } finally {
      setLoading(false)
    }
  }

  const formatMsg = (text) => {
    return text
      .replace(/\[DATA\]/g, '<span style="background:rgba(1,181,116,0.15);color:#01B574;padding:2px 6px;border-radius:6px;font-size:0.78em;font-weight:700;border:1px solid rgba(1,181,116,0.3)">DATA</span>')
      .replace(/\[INFERENCE\]/g, '<span style="background:rgba(255,181,71,0.12);color:#FFB547;padding:2px 6px;border-radius:6px;font-size:0.78em;font-weight:700;border:1px solid rgba(255,181,71,0.3)">INFERENCE</span>')
  }

  const topRegion = scoresData.sort((a,b)=>b.score-a.score)[0]

  return (
    <div>
      <SectionHeader>🤖 OilPulse AI Analyst</SectionHeader>
      <p style={{ color:'#64748B', fontSize:'0.85rem', marginBottom:'1rem' }}>
        Ask questions about live production data, forecasts, and investment decisions. The AI answers using real Supabase data — not training data.
      </p>

      {/* Example questions */}
      <div style={{ marginBottom:'1rem' }}>
        <div style={{ fontSize:'0.78rem', color:'#475569', fontWeight:600, marginBottom:6 }}>💡 Try these questions:</div>
        <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
          {EXAMPLES.map((q,i) => (
            <button key={i} onClick={() => send(q)} style={{
              background:'rgba(255,255,255,0.04)', color:'#64748B',
              border:'1px solid rgba(255,255,255,0.08)', borderRadius:8,
              padding:'4px 10px', fontSize:'0.76rem', cursor:'pointer',
              transition:'all 0.15s',
            }}
            onMouseEnter={e => { e.target.style.background='rgba(67,24,255,0.15)'; e.target.style.color='#A78BFA' }}
            onMouseLeave={e => { e.target.style.background='rgba(255,255,255,0.04)'; e.target.style.color='#64748B' }}
            >
              {q.length > 50 ? q.slice(0,48)+'...' : q}
            </button>
          ))}
        </div>
      </div>

      {/* Chat window */}
      <GlassCard style={{ padding:0, overflow:'hidden', marginBottom:'1rem' }}>
        <div className="chat-scroll" style={{ height:400, overflowY:'auto', padding:'1rem' }}>
          {messages.length === 0 && (
            <div style={{ textAlign:'center', color:'#334155', marginTop:'5rem' }}>
              <div style={{ fontSize:'2.5rem', marginBottom:'0.5rem' }}>🤖</div>
              <div style={{ fontWeight:600, color:'#475569' }}>Ask me about the data</div>
              <div style={{ fontSize:'0.8rem', marginTop:4, color:'#334155' }}>I answer with live numbers from Supabase</div>
              {topRegion && (
                <div style={{ marginTop:'1.5rem', background:'rgba(255,255,255,0.03)', borderRadius:12, padding:'1rem', textAlign:'left', border:'1px solid rgba(255,255,255,0.06)', maxWidth:480, margin:'1.5rem auto 0' }}>
                  <div style={{ fontWeight:600, color:'#F1F5F9', marginBottom:6 }}>Example answer preview:</div>
                  <div style={{ fontSize:'0.82rem', color:'#94A3B8', lineHeight:1.6 }}>
                    <span style={{ background:'rgba(1,181,116,0.15)',color:'#01B574',padding:'1px 5px',borderRadius:5,fontSize:'0.72em',fontWeight:700,border:'1px solid rgba(1,181,116,0.3)' }}>DATA</span>
                    {' '}<b style={{color:'#F1F5F9'}}>{topRegion.region}</b> leads with a score of <b style={{color:'#F1F5F9'}}>{Number(topRegion.score||0).toFixed(1)}/100</b> and ${Number(topRegion.revenue_potential||0).toLocaleString('en',{maximumFractionDigits:0})}M revenue potential.
                    <br/><br/>
                    <span style={{ background:'rgba(255,181,71,0.12)',color:'#FFB547',padding:'1px 5px',borderRadius:5,fontSize:'0.72em',fontWeight:700,border:'1px solid rgba(255,181,71,0.3)' }}>INFERENCE</span>
                    {' '}This combination suggests {topRegion.region} remains the primary target for capital deployment in {selectedYear}.
                  </div>
                </div>
              )}
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} style={{
              display:'flex', gap:10, marginBottom:'1rem',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}>
              {msg.role === 'assistant' && (
                <div style={{ flexShrink:0, width:32, height:32, borderRadius:'50%', background:'rgba(67,24,255,0.3)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:'0.9rem', border:'1px solid rgba(67,24,255,0.5)' }}>🤖</div>
              )}
              <div style={{
                maxWidth:'80%', padding:'0.75rem 1rem', borderRadius:14,
                background: msg.role === 'user' ? 'rgba(0,117,255,0.25)' : 'rgba(255,255,255,0.05)',
                border: msg.role === 'user' ? '1px solid rgba(0,117,255,0.4)' : '1px solid rgba(255,255,255,0.08)',
                fontSize:'0.85rem', color:'#E2E8F0', lineHeight:1.6,
                borderRadius: msg.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                maxWidth: '80%', padding: '0.75rem 1rem',
              }}>
                {msg.role === 'assistant'
                  ? <div dangerouslySetInnerHTML={{ __html: formatMsg(msg.content).replace(/\n/g,'<br/>') }} />
                  : msg.content
                }
              </div>
              {msg.role === 'user' && (
                <div style={{ flexShrink:0, width:32, height:32, borderRadius:'50%', background:'rgba(0,117,255,0.3)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:'0.9rem', border:'1px solid rgba(0,117,255,0.5)' }}>👤</div>
              )}
            </div>
          ))}

          {loading && (
            <div style={{ display:'flex', gap:10, marginBottom:'1rem' }}>
              <div style={{ flexShrink:0, width:32, height:32, borderRadius:'50%', background:'rgba(67,24,255,0.3)', display:'flex', alignItems:'center', justifyContent:'center' }}>🤖</div>
              <div style={{ padding:'0.75rem 1rem', background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.08)', borderRadius:'14px 14px 14px 4px' }}>
                <span style={{ color:'#475569', fontSize:'0.85rem' }}>Analyzing live data</span>
                <span style={{ animation:'blink 1s infinite', color:'#4318FF' }}> ...</span>
              </div>
            </div>
          )}

          {error && (
            <div style={{ background:'rgba(227,26,26,0.1)', border:'1px solid rgba(227,26,26,0.3)', borderRadius:10, padding:'0.75rem 1rem', color:'#FCA5A5', fontSize:'0.82rem', marginBottom:'0.5rem' }}>
              ⚠️ {error}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{ borderTop:'1px solid rgba(226,232,240,0.08)', padding:'0.8rem 1rem', display:'flex', gap:8 }}>
          <input
            type="text" value={input} onChange={e=>setInput(e.target.value)}
            onKeyDown={e=>e.key==='Enter' && send(input)}
            placeholder="Ask about regional data, forecasts, or investment decisions..."
            style={{
              flex:1, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(226,232,240,0.12)',
              borderRadius:10, padding:'8px 14px', color:'#F1F5F9', fontSize:'0.85rem', outline:'none',
            }}
          />
          <button onClick={() => send(input)} disabled={loading||!input.trim()} style={{
            background: loading||!input.trim() ? 'rgba(67,24,255,0.2)' : '#4318FF',
            color: loading||!input.trim() ? '#7551FF66' : '#fff',
            border:'none', borderRadius:10, padding:'8px 18px', cursor: loading ? 'not-allowed' : 'pointer',
            fontWeight:600, fontSize:'0.85rem', flexShrink:0,
          }}>Send</button>
          {messages.length > 0 && (
            <button onClick={()=>setMessages([])} style={{
              background:'rgba(255,255,255,0.04)', color:'#475569', border:'1px solid rgba(255,255,255,0.08)',
              borderRadius:10, padding:'8px 12px', cursor:'pointer', fontSize:'0.8rem',
            }}>🗑️</button>
          )}
        </div>
      </GlassCard>

      {/* Data context expander */}
      <details style={{ background:'rgba(255,255,255,0.02)', border:'1px solid rgba(255,255,255,0.06)', borderRadius:10, padding:'0.75rem 1rem' }}>
        <summary style={{ cursor:'pointer', color:'#475569', fontSize:'0.8rem', fontWeight:600 }}>
          🔍 View live data context sent to AI (transparency)
        </summary>
        <div style={{ marginTop:'0.5rem', fontSize:'0.75rem', color:'#475569', lineHeight:1.7 }}>
          {scoresData.length > 0 ? (
            <div>
              <div style={{ color:'#94A3B8', marginBottom:4 }}>Investment Scores snapshot:</div>
              {scoresData.sort((a,b)=>b.score-a.score).map(r => (
                <div key={r.region}>
                  {r.region}: Score={Number(r.score||0).toFixed(1)} | YoY={Number(r.yoy_growth||0).toFixed(2)}% | Revenue=${Number(r.revenue_potential||0).toLocaleString('en',{maximumFractionDigits:0})}M
                </div>
              ))}
              <div style={{ marginTop:6, color:'#334155', fontSize:'0.7rem' }}>All [DATA] claims in answers are grounded in these numbers.</div>
            </div>
          ) : <div>No data loaded yet.</div>}
        </div>
      </details>
    </div>
  )
}

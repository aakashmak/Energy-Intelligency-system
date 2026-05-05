import React, { useState, useCallback } from 'react'
import Plot from 'react-plotly.js'
import { useQuery } from '@tanstack/react-query'
import { fetchRegionPresets, postWellEcon } from '../../api/client'
import SectionHeader from '../SectionHeader'
import GlassCard from '../GlassCard'

const CHART_BG = '#040507', GRID = 'rgba(255,255,255,0.04)', AXIS_CLR = '#374151', FONT_CLR = '#374151', LEGEND_BG = 'rgba(4,5,7,0.96)'

function Inp({ label, value, onChange, min, max, step=1, unit='', help='' }) {
  return (
    <div>
      <label style={{ display:'block', fontSize:'0.72rem', color:'#64748B', marginBottom:3 }}>
        {label} {unit && <span style={{ color:'#334155' }}>({unit})</span>}
      </label>
      <input type="number" value={value} min={min} max={max} step={step}
        onChange={e => onChange(Number(e.target.value))} />
      {help && <div style={{ fontSize:'0.65rem', color:'#334155', marginTop:2 }}>{help}</div>}
    </div>
  )
}

export default function WellEconTab({ selectedRegion, commodity }) {
  const { data: presets = {} } = useQuery({ queryKey:['presets'], queryFn: fetchRegionPresets, staleTime: Infinity })

  const defaults = (selectedRegion && presets[selectedRegion]) || {
    ip_rate:900, di:70, b_factor:1.1, d_terminal:6, dc_cost:7.5, loe:8.0,
    price:72.0, royalty:22.5, sev_tax:4.6, wi:100, discount_rate:10, commodity:'oil',
  }

  const [inputs, setInputs] = useState({ ...defaults, discount_rate:10, months:240 })
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  const set = useCallback((key) => (val) => setInputs(p => ({ ...p, [key]: val })), [])

  const applyPreset = (region) => {
    if (presets[region]) {
      setInputs(p => ({ ...p, ...presets[region], discount_rate:p.discount_rate, months:p.months }))
    }
  }

  const run = async () => {
    setLoading(true); setError(null)
    try {
      const res = await postWellEcon(inputs)
      setResults(res)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  const fmtM = (v) => v == null ? 'N/A' : v >= 0 ? `$${(v/1e6).toFixed(2)}M` : `-$${(Math.abs(v)/1e6).toFixed(2)}M`

  return (
    <div>
      <SectionHeader>💰 Well Economics Calculator</SectionHeader>
      <p style={{ color:'#64748B', fontSize:'0.82rem', marginBottom:'1rem' }}>
        Arps hyperbolic decline curve + DCF financial model. All calculations run instantly.
      </p>

      {/* Region presets */}
      {Object.keys(presets).length > 0 && (
        <div style={{ marginBottom:'1rem' }}>
          <div style={{ fontSize:'0.75rem', color:'#475569', fontWeight:600, marginBottom:6 }}>Quick presets (basin averages):</div>
          <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
            {Object.entries(presets).map(([region, p]) => (
              <button key={region} onClick={() => applyPreset(region)} style={{
                padding:'5px 12px', borderRadius:8, fontSize:'0.78rem', fontWeight:600, cursor:'pointer',
                background: selectedRegion===region ? 'rgba(67,24,255,0.3)' : 'rgba(255,255,255,0.04)',
                color: selectedRegion===region ? '#A78BFA' : '#64748B',
                border: selectedRegion===region ? '1px solid rgba(67,24,255,0.5)' : '1px solid rgba(255,255,255,0.08)',
              }}>
                {region} {p.commodity === 'gas' ? '🔥' : '🛢️'}
              </button>
            ))}
          </div>
        </div>
      )}

      <div style={{ display:'grid', gridTemplateColumns:'320px 1fr', gap:'1.5rem', alignItems:'start' }}>
        {/* Inputs panel */}
        <GlassCard style={{ padding:'1.2rem' }}>
          <div style={{ fontSize:'0.85rem', color:'#94A3B8', fontWeight:700, marginBottom:'1rem' }}>⚙️ Well Parameters</div>
          <div style={{ display:'flex', flexDirection:'column', gap:'0.8rem' }}>
            <div>
              <label style={{ fontSize:'0.72rem', color:'#64748B', display:'block', marginBottom:3 }}>Commodity</label>
              <div style={{ display:'flex', gap:6 }}>
                {['oil','gas'].map(c=>(
                  <button key={c} onClick={()=>setInputs(p=>({...p,commodity:c}))} style={{
                    flex:1, padding:'5px 0', borderRadius:8, fontSize:'0.8rem', fontWeight:600, cursor:'pointer',
                    background: inputs.commodity===c?'#4318FF':'rgba(255,255,255,0.04)',
                    color: inputs.commodity===c?'#fff':'#64748B',
                    border: inputs.commodity===c?'1px solid #4318FF':'1px solid rgba(255,255,255,0.08)',
                  }}>{c==='oil'?'🛢️ Oil':'🔥 Gas'}</button>
                ))}
              </div>
            </div>
            <Inp label="Initial Production Rate" value={inputs.ip_rate} onChange={set('ip_rate')} min={10} max={10000} step={50} unit={inputs.commodity==='oil'?'bbl/day':'Mcf/day'} />
            <Inp label="Initial Decline Rate" value={inputs.di} onChange={set('di')} min={5} max={99} step={1} unit="% / year" />
            <Inp label="B-Factor (hyperbolic)" value={inputs.b_factor} onChange={set('b_factor')} min={0.1} max={2.0} step={0.1} />
            <Inp label="Terminal Decline Rate" value={inputs.d_terminal} onChange={set('d_terminal')} min={1} max={20} step={0.5} unit="% / year" />
            <div style={{ borderTop:'1px solid rgba(255,255,255,0.06)', paddingTop:'0.8rem' }}>
              <div style={{ fontSize:'0.72rem', color:'#475569', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:6 }}>Economics</div>
            </div>
            <Inp label="D&C Capital Cost" value={inputs.dc_cost} onChange={set('dc_cost')} min={0.5} max={100} step={0.5} unit="$MM" />
            <Inp label="Lease Operating Expense" value={inputs.loe} onChange={set('loe')} min={0.1} max={50} step={0.5} unit={inputs.commodity==='oil'?'$/bbl':'$/Mcf'} />
            <Inp label="Commodity Price" value={inputs.price} onChange={set('price')} min={10} max={300} step={0.5} unit={inputs.commodity==='oil'?'$/bbl':'$/MMcf'} />
            <Inp label="Royalty Rate" value={inputs.royalty} onChange={set('royalty')} min={0} max={50} step={0.25} unit="%" />
            <Inp label="Severance Tax" value={inputs.sev_tax} onChange={set('sev_tax')} min={0} max={20} step={0.1} unit="%" />
            <Inp label="Working Interest" value={inputs.wi} onChange={set('wi')} min={1} max={100} step={1} unit="%" />
            <Inp label="Discount Rate (NPV)" value={inputs.discount_rate} onChange={set('discount_rate')} min={1} max={50} step={1} unit="%" />
          </div>
          <button onClick={run} disabled={loading} style={{
            width:'100%', marginTop:'1rem', padding:'10px 0', borderRadius:12, fontSize:'0.9rem', fontWeight:700,
            background: loading ? 'rgba(67,24,255,0.2)' : 'linear-gradient(135deg,#4318FF,#0075FF)',
            color: loading ? '#7551FF66' : '#fff', border:'none', cursor: loading?'not-allowed':'pointer',
          }}>
            {loading ? '⏳ Calculating...' : '▶ Calculate'}
          </button>
          {error && <div style={{ marginTop:8, color:'#FCA5A5', fontSize:'0.8rem' }}>⚠️ {error}</div>}
        </GlassCard>

        {/* Results panel */}
        <div>
          {!results ? (
            <GlassCard style={{ textAlign:'center', padding:'3rem' }}>
              <div style={{ fontSize:'2.5rem', marginBottom:8 }}>💰</div>
              <div style={{ color:'#475569', fontWeight:600 }}>Configure inputs and click Calculate</div>
              <div style={{ color:'#334155', fontSize:'0.8rem', marginTop:4 }}>NPV, IRR, payback period, and production forecasts</div>
            </GlassCard>
          ) : (
            <>
              {/* KPI results */}
              <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:'0.8rem', marginBottom:'1rem' }}>
                {[
                  ['NPV', fmtM(results.npv), `@ ${inputs.discount_rate}% discount`, results.npv>=0?'#01B574':'#E31A1A'],
                  ['IRR', results.irr!=null?`${results.irr.toFixed(1)}%`:'N/A', 'annual return', results.irr>10?'#01B574':'#E31A1A'],
                  ['Payback', results.payback_month!=null?`${results.payback_month} mo`:'Never', 'to breakeven', '#FFB547'],
                  ['EUR', `${results.eur?.toFixed(2)} ${results.eur_unit}`, '20-year recovery', '#63B3ED'],
                ].map(([l,v,s,c])=>(
                  <GlassCard key={l}>
                    <div style={{ fontSize:'0.7rem', color:'#475569', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:4 }}>{l}</div>
                    <div style={{ fontSize:'1.5rem', fontWeight:800, color:c||'#F1F5F9' }}>{v}</div>
                    <div style={{ fontSize:'0.72rem', color:'#64748B', marginTop:2 }}>{s}</div>
                  </GlassCard>
                ))}
              </div>

              {/* Production decline chart */}
              <GlassCard style={{ marginBottom:'1rem' }}>
                <div style={{ fontSize:'0.85rem', color:'#94A3B8', fontWeight:600, marginBottom:8 }}>📉 Production Decline Curve</div>
                <Plot data={[
                  { x:results.months, y:results.monthly_prod, name:'Monthly Rate', mode:'lines', line:{color:'#3B82F6',width:2.5}, fill:'tozeroy', fillcolor:'rgba(59,130,246,0.07)' },
                  { x:results.months, y:results.cum_prod, name:'Cumulative', mode:'lines', line:{color:'#A855F7',width:2,dash:'dot'}, yaxis:'y2' },
                ]} layout={{
                  height:280, margin:{l:60,r:60,t:10,b:40},
                  plot_bgcolor:CHART_BG, paper_bgcolor:CHART_BG, font:{color:FONT_CLR},
                  xaxis:{gridcolor:GRID,color:AXIS_CLR,title:'Month'},
                  yaxis:{gridcolor:GRID,color:AXIS_CLR,title:inputs.commodity==='oil'?'bbl/month':'Mcf/month'},
                  yaxis2:{overlaying:'y',side:'right',color:'#A855F7',title:'Cumulative'},
                  legend:{orientation:'h',yanchor:'bottom',y:1.02,font:{color:FONT_CLR},bgcolor:LEGEND_BG},
                }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
              </GlassCard>

              {/* Cumulative cash flow chart */}
              <GlassCard style={{ marginBottom:'1rem' }}>
                <div style={{ fontSize:'0.85rem', color:'#94A3B8', fontWeight:600, marginBottom:8 }}>💵 Cumulative Cash Flow</div>
                <Plot data={[
                  {
                    x:results.months, y:results.cumulative_cash,
                    name:'Cumulative Cash Flow', mode:'lines',
                    line:{color:'#10B981',width:2.5},
                    fill:'tozeroy',
                    fillcolor: results.cumulative_cash?.slice(-1)[0] >= 0 ? 'rgba(1,181,116,0.08)' : 'rgba(227,26,26,0.08)',
                  },
                  results.payback_month != null && {
                    x:[results.payback_month], y:[0], name:'Payback', mode:'markers',
                    marker:{color:'#FFB547',size:12,symbol:'diamond'},
                  },
                ].filter(Boolean)} layout={{
                  height:260, margin:{l:80,r:20,t:10,b:40},
                  plot_bgcolor:CHART_BG, paper_bgcolor:CHART_BG, font:{color:FONT_CLR},
                  xaxis:{gridcolor:GRID,color:AXIS_CLR,title:'Month'},
                  yaxis:{gridcolor:GRID,color:AXIS_CLR,title:'Cumulative ($)'},
                  shapes:[{type:'line',x0:0,x1:240,y0:0,y1:0,line:{color:'rgba(255,255,255,0.15)',width:1}}],
                  legend:{font:{color:FONT_CLR},bgcolor:LEGEND_BG},
                }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
              </GlassCard>

              {/* Annual cash flow bars */}
              {results.annual_cash && (
                <GlassCard>
                  <div style={{ fontSize:'0.85rem', color:'#94A3B8', fontWeight:600, marginBottom:8 }}>📊 Annual Cash Flow</div>
                  <Plot data={[{
                    type:'bar',
                    x: results.annual_cash.map(r=>r.year),
                    y: results.annual_cash.map(r=>r.cash),
                    marker:{ color: results.annual_cash.map(r=>r.cash>=0?'rgba(1,181,116,0.8)':'rgba(227,26,26,0.8)') },
                    text: results.annual_cash.map(r=>r.cash>=0?`$${(r.cash/1e6).toFixed(1)}M`:`-$${(Math.abs(r.cash)/1e6).toFixed(1)}M`),
                    textposition:'outside', textfont:{color:FONT_CLR,size:9},
                  }]} layout={{
                    height:240, margin:{l:60,r:20,t:10,b:40},
                    plot_bgcolor:CHART_BG, paper_bgcolor:CHART_BG, font:{color:FONT_CLR},
                    xaxis:{gridcolor:GRID,color:AXIS_CLR,title:'Year'},
                    yaxis:{gridcolor:GRID,color:AXIS_CLR,title:'Cash Flow ($)'},
                    shapes:[{type:'line',x0:0.5,x1:20.5,y0:0,y1:0,line:{color:'rgba(255,255,255,0.15)',width:1}}],
                  }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
                </GlassCard>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

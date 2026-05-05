import React from 'react'
import Plot from 'react-plotly.js'
import { useQuery } from '@tanstack/react-query'
import { fetchColoradoMonthly, fetchColoradoFormations, fetchColoradoOperators, fetchColoradoDecline } from '../../api/client'
import SectionHeader from '../SectionHeader'
import GlassCard from '../GlassCard'

const CHART_BG = '#040507', GRID = 'rgba(255,255,255,0.04)', AXIS_CLR = '#374151', FONT_CLR = '#374151', LEGEND_BG = 'rgba(4,5,7,0.96)'
const FORM_COLORS = ['#3B82F6','#10B981','#F59E0B','#A855F7','#EF4444']

export default function ColoradoTab() {
  const { data: monthly   = [], isLoading: lM } = useQuery({ queryKey:['co_monthly'],    queryFn: fetchColoradoMonthly,    staleTime: 600000 })
  const { data: formation = [], isLoading: lF } = useQuery({ queryKey:['co_formations'],  queryFn: fetchColoradoFormations, staleTime: 600000 })
  const { data: operators = [], isLoading: lO } = useQuery({ queryKey:['co_operators'],   queryFn: fetchColoradoOperators,  staleTime: 600000 })
  const { data: decline   = [], isLoading: lD } = useQuery({ queryKey:['co_decline'],     queryFn: fetchColoradoDecline,    staleTime: 600000 })

  const loading = lM || lF || lO || lD

  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:400, color:'#475569' }}>
      <div style={{ textAlign:'center' }}><div style={{ fontSize:'2rem', marginBottom:8 }}>⏳</div>Loading Colorado data...</div>
    </div>
  )

  if (!monthly.length) return (
    <div>
      <SectionHeader>🔬 Colorado DJ Basin — Well-Level Case Study</SectionHeader>
      <GlassCard>
        <div style={{ textAlign:'center', padding:'2rem', color:'#64748B' }}>
          <div style={{ fontSize:'2rem', marginBottom:8 }}>⚠️</div>
          <div style={{ fontWeight:600, color:'#94A3B8' }}>Colorado data not loaded yet</div>
          <div style={{ fontSize:'0.82rem', marginTop:8, lineHeight:1.7 }}>
            Run the aggregator to populate Colorado data:<br />
            <code style={{ background:'rgba(255,255,255,0.05)', padding:'2px 6px', borderRadius:4 }}>
              python -m src.data.colorado.aggregator
            </code>
          </div>
          <div style={{ fontSize:'0.78rem', color:'#475569', marginTop:8 }}>
            Processes ~1GB of COGCC well-level CSVs and saves to Supabase (~5 min)
          </div>
        </div>
      </GlassCard>
    </div>
  )

  // Summary stats
  const totalOil   = monthly.reduce((s,r)=>s+(Number(r.oil_bbl)||0),0)
  const totalGas   = monthly.reduce((s,r)=>s+(Number(r.gas_mcf)||0),0)
  const totalWater = monthly.reduce((s,r)=>s+(Number(r.water_bbl)||0),0)
  const avgWells   = monthly.length ? monthly.reduce((s,r)=>s+(Number(r.active_wells)||0),0)/monthly.length : 0
  const minDate = monthly.reduce((m,r)=>!m||r.period<m?r.period:m,'')
  const maxDate = monthly.reduce((m,r)=>!m||r.period>m?r.period:m,'')

  // Monthly production chart traces
  const mSorted = [...monthly].sort((a,b)=>a.period<b.period?-1:1)
  const chartTraces = [
    { x:mSorted.map(r=>r.period), y:mSorted.map(r=>Number(r.oil_bbl)||0), name:'Oil (bbl)', mode:'lines',
      line:{color:'#3B82F6',width:2.5}, fill:'tozeroy', fillcolor:'rgba(59,130,246,0.07)' },
    { x:mSorted.map(r=>r.period), y:mSorted.map(r=>Number(r.gas_mcf)||0), name:'Gas (Mcf)', mode:'lines',
      line:{color:'#10B981',width:2,dash:'dot'} },
  ]
  const wellTrace = [
    { x:mSorted.map(r=>r.period), y:mSorted.map(r=>Number(r.active_wells)||0), name:'Active Wells', mode:'lines',
      line:{color:'#F97316',width:1.5}, yaxis:'y2' },
  ]

  // Formation chart
  const topFormations = [...new Set(formation.map(r=>r.formation))]
    .map(f=>({ f, total: formation.filter(r=>r.formation===f).reduce((s,r)=>s+(Number(r.oil_bbl)||0),0) }))
    .sort((a,b)=>b.total-a.total).slice(0,5).map(f=>f.f)

  const formYears = [...new Set(formation.map(r=>r.year))].sort()

  const formOilTraces = topFormations.map((f,i) => {
    const rows = formation.filter(r=>r.formation===f).sort((a,b)=>a.year-b.year)
    return { type:'bar', name:f, x:rows.map(r=>r.year), y:rows.map(r=>Number(r.oil_bbl)||0), marker:{color:FORM_COLORS[i%5]} }
  })

  // Top operators
  const opSorted = [...operators].sort((a,b)=>(Number(b.oil_bbl)||0)-(Number(a.oil_bbl)||0)).slice(0,10)
  const opTrace = {
    type:'bar', orientation:'h',
    x: opSorted.map(r=>Number(r.oil_bbl)||0),
    y: opSorted.map(r=>r.operator),
    marker:{ color:'#3B82F6', opacity:0.85 },
    text: opSorted.map(r=>`${((Number(r.oil_bbl)||0)/1e6).toFixed(1)}M bbl`),
    textposition:'outside', textfont:{color:FONT_CLR,size:11},
  }

  // Decline curve
  const dSorted = [...decline].sort((a,b)=>a.month_index-b.month_index)
  const declineOilTrace = {
    x:dSorted.map(r=>r.month_index), y:dSorted.map(r=>Number(r.avg_oil_bbl)||0),
    name:'Avg oil/well', mode:'lines+markers',
    line:{color:'#3B82F6',width:2.5}, marker:{size:5},
    fill:'tozeroy', fillcolor:'rgba(59,130,246,0.1)',
  }
  const declinePctTraces = [
    { x:dSorted.map(r=>r.month_index), y:dSorted.map(r=>Number(r.oil_pct_of_month1)||0), name:'Oil % of Month 1', mode:'lines+markers', line:{color:'#EF4444',width:2.5}, marker:{size:5} },
    { x:dSorted.map(r=>r.month_index), y:dSorted.map(r=>Number(r.gas_pct_of_month1)||0), name:'Gas % of Month 1', mode:'lines+markers', line:{color:'#10B981',width:2,dash:'dash'}, marker:{size:4} },
  ]

  // Decline KPIs
  const d1  = dSorted.find(r=>r.month_index===1)
  const d6  = dSorted.find(r=>r.month_index===6)
  const d12 = dSorted.find(r=>r.month_index===12)
  const d24 = dSorted.find(r=>r.month_index===24)
  const m1  = d1 ? Number(d1.avg_oil_bbl)||0 : 0

  const chartLayout = (extra={}) => ({
    height:360, margin:{l:50,r:20,t:30,b:40},
    plot_bgcolor:CHART_BG, paper_bgcolor:CHART_BG, font:{color:FONT_CLR},
    xaxis:{gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID},
    yaxis:{gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID},
    legend:{orientation:'h',yanchor:'bottom',y:1.02,xanchor:'left',x:0,font:{color:FONT_CLR},bgcolor:LEGEND_BG},
    ...extra,
  })

  return (
    <div>
      <SectionHeader>🔬 Colorado DJ Basin — Well-Level Case Study</SectionHeader>

      <div style={{ background:'linear-gradient(127.09deg,rgba(6,11,40,0.94) 19.41%,rgba(10,14,35,0.49) 76.65%)', border:'1px solid rgba(14,165,233,0.25)', borderLeft:'4px solid #0EA5E9', borderRadius:12, padding:'1rem 1.2rem', marginBottom:'1.5rem', backdropFilter:'blur(40px)' }}>
        <b style={{color:'#F1F5F9'}}>Why this matters:</b>
        <span style={{color:'#94A3B8'}}> While the main dashboard uses EIA state-level aggregates, this case study demonstrates OilPulse processing <b style={{color:'#E2E8F0'}}>10 years of well-level production data</b> (2015–2024) from the Colorado Oil &amp; Gas Conservation Commission (COGCC). Over 10 million individual well-month records aggregated into basin intelligence.</span>
      </div>

      {/* KPI Cards */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:'0.8rem', marginBottom:'1.5rem' }}>
        {[
          ['🛢️ Total Oil', `${(totalOil/1e6).toFixed(1)}M bbl`],
          ['🔥 Total Gas', `${(totalGas/1e6).toFixed(1)}M Mcf`],
          ['💧 Total Water', `${(totalWater/1e6).toFixed(1)}M bbl`],
          ['⛏️ Avg Wells/mo', avgWells.toFixed(0)],
          ['📅 Data Range', `${String(minDate).slice(0,7)} → ${String(maxDate).slice(0,7)}`],
        ].map(([l,v])=>(
          <GlassCard key={l}>
            <div style={{ fontSize:'0.7rem', color:'#475569', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:4 }}>{l}</div>
            <div style={{ fontSize:'1.3rem', fontWeight:800, color:'#F1F5F9' }}>{v}</div>
          </GlassCard>
        ))}
      </div>

      {/* Monthly production */}
      <SectionHeader>📈 Monthly Basin Production (2015–2024)</SectionHeader>
      <GlassCard style={{ marginBottom:'1rem' }}>
        <Plot data={[...chartTraces,...wellTrace]} layout={{
          ...chartLayout(),
          yaxis2:{overlaying:'y',side:'right',gridcolor:GRID,color:AXIS_CLR,showgrid:false,title:'Active Wells',title_font:{color:AXIS_CLR}},
          yaxis:{...chartLayout().yaxis,title:'Production Volume'},
        }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
      </GlassCard>

      {/* Formation breakdown */}
      {formOilTraces.length > 0 && (
        <>
          <SectionHeader>🪨 Production by Formation (Oil)</SectionHeader>
          <GlassCard style={{ marginBottom:'1rem' }}>
            <Plot data={formOilTraces} layout={{
              ...chartLayout(), barmode:'stack',
              yaxis:{...chartLayout().yaxis,title:'Oil (bbl)'},
            }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
          </GlassCard>
        </>
      )}

      {/* Top operators */}
      {opSorted.length > 0 && (
        <>
          <SectionHeader>🏢 Top 10 Operators by Cumulative Oil</SectionHeader>
          <GlassCard style={{ marginBottom:'1rem' }}>
            <Plot data={[opTrace]} layout={{
              ...chartLayout(), height:360,
              margin:{l:160,r:80,t:15,b:40},
              xaxis:{...chartLayout().xaxis,title:'Cumulative Oil (bbl)'},
              yaxis:{color:AXIS_CLR},
            }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
          </GlassCard>
        </>
      )}

      {/* Decline curves */}
      {dSorted.length > 0 && (
        <>
          <SectionHeader>📉 Normalized Well Decline Curve</SectionHeader>
          <p style={{ fontSize:'0.8rem', color:'#64748B', marginBottom:'0.8rem' }}>
            Average production over the first 36 months of a well's life (top 500 wells). Shows the typical steep initial decline characteristic of shale wells.
          </p>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1rem', marginBottom:'1rem' }}>
            <GlassCard>
              <Plot data={[declineOilTrace]} layout={{
                ...chartLayout({ height:300 }),
                title:{text:'Oil Decline (avg bbl/well/month)',font:{color:FONT_CLR,size:13}},
                xaxis:{...chartLayout().xaxis,title:'Months since first production'},
                yaxis:{...chartLayout().yaxis,title:'Avg Oil (bbl)'},
              }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
            </GlassCard>
            <GlassCard>
              <Plot data={declinePctTraces} layout={{
                ...chartLayout({ height:300 }),
                title:{text:'Decline Rate (% of Month 1)',font:{color:FONT_CLR,size:13}},
                xaxis:{...chartLayout().xaxis,title:'Months since first production'},
                yaxis:{...chartLayout().yaxis,title:'% of Month 1',range:[0,110]},
              }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
            </GlassCard>
          </div>

          {m1 > 0 && (
            <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:'0.8rem', marginBottom:'1rem' }}>
              {[
                ['Month 1 avg', `${m1.toFixed(0)} bbl`, 'Initial production'],
                d6  && ['Month 6 decline', `${((1-Number(d6.avg_oil_bbl)/m1)*100).toFixed(0)}%`, `${Number(d6.avg_oil_bbl).toFixed(0)} bbl`],
                d12 && ['Month 12 decline',`${((1-Number(d12.avg_oil_bbl)/m1)*100).toFixed(0)}%`, `${Number(d12.avg_oil_bbl).toFixed(0)} bbl`],
                d24 && ['Month 24 decline',`${((1-Number(d24.avg_oil_bbl)/m1)*100).toFixed(0)}%`, `${Number(d24.avg_oil_bbl).toFixed(0)} bbl`],
              ].filter(Boolean).map(([l,v,s])=>(
                <GlassCard key={l}>
                  <div style={{ fontSize:'0.7rem', color:'#475569', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:4 }}>{l}</div>
                  <div style={{ fontSize:'1.5rem', fontWeight:800, color:'#F1F5F9' }}>{v}</div>
                  <div style={{ fontSize:'0.75rem', color:'#64748B', marginTop:2 }}>{s}</div>
                </GlassCard>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

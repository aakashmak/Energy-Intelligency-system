import React, { useMemo } from 'react'
import Plot from 'react-plotly.js'
import SectionHeader from '../SectionHeader'
import GlassCard from '../GlassCard'

const CHART_BG = '#040507', GRID = 'rgba(255,255,255,0.04)', AXIS_CLR = '#374151', FONT_CLR = '#374151', LEGEND_BG = 'rgba(4,5,7,0.96)'
const REGION_COLORS = { Permian:'#3B82F6', Bakken:'#10B981', 'Eagle Ford':'#F59E0B', Appalachia:'#A855F7', 'Gulf Coast':'#EF4444' }

export default function RigsTab({ rigsData, selectedRegion }) {
  const activeRegions = selectedRegion ? [selectedRegion] : Object.keys(REGION_COLORS)

  const latestRigs = useMemo(() => {
    const map = {}
    rigsData.forEach(r => {
      if (!map[r.region] || r.period > map[r.region].period) map[r.region] = r
    })
    return Object.values(map).sort((a,b) => b.rigs - a.rigs)
  }, [rigsData])

  const traces = useMemo(() => {
    return activeRegions.map(region => {
      const rows = rigsData.filter(r => r.region === region).sort((a,b)=>a.period<b.period?-1:1)
      return {
        x: rows.map(r=>r.period),
        y: rows.map(r=>Number(r.rigs||0)),
        name: region, mode:'lines+markers',
        line:{ color:REGION_COLORS[region]||'#6B7280', width:2.5 },
        marker:{ size:4, color:REGION_COLORS[region]||'#6B7280' },
        hovertemplate:`<b>${region}</b><br>%{x}<br>Rigs: <b>%{y}</b><extra></extra>`,
      }
    })
  }, [rigsData, activeRegions])

  const barTrace = useMemo(() => ({
    type:'bar',
    x: latestRigs.filter(r=>activeRegions.includes(r.region)).map(r=>r.region),
    y: latestRigs.filter(r=>activeRegions.includes(r.region)).map(r=>Number(r.rigs||0)),
    marker:{ color: latestRigs.filter(r=>activeRegions.includes(r.region)).map(r=>REGION_COLORS[r.region]||'#6B7280'), opacity:0.9 },
    text: latestRigs.filter(r=>activeRegions.includes(r.region)).map(r=>`${r.rigs} rigs`),
    textposition:'outside', textfont:{color:FONT_CLR, size:11},
    hovertemplate:'<b>%{x}</b><br>%{y} active rigs<extra></extra>',
  }), [latestRigs, activeRegions])

  const totalRigs = latestRigs.filter(r=>activeRegions.includes(r.region)).reduce((s,r)=>s+Number(r.rigs||0),0)

  return (
    <div>
      <SectionHeader>🏗️ Active Rig Activity</SectionHeader>

      {/* Summary KPIs */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:'0.8rem', marginBottom:'1.5rem' }}>
        {latestRigs.filter(r=>activeRegions.includes(r.region)).map(r => (
          <GlassCard key={r.region}>
            <div style={{ fontSize:'0.7rem', color:'#475569', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:4 }}>{r.region}</div>
            <div style={{ fontSize:'2rem', fontWeight:800, color:'#F59E0B' }}>🏗️ {r.rigs}</div>
            <div style={{ fontSize:'0.75rem', color:'#64748B', marginTop:4 }}>active rigs</div>
            <div style={{ fontSize:'0.7rem', color:'#334155', marginTop:2 }}>as of {String(r.period||'').slice(0,7)}</div>
          </GlassCard>
        ))}
      </div>

      {totalRigs > 0 && (
        <div style={{ background:'rgba(245,158,11,0.08)', border:'1px solid rgba(245,158,11,0.2)', borderRadius:10, padding:'8px 14px', marginBottom:'1rem', fontSize:'0.82rem', color:'#FCD34D' }}>
          🏗️ Total active rigs across selected regions: <b>{totalRigs}</b>
        </div>
      )}

      {/* Rig history chart */}
      <GlassCard style={{ marginBottom:'1rem' }}>
        <div style={{ fontSize:'0.85rem', color:'#94A3B8', fontWeight:600, marginBottom:8 }}>Rig Count History — All Regions</div>
        {traces.some(t=>t.x.length>0) ? (
          <Plot data={traces} layout={{
            height:360, margin:{l:50,r:20,t:10,b:40},
            plot_bgcolor:CHART_BG, paper_bgcolor:CHART_BG, font:{color:FONT_CLR},
            xaxis:{gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID},
            yaxis:{gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID,title:'Active Rigs'},
            legend:{orientation:'h',yanchor:'bottom',y:1.02,xanchor:'left',x:0,font:{color:FONT_CLR},bgcolor:LEGEND_BG},
          }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
        ) : (
          <div style={{ height:200, display:'flex', alignItems:'center', justifyContent:'center', color:'#334155' }}>No rig data available</div>
        )}
      </GlassCard>

      {/* Latest rig bar chart */}
      <GlassCard>
        <div style={{ fontSize:'0.85rem', color:'#94A3B8', fontWeight:600, marginBottom:8 }}>Latest Rig Counts — Comparison</div>
        <Plot data={[barTrace]} layout={{
          height:280, margin:{l:10,r:20,t:10,b:40},
          plot_bgcolor:CHART_BG, paper_bgcolor:CHART_BG, font:{color:FONT_CLR},
          xaxis:{gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID},
          yaxis:{gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID,title:'Rigs'},
          showlegend:false,
        }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
      </GlassCard>
    </div>
  )
}

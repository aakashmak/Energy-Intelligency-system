import React, { useMemo } from 'react'
import Plot from 'react-plotly.js'
import SectionHeader from '../SectionHeader'
import GlassCard from '../GlassCard'

const CHART_BG = '#040507', GRID = 'rgba(255,255,255,0.04)', AXIS_CLR = '#374151', FONT_CLR = '#374151', LEGEND_BG = 'rgba(4,5,7,0.96)'
const REGION_COLORS = { Permian:'#3B82F6', Bakken:'#10B981', 'Eagle Ford':'#F59E0B', Appalachia:'#A855F7', 'Gulf Coast':'#EF4444' }

function grade(s) { if(s>=75)return'A';if(s>=60)return'B';if(s>=45)return'C';return'D' }
function gradeColor(g) { return{A:'#01B574',B:'#63B3ED',C:'#FFB547',D:'#E31A1A'}[g]||'#6B7280' }
function fmtPct(v) { return (v >= 0 ? '+' : '') + Number(v).toFixed(2) + '%' }

export default function ScoresTab({ scoresData, prodData, fcData, qData, selectedYear, commodity, selectedRegion, currentYear }) {
  const activeRegions = selectedRegion ? [selectedRegion] : scoresData.map(r=>r.region)
  const filtered = scoresData.filter(r => activeRegions.includes(r.region)).sort((a,b) => b.score - a.score)

  const barTrace = useMemo(() => ({
    type:'bar',
    x: filtered.map(r => r.region),
    y: filtered.map(r => Number(r.score||0)),
    marker:{ color: filtered.map(r => REGION_COLORS[r.region]||'#6B7280'), opacity:0.9 },
    text: filtered.map(r => `${Number(r.score||0).toFixed(0)}/100`),
    textposition:'outside', textfont:{color:FONT_CLR,size:11},
    hovertemplate:'<b>%{x}</b><br>Score: %{y:.1f}/100<extra></extra>',
  }), [filtered])

  const kpis = ['yoy_growth','decline_rate','consistency_score','rel_performance']
  const kpiLabels = { yoy_growth:'YoY Growth %', decline_rate:'Decline Rate %', consistency_score:'Consistency', rel_performance:'Rel. Performance' }
  const kpiColors = ['#01B574','#E31A1A','#63B3ED','#A78BFA']

  const radarTraces = useMemo(() => filtered.map(r => ({
    type:'scatterpolar',
    r:[
      Math.max(0, Math.min(100, 50 + (Number(r.yoy_growth||0)))),
      Math.max(0, 100 - Math.abs(Number(r.decline_rate||0))*2),
      Number(r.consistency_score||0),
      Number(r.rel_performance||50),
      Number(r.score||0),
    ],
    theta:['YoY Growth','Low Decline','Consistency','Rel. Perf.','Inv. Score'],
    fill:'toself',
    fillcolor:`${REGION_COLORS[r.region]||'#6B7280'}22`,
    line:{color:REGION_COLORS[r.region]||'#6B7280',width:2},
    name:r.region,
  })), [filtered])

  return (
    <div>
      <SectionHeader>📊 Investment Scores — Regional KPI Detail</SectionHeader>

      {selectedRegion && (
        <div style={{ background:'rgba(67,24,255,0.1)', border:'1px solid rgba(67,24,255,0.3)', borderRadius:10, padding:'8px 14px', marginBottom:'1rem', fontSize:'0.82rem', color:'#A78BFA' }}>
          📍 Filtered to <b>{selectedRegion}</b> — clear selection in sidebar to see all regions
        </div>
      )}

      {/* Score cards */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:'0.8rem', marginBottom:'1.5rem' }}>
        {scoresData.sort((a,b)=>b.score-a.score).slice(0,5).map((row,i) => {
          const medals = ['🥇','🥈','🥉','4️⃣','5️⃣']
          const g = grade(Number(row.score||0))
          const yoy = Number(row.yoy_growth||0)
          return (
            <GlassCard key={row.region}>
              <div style={{ fontSize:'0.78rem', color:'#64748B', fontWeight:600, marginBottom:4 }}>{medals[i]} {row.region}</div>
              <div style={{ fontSize:'1.8rem', fontWeight:800, color:'#F1F5F9' }}>
                {Number(row.score||0).toFixed(0)}<span style={{ fontSize:'0.8rem', color:'#475569' }}>/100</span>
              </div>
              <div style={{ display:'inline-block', marginTop:4, background:gradeColor(g)+'22', color:gradeColor(g), fontSize:'0.7rem', fontWeight:700, padding:'2px 8px', borderRadius:6, border:`1px solid ${gradeColor(g)}44` }}>Grade {g}</div>
              <div style={{ fontSize:'0.78rem', marginTop:6, color:yoy>=0?'#01B574':'#E31A1A', fontWeight:600 }}>{fmtPct(yoy)} YoY</div>
              <div style={{ fontSize:'0.72rem', color:'#64748B', marginTop:2 }}>${Number(row.revenue_potential||0).toLocaleString('en',{maximumFractionDigits:0})}M revenue</div>
            </GlassCard>
          )
        })}
      </div>

      {/* Score bar chart */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1rem', marginBottom:'1.5rem' }}>
        <GlassCard>
          <div style={{ fontSize:'0.85rem', color:'#94A3B8', fontWeight:600, marginBottom:8 }}>Investment Score Comparison</div>
          <Plot data={[barTrace]} layout={{
            height:260, margin:{l:10,r:20,t:10,b:40},
            plot_bgcolor:CHART_BG, paper_bgcolor:CHART_BG, font:{color:FONT_CLR},
            xaxis:{gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID},
            yaxis:{gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID,range:[0,115]},
            showlegend:false,
          }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
        </GlassCard>

        <GlassCard>
          <div style={{ fontSize:'0.85rem', color:'#94A3B8', fontWeight:600, marginBottom:8 }}>Basin Radar — KPI Profile</div>
          <Plot data={radarTraces} layout={{
            height:260, margin:{l:20,r:20,t:20,b:20},
            paper_bgcolor:CHART_BG, font:{color:FONT_CLR},
            polar:{bgcolor:CHART_BG, radialaxis:{visible:true,range:[0,100],gridcolor:GRID,tickfont:{color:AXIS_CLR}}, angularaxis:{gridcolor:GRID,tickfont:{color:AXIS_CLR,size:10}}},
            legend:{font:{color:FONT_CLR},bgcolor:LEGEND_BG,bordercolor:'rgba(226,232,240,0.15)',borderwidth:1},
            showlegend:true,
          }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
        </GlassCard>
      </div>

      {/* KPI Detail per region */}
      <SectionHeader>🔍 Detailed KPI Breakdown</SectionHeader>
      {filtered.map(row => {
        const g = grade(Number(row.score||0))
        return (
          <GlassCard key={row.region} style={{ marginBottom:'0.8rem' }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'0.8rem' }}>
              <div style={{ fontWeight:700, fontSize:'1rem', color:REGION_COLORS[row.region]||'#F1F5F9' }}>
                {row.region}
              </div>
              <div style={{ display:'flex', gap:8 }}>
                <span style={{ background:gradeColor(g)+'22', color:gradeColor(g), padding:'3px 10px', borderRadius:10, fontSize:'0.8rem', fontWeight:700, border:`1px solid ${gradeColor(g)}44` }}>Grade {g}</span>
                <span style={{ color:'#475569', fontSize:'0.85rem' }}>Rank #{row.rank||'—'}</span>
              </div>
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(6,1fr)', gap:'0.8rem' }}>
              {[
                ['Score',          `${Number(row.score||0).toFixed(1)}/100`],
                ['YoY Growth',     fmtPct(Number(row.yoy_growth||0)),     Number(row.yoy_growth||0)>=0?'#01B574':'#E31A1A'],
                ['Decline Rate',   fmtPct(Number(row.decline_rate||0)),   '#E31A1A'],
                ['Revenue',        `$${Number(row.revenue_potential||0).toLocaleString('en',{maximumFractionDigits:0})}M`],
                ['Consistency',    `${Number(row.consistency_score||0).toFixed(1)}/100`],
                ['Rel. Perf.',     `${Number(row.rel_performance||50).toFixed(1)}/100`],
              ].map(([l,v,c])=>(
                <div key={l}>
                  <div style={{ fontSize:'0.68rem', color:'#475569', textTransform:'uppercase', letterSpacing:'0.05em', marginBottom:3 }}>{l}</div>
                  <div style={{ fontSize:'1rem', fontWeight:700, color:c||'#F1F5F9' }}>{v}</div>
                </div>
              ))}
            </div>
            {row.momentum != null && (
              <div style={{ marginTop:8, fontSize:'0.75rem', color:'#475569' }}>
                Momentum: <span style={{ color:'#94A3B8' }}>{Number(row.momentum||0).toFixed(4)}</span>
                &nbsp;|&nbsp; WTI used: <span style={{ color:'#94A3B8' }}>${Number(row.wti_price_used||72).toFixed(0)}/bbl</span>
                &nbsp;|&nbsp; HH used: <span style={{ color:'#94A3B8' }}>${Number(row.henry_price_used||2.5).toFixed(2)}/MMcf</span>
              </div>
            )}
          </GlassCard>
        )
      })}
    </div>
  )
}

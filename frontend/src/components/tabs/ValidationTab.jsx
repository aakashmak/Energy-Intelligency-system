import React, { useMemo } from 'react'
import Plot from 'react-plotly.js'
import SectionHeader from '../SectionHeader'
import GlassCard from '../GlassCard'

const CHART_BG = '#040507', GRID = 'rgba(255,255,255,0.04)', AXIS_CLR = '#374151', FONT_CLR = '#374151', LEGEND_BG = 'rgba(4,5,7,0.96)'
const REGION_COLORS = { Permian:'#3B82F6', Bakken:'#10B981', 'Eagle Ford':'#F59E0B', Appalachia:'#A855F7', 'Gulf Coast':'#EF4444' }

function gradeColor(g) { return{A:'#01B574',B:'#63B3ED',C:'#FFB547',D:'#E31A1A'}[g]||'#6B7280' }

export default function ValidationTab({ valData, prodData, fcData, commodity }) {
  const validationRows = useMemo(() => {
    if (valData && valData.length > 0) return valData
    // Compute MAPE from prod vs forecasts if no val table
    const regions = [...new Set(prodData.map(r=>r.region))]
    return regions.flatMap(region => ['oil','gas'].map(com => {
      const actuals  = prodData.filter(r=>r.region===region&&r.commodity===com)
      const forecasts = fcData.filter(r=>r.region===region&&r.commodity===com)
      if (!actuals.length || !forecasts.length) return null
      const matched = actuals.filter(a => forecasts.some(f=>f.period===a.period))
      if (!matched.length) return null
      const errors = matched.map(a => {
        const f = forecasts.find(f=>f.period===a.period)
        return f ? Math.abs((a.value - f.forecast) / (a.value||1)) * 100 : null
      }).filter(Boolean)
      const mape = errors.length ? errors.reduce((s,v)=>s+v,0)/errors.length : 0
      const grade = mape<5?'A':mape<10?'B':mape<20?'C':'D'
      return { region, commodity:com, mape, grade, mae: 0 }
    }).filter(Boolean))
  }, [valData, prodData, fcData])

  const filtered = validationRows.filter(r => r.commodity === commodity)

  const mapeTrace = useMemo(() => {
    const rows = filtered.sort((a,b)=>a.mape-b.mape)
    return {
      type:'bar', orientation:'h',
      x: rows.map(r=>Number(r.mape||0)),
      y: rows.map(r=>r.region),
      marker:{ color: rows.map(r=>REGION_COLORS[r.region]||'#6B7280'), opacity:0.85 },
      text: rows.map(r=>`${Number(r.mape||0).toFixed(2)}%`),
      textposition:'outside', textfont:{color:FONT_CLR,size:11},
      hovertemplate:'<b>%{y}</b><br>MAPE: %{x:.2f}%<extra></extra>',
    }
  }, [filtered])

  return (
    <div>
      <SectionHeader>🎯 SARIMA Forecast Accuracy</SectionHeader>
      <div style={{ background:'rgba(67,24,255,0.08)', border:'1px solid rgba(67,24,255,0.2)', borderRadius:10, padding:'0.75rem 1rem', marginBottom:'1rem', fontSize:'0.82rem', color:'#94A3B8', lineHeight:1.7 }}>
        <b style={{color:'#A78BFA'}}>Model:</b> SARIMA(1,1,1)(1,1,0)[12] trained on EIA historical monthly data.
        MAPE (Mean Absolute Percentage Error) measures forecast accuracy on held-out validation data.
        Grade A = &lt;5% MAPE (excellent), B = 5-10%, C = 10-20%, D = &gt;20%.
      </div>

      {/* Grade cards */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:'0.8rem', marginBottom:'1.5rem' }}>
        {filtered.map(r => {
          const g = r.grade || (Number(r.mape||0)<5?'A':Number(r.mape||0)<10?'B':Number(r.mape||0)<20?'C':'D')
          const gc = gradeColor(g)
          return (
            <GlassCard key={r.region+r.commodity}>
              <div style={{ fontSize:'0.7rem', color:'#475569', textTransform:'uppercase', marginBottom:4 }}>{r.region}</div>
              <div style={{ fontSize:'1.8rem', fontWeight:800, color:gc }}>{g}</div>
              <div style={{ fontSize:'0.75rem', color:'#64748B', marginTop:4 }}>Grade</div>
              <div style={{ fontSize:'0.85rem', color:'#94A3B8', marginTop:4 }}>MAPE: <b style={{color:gc}}>{Number(r.mape||0).toFixed(2)}%</b></div>
              {r.mae > 0 && <div style={{ fontSize:'0.75rem', color:'#475569', marginTop:2 }}>MAE: {Number(r.mae||0).toLocaleString('en',{maximumFractionDigits:0})}</div>}
            </GlassCard>
          )
        })}
      </div>

      {/* MAPE bar chart */}
      {filtered.length > 0 && (
        <GlassCard style={{ marginBottom:'1rem' }}>
          <div style={{ fontSize:'0.85rem', color:'#94A3B8', fontWeight:600, marginBottom:8 }}>
            MAPE by Region — {commodity.toUpperCase()}
          </div>
          <Plot data={[mapeTrace]} layout={{
            height:280, margin:{l:100,r:80,t:10,b:40},
            plot_bgcolor:CHART_BG, paper_bgcolor:CHART_BG, font:{color:FONT_CLR},
            xaxis:{gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID,title:'MAPE (%)'},
            yaxis:{color:AXIS_CLR},
            shapes:[{type:'line',x0:5,x1:5,y0:-0.5,y1:filtered.length-0.5,yref:'y',line:{color:'#01B574',width:1.5,dash:'dot'}},{type:'line',x0:10,x1:10,y0:-0.5,y1:filtered.length-0.5,yref:'y',line:{color:'#FFB547',width:1.5,dash:'dot'}}],
            annotations:[{x:5,y:filtered.length-0.3,xref:'x',yref:'y',text:'5% (A)',showarrow:false,font:{color:'#01B574',size:10}},{x:10,y:filtered.length-0.3,xref:'x',yref:'y',text:'10% (B)',showarrow:false,font:{color:'#FFB547',size:10}}],
          }} config={{displayModeBar:false,responsive:true}} style={{width:'100%'}} />
        </GlassCard>
      )}

      {/* No val data message */}
      {filtered.length === 0 && (
        <GlassCard>
          <div style={{ textAlign:'center', padding:'2rem', color:'#475569' }}>
            <div style={{ fontSize:'2rem', marginBottom:'0.5rem' }}>📊</div>
            <div style={{ fontWeight:600 }}>No validation data available</div>
            <div style={{ fontSize:'0.8rem', marginTop:4 }}>
              Run the forecasting pipeline to populate model_validation table.
            </div>
          </div>
        </GlassCard>
      )}

      {/* Methodology */}
      <GlassCard style={{ marginTop:'1rem' }}>
        <div style={{ fontSize:'0.85rem', color:'#94A3B8', fontWeight:700, marginBottom:8 }}>📖 Model Methodology</div>
        <div style={{ fontSize:'0.8rem', color:'#64748B', lineHeight:1.8 }}>
          <div><b style={{color:'#94A3B8'}}>Algorithm:</b> SARIMA(1,1,1)(1,1,0)[12] — Seasonal AutoRegressive Integrated Moving Average</div>
          <div><b style={{color:'#94A3B8'}}>Training data:</b> EIA Petroleum Supply Monthly + EIA Natural Gas Monthly (2015–present)</div>
          <div><b style={{color:'#94A3B8'}}>Forecast horizon:</b> 36 months (3 years) with 80% confidence intervals</div>
          <div><b style={{color:'#94A3B8'}}>Validation approach:</b> Hold-out last 12 months, compute MAPE on out-of-sample predictions</div>
          <div><b style={{color:'#94A3B8'}}>STEO integration:</b> EIA Short-Term Energy Outlook Table 10a used for near-term calibration</div>
          <div><b style={{color:'#94A3B8'}}>Why SARIMA?</b> Captures both trend and monthly seasonality inherent in oil/gas production patterns</div>
        </div>
      </GlassCard>
    </div>
  )
}

import React, { useState, useEffect, useMemo } from 'react'
import Plot from 'react-plotly.js'
import { postSensitivity } from '../../api/client'
import SectionHeader from '../SectionHeader'
import GlassCard from '../GlassCard'

const CHART_BG = '#040507', GRID = 'rgba(255,255,255,0.04)', AXIS_CLR = '#374151', FONT_CLR = '#374151'

const VAR_OPTIONS = [
  'Decline Rate (% adj.)',
  'Commodity Price ($/unit adj.)',
  'Production Volume (% adj.)',
  'Working Interest (% abs.)',
]

const METRIC_OPTIONS = ['production', 'revenue']

export default function SensitivityTab({ scoresData, prodData, fcData, qData, selectedYear, commodity, selectedRegion, currentYear, wtiPrice, hhPrice }) {
  const [xVar,    setXVar]    = useState('Commodity Price ($/unit adj.)')
  const [yVar,    setYVar]    = useState('Decline Rate (% adj.)')
  const [metric,  setMetric]  = useState('production')
  const [wiPct,   setWiPct]   = useState(100)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)

  // Compute base production from data
  const baseProd = useMemo(() => {
    const activeRegions = selectedRegion ? [selectedRegion] : (scoresData.map(r=>r.region))
    const yearData = fcData.filter(r => activeRegions.includes(r.region) && r.commodity === commodity && new Date(r.period).getFullYear() === selectedYear)
    if (yearData.length) return yearData.reduce((s,r)=>s+(Number(r.forecast)||0),0)
    const actData = prodData.filter(r => activeRegions.includes(r.region) && r.commodity === commodity && new Date(r.period).getFullYear() === selectedYear)
    if (actData.length) return actData.reduce((s,r)=>s+(Number(r.value)||0),0)
    // fallback: use scores projected_prod
    const srows = scoresData.filter(r => activeRegions.includes(r.region))
    return srows.reduce((s,r)=>s+(Number(r.projected_prod)||0),0) || 100000
  }, [selectedRegion, scoresData, prodData, fcData, commodity, selectedYear])

  const basePrice = commodity === 'oil' ? wtiPrice : hhPrice

  const runSensitivity = async () => {
    if (xVar === yVar) return
    setLoading(true)
    try {
      const res = await postSensitivity({ base_prod: baseProd, base_price: basePrice, x_var: xVar, y_var: yVar, commodity, metric, wi_pct: wiPct })
      setResults(res)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { runSensitivity() }, [xVar, yVar, metric, commodity, selectedYear, selectedRegion, wiPct])

  const heatmapData = useMemo(() => {
    if (!results) return null
    const { matrix, x_labels, y_labels } = results
    const zValues = matrix.map(row => row.map(cell => cell.pct))
    const textValues = matrix.map(row => row.map((cell,j) => {
      const val = metric === 'production' ? cell.value : cell.value
      const unit = metric === 'production' ? (commodity==='oil'?'Mbbl':'MMcf') : '$M'
      const formatted = metric === 'production' ? `${(val/1000).toFixed(0)}K` : `$${val.toFixed(1)}M`
      const pct = cell.pct >= 0 ? `+${cell.pct.toFixed(0)}%` : `${cell.pct.toFixed(0)}%`
      return `${formatted}<br>${pct}`
    }))
    return { zValues, textValues, x_labels, y_labels }
  }, [results, metric, commodity])

  return (
    <div>
      <SectionHeader>📐 Sensitivity Analysis — Stress Test Forecasts</SectionHeader>

      <div style={{ background:'rgba(67,24,255,0.08)', border:'1px solid rgba(67,24,255,0.2)', borderRadius:10, padding:'0.75rem 1rem', marginBottom:'1rem', fontSize:'0.82rem', color:'#94A3B8', lineHeight:1.7 }}>
        Shows how <b style={{color:'#A78BFA'}}>projected production</b> or <b style={{color:'#A78BFA'}}>net revenue</b> changes across two input variables.
        Green = above base case, Red = below base case. Base year: <b style={{color:'#F1F5F9'}}>{selectedYear}</b>.
        {selectedRegion && <span> Filtered to <b style={{color:'#A78BFA'}}>{selectedRegion}</b>.</span>}
      </div>

      {/* Controls */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:'1rem', marginBottom:'1.5rem' }}>
        <GlassCard style={{ padding:'0.9rem' }}>
          <label style={{ fontSize:'0.72rem', color:'#64748B', display:'block', marginBottom:4 }}>X Axis Variable</label>
          <select value={xVar} onChange={e=>{setXVar(e.target.value)}}>
            {VAR_OPTIONS.filter(v=>v!==yVar).map(v=><option key={v} value={v}>{v}</option>)}
          </select>
        </GlassCard>
        <GlassCard style={{ padding:'0.9rem' }}>
          <label style={{ fontSize:'0.72rem', color:'#64748B', display:'block', marginBottom:4 }}>Y Axis Variable</label>
          <select value={yVar} onChange={e=>{setYVar(e.target.value)}}>
            {VAR_OPTIONS.filter(v=>v!==xVar).map(v=><option key={v} value={v}>{v}</option>)}
          </select>
        </GlassCard>
        <GlassCard style={{ padding:'0.9rem' }}>
          <label style={{ fontSize:'0.72rem', color:'#64748B', display:'block', marginBottom:4 }}>Metric</label>
          <select value={metric} onChange={e=>setMetric(e.target.value)}>
            {METRIC_OPTIONS.map(m=><option key={m} value={m}>{m==='production'?'📦 Production':'💵 Net Revenue'}</option>)}
          </select>
        </GlassCard>
        <GlassCard style={{ padding:'0.9rem' }}>
          <label style={{ fontSize:'0.72rem', color:'#64748B', display:'block', marginBottom:4 }}>Working Interest %</label>
          <input type="number" value={wiPct} min={1} max={100} step={1} onChange={e=>setWiPct(Number(e.target.value))} />
        </GlassCard>
      </div>

      {/* Base case info */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:'0.8rem', marginBottom:'1.5rem' }}>
        {[
          ['Base Production', `${(baseProd/1000).toFixed(0)}K ${commodity==='oil'?'Mbbl':'MMcf'}`, '#63B3ED'],
          ['Base Price', `$${basePrice}/${commodity==='oil'?'bbl':'MMcf'}`, '#F59E0B'],
          ['Year', selectedYear, '#A78BFA'],
          ['Scenario', selectedRegion||'All Basins', '#10B981'],
        ].map(([l,v,c])=>(
          <GlassCard key={l}>
            <div style={{ fontSize:'0.7rem', color:'#475569', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:4 }}>{l}</div>
            <div style={{ fontSize:'1.2rem', fontWeight:700, color:c }}>{v}</div>
          </GlassCard>
        ))}
      </div>

      {/* Heatmap */}
      {loading && (
        <GlassCard style={{ textAlign:'center', padding:'3rem' }}>
          <div style={{ color:'#475569' }}>⏳ Building sensitivity matrix...</div>
        </GlassCard>
      )}

      {!loading && heatmapData && (
        <GlassCard style={{ marginBottom:'1rem' }}>
          <div style={{ fontSize:'0.85rem', color:'#94A3B8', fontWeight:600, marginBottom:8 }}>
            {metric === 'production' ? '📦 Production' : '💵 Net Revenue'} Sensitivity Matrix — % change from base case
          </div>
          <Plot
            data={[{
              type: 'heatmap',
              z: heatmapData.zValues,
              x: heatmapData.x_labels,
              y: heatmapData.y_labels,
              text: heatmapData.textValues,
              texttemplate: '%{text}',
              textfont: { size: 11, color: '#F1F5F9', family: 'Inter' },
              colorscale: [
                [0.0, '#7F1D1D'], [0.1, '#991B1B'], [0.2, '#B91C1C'],
                [0.4, '#374151'], [0.5, '#1E3A5F'],
                [0.6, '#065F46'], [0.8, '#047857'], [1.0, '#059669'],
              ],
              zmid: 0,
              colorbar: {
                tickfont: { color: AXIS_CLR },
                title: { text: '% change', font: { color: AXIS_CLR } },
                bgcolor: 'rgba(6,11,40,0.8)',
              },
              hoverongaps: false,
              hovertemplate: `<b>X: %{x}</b><br><b>Y: %{y}</b><br>%{text}<extra></extra>`,
            }]}
            layout={{
              height: 400, margin: { l: 140, r: 80, t: 20, b: 80 },
              paper_bgcolor: CHART_BG, plot_bgcolor: CHART_BG,
              font: { color: FONT_CLR },
              xaxis: { title: xVar, color: AXIS_CLR, gridcolor: GRID, title_font:{color:AXIS_CLR} },
              yaxis: { title: yVar, color: AXIS_CLR, gridcolor: GRID, title_font:{color:AXIS_CLR} },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%' }}
          />
          <div style={{ fontSize:'0.75rem', color:'#475569', marginTop:8 }}>
            🟢 Green = above base case &nbsp;|&nbsp; 🔴 Red = below base case &nbsp;|&nbsp; 🔵 Blue = base case
          </div>
        </GlassCard>
      )}

      {/* Summary stats */}
      {!loading && results && (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:'0.8rem' }}>
          {(() => {
            const allPcts = results.matrix.flat().map(c=>c.pct)
            const best = Math.max(...allPcts)
            const worst = Math.min(...allPcts)
            const spread = best - worst
            return [
              ['Base Case', results.base_val != null ? `${(results.base_val/1000).toFixed(0)}K ${metric==='production'?(commodity==='oil'?'Mbbl':'MMcf'):'$M'}` : '—', '#63B3ED'],
              ['Best Case', `+${best.toFixed(0)}%`, '#01B574'],
              ['Worst Case', `${worst.toFixed(0)}%`, '#E31A1A'],
              ['Range', `${spread.toFixed(0)}%`, '#FFB547'],
            ].map(([l,v,c])=>(
              <GlassCard key={l}>
                <div style={{ fontSize:'0.7rem', color:'#475569', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:4 }}>{l}</div>
                <div style={{ fontSize:'1.4rem', fontWeight:800, color:c }}>{v}</div>
              </GlassCard>
            ))
          })()}
        </div>
      )}
    </div>
  )
}

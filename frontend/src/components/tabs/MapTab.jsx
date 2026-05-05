import React, { useMemo, useState } from 'react'
import Plot from 'react-plotly.js'
import SectionHeader from '../SectionHeader'
import GlassCard from '../GlassCard'

const REGION_COORDS = {
  Permian:    { lat: 31.9,  lon: -102.3, state: 'TX/NM',          zoom: 5.2 },
  Bakken:     { lat: 47.8,  lon: -103.4, state: 'ND/MT',          zoom: 5.5 },
  'Eagle Ford':{ lat: 28.4, lon:  -98.1, state: 'TX',             zoom: 5.8 },
  Appalachia: { lat: 39.5,  lon:  -80.2, state: 'PA/WV/OH',       zoom: 5.5 },
  'Gulf Coast':{ lat: 28.0, lon:  -90.5, state: 'LA/TX Offshore', zoom: 5.0 },
}

const REGION_COLORS = {
  Permian: '#3B82F6', Bakken: '#10B981', 'Eagle Ford': '#F59E0B',
  Appalachia: '#A855F7', 'Gulf Coast': '#EF4444',
}

const REGION_POLYGONS = {
  Permian:      [[32.9,-104.2],[33.8,-103.1],[33.5,-101.8],[32.6,-100.9],[31.0,-100.8],[30.4,-101.6],[30.2,-102.8],[30.6,-104.3],[31.7,-104.8],[32.9,-104.2]],
  Bakken:       [[48.9,-104.3],[48.9,-102.4],[47.9,-101.3],[46.9,-101.2],[46.5,-102.8],[46.8,-104.5],[47.8,-104.9],[48.9,-104.3]],
  'Eagle Ford': [[29.6,-99.7],[29.9,-98.1],[29.3,-96.8],[28.2,-96.5],[27.2,-97.5],[27.0,-99.3],[28.3,-100.1],[29.6,-99.7]],
  Appalachia:   [[41.8,-81.1],[41.6,-78.4],[40.4,-76.8],[38.4,-78.2],[37.2,-80.4],[37.8,-82.8],[39.6,-82.5],[41.1,-82.1],[41.8,-81.1]],
  'Gulf Coast': [[30.1,-94.2],[30.1,-89.1],[29.1,-87.5],[27.2,-87.8],[26.5,-90.5],[27.1,-93.5],[28.3,-94.8],[29.8,-94.6],[30.1,-94.2]],
}

const CHART_BG  = '#060810'
const GRID      = 'rgba(255,255,255,0.05)'
const AXIS_CLR  = '#5A6A80'
const FONT_CLR  = '#5A6A80'
const LEGEND_BG = 'rgba(4,5,7,0.96)'

function hexToRgb(h) {
  const r = parseInt(h.slice(1,3),16), g = parseInt(h.slice(3,5),16), b = parseInt(h.slice(5,7),16)
  return [r,g,b]
}
function rgba(hex, a) { const [r,g,b] = hexToRgb(hex); return `rgba(${r},${g},${b},${a})` }
// Normalise "YYYY-MM" → "YYYY-MM-01" so Plotly always treats x as a date axis
function toISODate(p) {
  if (!p) return p
  if (/^\d{4}-\d{2}$/.test(String(p))) return p + '-01'
  return p
}
function grade(score) { if(score>=75)return'A'; if(score>=60)return'B'; if(score>=45)return'C'; return'D' }
function gradeColor(g) { return {A:'#10B981',B:'#3B82F6',C:'#F59E0B',D:'#EF4444'}[g]||'#6B7280' }
function fmtPct(v) { return v >= 0 ? `+${v.toFixed(2)}%` : `${v.toFixed(2)}%` }

// ── Production traces (actuals only) ──────────────────────────────────────

function buildProdTraces(prodData, qData, commodity, granularity, selectedRegion, selectedYear) {
  const regs   = selectedRegion ? [selectedRegion] : Object.keys(REGION_COLORS)
  const cutoff = new Date(selectedYear, 11, 31)

  if (granularity === 'monthly') {
    return regs.map(region => {
      const color = REGION_COLORS[region]
      const [r,g,b] = hexToRgb(color)
      const rows = prodData
        .filter(d => d.region===region && d.commodity===commodity && new Date(toISODate(d.period))<=cutoff)
        .sort((a,b) => a.period<b.period?-1:1)
      return {
        x: rows.map(d=>toISODate(d.period)), y: rows.map(d=>Number(d.value)||0),
        name: region, mode:'lines', line:{color, width:selectedRegion?2.8:2},
        ...(selectedRegion ? {fill:'tozeroy', fillcolor:`rgba(${r},${g},${b},0.08)`} : {}),
        hovertemplate:`<b>${region}</b> %{x|%b %Y}<br>%{y:,.0f}<extra></extra>`,
      }
    })
  }

  if (granularity === 'quarterly') {
    return regs.map(region => {
      const color = REGION_COLORS[region]
      const [r,g,b] = hexToRgb(color)

      // Primary: actual quarterly rows from qData
      let rows = qData
        .filter(d => d.region===region && d.commodity===commodity && !d.is_forecast)
        .sort((a,b) => a.year!==b.year ? a.year-b.year : a.quarter<b.quarter?-1:1)

      // Fallback: aggregate monthly prodData → quarters when qData is empty
      if (!rows.length) {
        const qMap = {}
        prodData
          .filter(d => d.region===region && d.commodity===commodity && new Date(toISODate(d.period))<=cutoff)
          .forEach(d => {
            const date = new Date(toISODate(d.period))
            const yr   = date.getFullYear()
            const q    = `Q${Math.floor(date.getMonth()/3)+1}`
            const key  = `${yr}||${q}`
            qMap[key]  = (qMap[key]||0) + (Number(d.value)||0)
          })
        rows = Object.entries(qMap)
          .map(([key,value]) => { const [year,quarter]=key.split('||'); return {year:Number(year),quarter,value} })
          .sort((a,b) => a.year!==b.year ? a.year-b.year : a.quarter<b.quarter?-1:1)
      }

      if (selectedRegion) {
        return {
          type:'bar', x:rows.map(d=>`${d.year} ${d.quarter}`), y:rows.map(d=>Number(d.value)||0),
          name:region, marker:{color:`rgba(${r},${g},${b},0.85)`},
          hovertemplate:'<b>%{x}</b><br>%{y:,.0f}<extra></extra>',
        }
      }
      return {
        x:rows.map(d=>`${d.year} ${d.quarter}`), y:rows.map(d=>Number(d.value)||0),
        name:region, mode:'lines+markers', line:{color,width:2}, marker:{size:4,color},
        hovertemplate:`<b>${region}</b> %{x}<br>%{y:,.0f}<extra></extra>`,
      }
    })
  }

  // yearly — fill gaps from quarterly actuals
  return regs.map(region => {
    const color = REGION_COLORS[region]
    const [r,g,b] = hexToRgb(color)
    const actMap = {}
    prodData.filter(d=>d.region===region&&d.commodity===commodity).forEach(d=>{
      const yr = new Date(toISODate(d.period)).getFullYear()
      actMap[yr] = (actMap[yr]||0)+(Number(d.value)||0)
    })
    const qYearMap = {}
    qData.filter(d=>d.region===region&&d.commodity===commodity&&!d.is_forecast).forEach(d=>{
      const yr = Number(d.year); qYearMap[yr] = (qYearMap[yr]||0)+(Number(d.value)||0)
    })
    Object.keys(qYearMap).forEach(yr => { const y=Number(yr); if(!actMap[y]) actMap[y]=qYearMap[y] })
    const years = Object.keys(actMap).map(Number).sort()
    return {
      type:'bar', x:years, y:years.map(y=>actMap[y]),
      name:region, marker:{color:selectedRegion?`rgba(${r},${g},${b},0.85)`:color},
      hovertemplate:`<b>${region}</b> %{x}<br>%{y:,.0f}<extra></extra>`,
    }
  })
}

// ── Forecast traces (SARIMA / qData forecasts only) ────────────────────────

function buildFcTraces(fcData, qData, commodity, granularity, selectedRegion, selectedYear) {
  const regs    = selectedRegion ? [selectedRegion] : Object.keys(REGION_COLORS)
  const maxYear = selectedYear + 2

  if (granularity === 'monthly') {
    return regs.flatMap(region => {
      const color = REGION_COLORS[region]
      const [r,g,b] = hexToRgb(color)
      const rows = fcData
        .filter(d => d.region===region && d.commodity===commodity)
        .sort((a,b) => a.period<b.period?-1:1)
      const traces = []
      if (selectedRegion && rows.some(d=>d.upper_ci!=null)) {
        const up  = rows.map(d=>Number(d.upper_ci??d.forecast)||0)
        const low = rows.map(d=>Number(d.lower_ci??d.forecast)||0)
        traces.push({
          x:[...rows.map(d=>toISODate(d.period)),...[...rows].reverse().map(d=>toISODate(d.period))],
          y:[...up,...low.reverse()], fill:'toself',
          fillcolor:`rgba(${r},${g},${b},0.1)`, line:{color:'rgba(0,0,0,0)'},
          showlegend:false, hoverinfo:'skip',
        })
      }
      traces.push({
        x:rows.map(d=>toISODate(d.period)), y:rows.map(d=>Number(d.forecast)||0),
        name:region, mode:'lines', line:{color, width:selectedRegion?2.8:2, dash:'dash'},
        hovertemplate:`<b>${region}</b> %{x|%b %Y}<br>Forecast: %{y:,.0f}<extra></extra>`,
      })
      return traces
    })
  }

  if (granularity === 'quarterly') {
    return regs.map(region => {
      const color = REGION_COLORS[region]
      const [r,g,b] = hexToRgb(color)

      // Primary: quarterly forecast rows from qData
      let rows = qData
        .filter(d => d.region===region && d.commodity===commodity && d.is_forecast && Number(d.year)<=maxYear)
        .sort((a,b) => a.year!==b.year ? a.year-b.year : a.quarter<b.quarter?-1:1)

      // Fallback: aggregate monthly fcData → quarters when qData has no forecast rows
      if (!rows.length) {
        const qMap = {}
        fcData
          .filter(d => d.region===region && d.commodity===commodity)
          .forEach(d => {
            const date = new Date(toISODate(d.period))
            const yr   = date.getFullYear()
            if (yr > maxYear) return
            const q    = `Q${Math.floor(date.getMonth()/3)+1}`
            const key  = `${yr}||${q}`
            qMap[key]  = (qMap[key]||0) + (Number(d.forecast)||0)
          })
        rows = Object.entries(qMap)
          .map(([key,value]) => { const [year,quarter]=key.split('||'); return {year:Number(year),quarter,value} })
          .sort((a,b) => a.year!==b.year ? a.year-b.year : a.quarter<b.quarter?-1:1)
      }

      if (selectedRegion) {
        return {
          type:'bar', x:rows.map(d=>`${d.year} ${d.quarter}`), y:rows.map(d=>Number(d.value)||0),
          name:region, marker:{color:`rgba(${r},${g},${b},0.5)`, pattern:{shape:'/', solidity:0.4}},
          hovertemplate:'<b>%{x}</b><br>Forecast: %{y:,.0f}<extra></extra>',
        }
      }
      return {
        x:rows.map(d=>`${d.year} ${d.quarter}`), y:rows.map(d=>Number(d.value)||0),
        name:region, mode:'lines+markers', line:{color,width:2,dash:'dot'}, marker:{size:4,color},
        hovertemplate:`<b>${region}</b> %{x}<br>Forecast: %{y:,.0f}<extra></extra>`,
      }
    })
  }

  // yearly
  return regs.map(region => {
    const color = REGION_COLORS[region]
    const fcMap = {}
    fcData.filter(d=>d.region===region&&d.commodity===commodity).forEach(d=>{
      const yr = new Date(toISODate(d.period)).getFullYear()
      fcMap[yr] = (fcMap[yr]||0)+(Number(d.forecast)||0)
    })
    const qFcMap = {}
    qData.filter(d=>d.region===region&&d.commodity===commodity&&d.is_forecast&&Number(d.year)<=maxYear).forEach(d=>{
      const yr = Number(d.year); qFcMap[yr] = (qFcMap[yr]||0)+(Number(d.value)||0)
    })
    Object.keys(qFcMap).forEach(yr => { const y=Number(yr); if(!fcMap[y]) fcMap[y]=qFcMap[y] })
    const years = Object.keys(fcMap).map(Number).filter(y=>y<=maxYear).sort()
    return {
      x:years, y:years.map(y=>fcMap[y]),
      name:region, mode:'lines+markers',
      line:{color, width:2.5, dash:'dash'}, marker:{size:6,color},
      hovertemplate:`<b>${region}</b> %{x}<br>Forecast: %{y:,.0f}<extra></extra>`,
    }
  })
}

// ── Granularity toggle pill ────────────────────────────────────────────────

function GranularityToggle({ value, onChange }) {
  const opts = [
    { key:'monthly',   label:'Monthly' },
    { key:'quarterly', label:'Quarterly' },
    { key:'yearly',    label:'Yearly' },
  ]
  return (
    <div style={{ display:'flex', gap:2, background:'rgba(255,255,255,0.04)', padding:3, borderRadius:8, border:'1px solid rgba(255,255,255,0.065)', width:'fit-content' }}>
      {opts.map(o=>(
        <button key={o.key} onClick={()=>onChange(o.key)} className={`gran-btn${value===o.key?' active':''}`}>{o.label}</button>
      ))}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

export default function MapTab({ prodData, fcData, scoresData, qData, rigsData, selectedYear, commodity, currentYear, selectedRegion, onRegionSelect, onTabChange }) {
  const [mapStyle,  setMapStyle]  = useState('carto-darkmatter')
  const [prodGran,  setProdGran]  = useState('monthly')
  const [fcGran,    setFcGran]    = useState('monthly')

  const regions = Object.keys(REGION_COORDS)

  const regionStats = useMemo(() => {
    return regions.map(region => {
      const yearProd = prodData.filter(r=>r.region===region&&r.commodity===commodity&&new Date(r.period).getFullYear()===selectedYear)
      let prod = yearProd.reduce((s,r)=>s+(r.value||0),0)
      if (prod===0) {
        const all = prodData.filter(r=>r.region===region&&r.commodity===commodity)
        if (all.length) {
          const years = [...new Set(all.map(r=>new Date(r.period).getFullYear()))].sort()
          prod = all.filter(r=>new Date(r.period).getFullYear()===years[years.length-1]).reduce((s,r)=>s+(r.value||0),0)
        }
      }
      const srow  = scoresData.find(r=>r.region===region)
      const score = srow ? (Number(srow.score)||50) : 50
      const yoy   = srow ? (Number(srow.yoy_growth)||0) : 0
      const rev   = srow ? (Number(srow.revenue_potential)||0) : 0
      const cons  = srow ? (Number(srow.consistency_score)||0) : 0
      const rigRows = rigsData.filter(r=>r.region===region)
      const rigs  = rigRows.length ? Number(rigRows.sort((a,b)=>a.period<b.period?1:-1)[0].rigs||0) : 0
      const g     = grade(score)
      return { region, prod, score, yoy, rev, cons, rigs, grade:g, color:REGION_COLORS[region]||'#6B7280', ...REGION_COORDS[region] }
    })
  }, [prodData, scoresData, rigsData, selectedYear, commodity])

  const sorted   = [...regionStats].sort((a,b)=>b.score-a.score).map((r,i)=>({...r,rank:i+1}))
  const maxProd  = Math.max(...sorted.map(r=>r.prod),1)
  const unit     = commodity==='oil' ? 'Mbbl' : 'MMcf'
  const unitMonth= commodity==='oil' ? 'Mbbl/month' : 'MMcf/month'

  // Map traces
  const traces = useMemo(() => {
    const t = []
    sorted.forEach(row => {
      const poly = REGION_POLYGONS[row.region]; if(!poly) return
      const lats=poly.map(p=>p[0]), lons=poly.map(p=>p[1])
      const isActive=selectedRegion===row.region, isDimmed=selectedRegion&&selectedRegion!==row.region
      const alpha=isDimmed?0.04:isActive?0.45:0.15+(row.score/100)*0.35
      t.push({ type:'scattermapbox',lat:lats,lon:lons,mode:'lines',fill:'toself',
        fillcolor:rgba(row.color,alpha),line:{color:isDimmed?rgba(row.color,0.15):row.color,width:isActive?3.5:2},
        hoverinfo:'skip',showlegend:false })
    })
    sorted.forEach(row => {
      const isActive=selectedRegion===row.region, isDimmed=selectedRegion&&selectedRegion!==row.region
      const baseSize=Math.max(20,(row.prod/maxProd)*75)
      const outer=baseSize*(isActive?1.6:1.0), inner=outer*(isActive?0.65:0.55)
      const hover=`<b>${row.region}</b><br>Rank #${row.rank}<br>Score ${row.score.toFixed(0)}/100<br>Grade ${row.grade}`
      t.push({ type:'scattermapbox',lat:[row.lat],lon:[row.lon],mode:'markers',
        marker:{size:outer,color:row.color,opacity:isDimmed?0.05:isActive?0.45:0.25},hoverinfo:'skip',showlegend:false })
      t.push({ type:'scattermapbox',lat:[row.lat],lon:[row.lon],
        mode:isDimmed?'markers':'markers+text',
        marker:{size:inner,color:row.color,opacity:isDimmed?0.2:0.95},
        text:[row.region],textposition:'top center',
        textfont:{size:isActive?14:12,color:'#FFFFFF',family:'Arial Black'},
        hovertext:isDimmed?'':hover,hoverinfo:isDimmed?'skip':'text',
        name:row.region,showlegend:!isDimmed })
      if (row.rigs>0&&!isDimmed) t.push({
        type:'scattermapbox',lat:[row.lat-1.2],lon:[row.lon+1.2],mode:'markers+text',
        marker:{size:Math.max(15,Math.min(40,row.rigs/6)),color:'#F59E0B',opacity:0.95},
        text:[String(row.rigs)],textposition:'middle center',
        textfont:{size:11,color:'#0F172A',family:'Arial Black'},
        hovertext:`🏗️ ${row.region}: ${row.rigs} rigs`,hoverinfo:'text',showlegend:false })
    })
    return t
  }, [sorted, selectedRegion, maxProd])

  const center = selectedRegion&&REGION_COORDS[selectedRegion] ? {lat:REGION_COORDS[selectedRegion].lat,lon:REGION_COORDS[selectedRegion].lon} : {lat:37.5,lon:-96.0}
  const zoom   = selectedRegion&&REGION_COORDS[selectedRegion] ? REGION_COORDS[selectedRegion].zoom : 3.3

  // Active region data
  const activeRow = selectedRegion ? sorted.find(r=>r.region===selectedRegion) : null

  // Production chart traces
  const prodTraces = useMemo(
    () => buildProdTraces(prodData, qData, commodity, prodGran, selectedRegion, selectedYear),
    [prodData, qData, commodity, prodGran, selectedRegion, selectedYear]
  )
  const prodYLabel = prodGran==='monthly' ? unitMonth : prodGran==='quarterly' ? `${unit}/quarter` : `${unit}/year`
  const prodBarmode = prodGran!=='monthly' ? 'group' : undefined

  // Forecast chart traces
  const fcTraces = useMemo(
    () => buildFcTraces(fcData, qData, commodity, fcGran, selectedRegion, selectedYear),
    [fcData, qData, commodity, fcGran, selectedRegion, selectedYear]
  )
  const fcYLabel = fcGran==='monthly' ? unitMonth : fcGran==='quarterly' ? `${unit}/quarter` : `${unit}/year`
  const fcBarmode = fcGran!=='monthly' ? 'group' : undefined

  // Quarterly summary cards for selected region
  const prodQCards = useMemo(() => {
    if (!selectedRegion || prodGran!=='quarterly') return null
    return qData.filter(r=>r.region===selectedRegion&&r.commodity===commodity&&Number(r.year)===selectedYear&&!r.is_forecast).sort((a,b)=>a.quarter<b.quarter?-1:1)
  }, [selectedRegion, qData, commodity, selectedYear, prodGran])

  const fcQCards = useMemo(() => {
    if (!selectedRegion || fcGran!=='quarterly') return null
    return qData.filter(r=>r.region===selectedRegion&&r.commodity===commodity&&Number(r.year)===selectedYear&&r.is_forecast).sort((a,b)=>a.quarter<b.quarter?-1:1)
  }, [selectedRegion, qData, commodity, selectedYear, fcGran])

  const totalProd = sorted.reduce((s,r)=>s+r.prod,0)
  const totalRev  = sorted.reduce((s,r)=>s+r.rev,0)
  const totalRigs = sorted.reduce((s,r)=>s+r.rigs,0)
  const avgScore  = sorted.length ? sorted.reduce((s,r)=>s+r.score,0)/sorted.length : 0
  const topRegion = sorted[0]

  return (
    <div>
      {/* KPI Banner */}
      <div style={{ display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:'1rem',marginBottom:'1rem',
        background:'rgba(255,255,255,0.028)',
        borderRadius:12,padding:'1rem 1.25rem',
        border:'1px solid rgba(255,255,255,0.065)',
        boxShadow:'0 1px 3px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)' }}>
        {[
          {label:'Total Production', value:`${(totalProd/1e6).toFixed(1)}M`, sub:`${selectedYear} ${commodity.toUpperCase()} ${unit}`, color:'#10B981'},
          {label:'Revenue Potential', value:`$${(totalRev/1000).toFixed(1)}B`, sub:'across 5 basins', color:'#10B981'},
          {label:'Active Rigs', value:totalRigs, sub:'🏗️ drilling now', color:'#F59E0B'},
          {label:'Avg Investment Score', value:`${avgScore.toFixed(0)}/100`, sub:'portfolio avg', color:'#3B82F6'},
          {label:'🏆 Top Basin', value:topRegion?.region||'—', sub:topRegion?`Score ${topRegion.score.toFixed(0)} · Grade ${topRegion.grade}`:'', color:topRegion?.color||'#6B7280'},
        ].map((k,i)=>(
          <div key={i} style={{ borderRight:i<4?'1px solid rgba(255,255,255,0.06)':'none', paddingRight:'1rem' }}>
            <div style={{ fontSize:'0.7rem',color:'#475569',textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:4 }}>{k.label}</div>
            <div style={{ fontSize:'1.4rem',fontWeight:700,color:'#F1F5F9' }}>{k.value}</div>
            <div style={{ fontSize:'0.75rem',color:k.color,marginTop:2 }}>{k.sub}</div>
          </div>
        ))}
      </div>

      {/* Map controls */}
      <div style={{ display:'flex',gap:8,marginBottom:8,alignItems:'center',flexWrap:'wrap' }}>
        <span style={{ fontSize:'0.8rem',color:'#475569' }}>Map style:</span>
        {[['carto-darkmatter','🌑 Dark'],['carto-positron','☀️ Light'],['open-street-map','🗺️ Street']].map(([v,l])=>(
          <button key={v} onClick={()=>setMapStyle(v)} style={{
            padding:'4px 10px',borderRadius:8,fontSize:'0.78rem',
            background:mapStyle===v?'rgba(67,24,255,0.3)':'rgba(255,255,255,0.04)',
            color:mapStyle===v?'#A78BFA':'#64748B',
            border:mapStyle===v?'1px solid rgba(67,24,255,0.5)':'1px solid rgba(255,255,255,0.08)',
            cursor:'pointer',
          }}>{l}</button>
        ))}
        <span style={{ marginLeft:'auto',fontSize:'0.78rem',color:'#475569' }}>
          Hover = Rank · Score · Grade &nbsp;|&nbsp; Click a basin to drill down
        </span>
      </div>

      {/* Map */}
      <Plot data={traces} layout={{
          mapbox:{style:mapStyle,center,zoom},
          height:520,margin:{l:0,r:0,t:0,b:0},
          paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
          showlegend:true,
          legend:{orientation:'v',yanchor:'top',y:0.99,xanchor:'left',x:0.01,
            bgcolor:'rgba(6,11,40,0.92)',bordercolor:'rgba(226,232,240,0.25)',
            borderwidth:1,font:{size:11,color:'#FFFFFF'}},
          uirevision:'map',
        }}
        config={{ displayModeBar:false,responsive:true }}
        style={{ width:'100%',borderRadius:16,overflow:'hidden' }}
        onClick={e=>{
          const pt=e.points?.[0]
          if (pt?.data?.name&&!pt.data.name.startsWith('🏗️')) onRegionSelect(selectedRegion===pt.data.name?null:pt.data.name)
        }}
      />

      {/* Basin buttons */}
      <div style={{ display:'flex',gap:8,marginTop:'0.8rem',flexWrap:'wrap' }}>
        {sorted.map(row=>(
          <button key={row.region} onClick={()=>onRegionSelect(selectedRegion===row.region?null:row.region)} style={{
            padding:'6px 16px',borderRadius:10,fontSize:'0.82rem',fontWeight:600,cursor:'pointer',transition:'all 0.15s',
            background:selectedRegion===row.region?row.color:'rgba(255,255,255,0.04)',
            color:selectedRegion===row.region?'#fff':row.color,
            border:selectedRegion===row.region?`2px solid ${row.color}`:`2px solid ${rgba(row.color,0.35)}`,
            boxShadow:selectedRegion===row.region?`0 0 14px ${rgba(row.color,0.5)}`:'none',
          }}>{selectedRegion===row.region?'●':'○'} {row.region}</button>
        ))}
        {selectedRegion&&(
          <button onClick={()=>onRegionSelect(null)} style={{ padding:'6px 16px',borderRadius:10,fontSize:'0.82rem',fontWeight:500,cursor:'pointer',background:'rgba(255,255,255,0.03)',color:'#475569',border:'2px solid rgba(255,255,255,0.1)' }}>✕ All</button>
        )}
      </div>

      {/* Investment Scorecard */}
      <SectionHeader>📊 Investment Scorecard — All Basins Ranked</SectionHeader>
      <div style={{ display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:'0.8rem',marginBottom:'1.5rem' }}>
        {sorted.map((row,i)=>{
          const medals=['🥇','🥈','🥉','4️⃣','5️⃣']
          const yoyColor=row.yoy>=0?'#01B574':'#E31A1A'
          return (
            <GlassCard key={row.region} style={{ cursor:'pointer' }} onClick={()=>onRegionSelect(selectedRegion===row.region?null:row.region)}>
              <div style={{ fontSize:'0.78rem',color:'#64748B',fontWeight:600,marginBottom:4 }}>{medals[i]} {row.region}</div>
              <div style={{ fontSize:'1.8rem',fontWeight:800,color:'#F1F5F9',lineHeight:1 }}>{row.score.toFixed(0)}<span style={{ fontSize:'0.85rem',color:'#475569' }}>/100</span></div>
              <div style={{ fontSize:'0.72rem',color:'#475569',marginTop:4 }}>Investment Score</div>
              <div style={{ fontSize:'0.78rem',color:yoyColor,marginTop:4,fontWeight:600 }}>{fmtPct(row.yoy)} YoY</div>
              <div style={{ fontSize:'0.72rem',color:'#64748B',marginTop:2 }}>${row.rev.toLocaleString('en',{maximumFractionDigits:0})}M revenue</div>
            </GlassCard>
          )
        })}
      </div>

      {/* ── PRODUCTION chart ──────────────────────────────────────────────── */}
      <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'0.6rem' }}>
        <div style={{ borderLeft:`4px solid ${activeRow?.color||'#10B981'}`,paddingLeft:'0.7rem',fontWeight:700,color:'#E2E8F0',fontSize:'1rem' }}>
          🛢️ {selectedRegion ? `${selectedRegion} —` : 'All Basins —'} Actual Production
        </div>
        <GranularityToggle value={prodGran} onChange={setProdGran} />
      </div>

      <GlassCard style={{ marginBottom:'0.75rem',padding:'0.8rem 1rem' }}>
        {prodTraces.length > 0 ? (
          <Plot
            data={prodTraces}
            layout={{
              height:320,margin:{l:60,r:20,t:20,b:50},
              plot_bgcolor:CHART_BG,paper_bgcolor:CHART_BG,font:{color:FONT_CLR},
              xaxis:{
                gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID,
                title:prodGran==='monthly'?'Month':prodGran==='quarterly'?'Quarter':'Year',
                title_font:{color:AXIS_CLR},
                ...(prodGran==='monthly' ? {type:'date',tickformat:'%b %Y',dtick:'M6',tickangle:-35}
                  : prodGran==='quarterly' ? {tickangle:-35}
                  : {tickformat:'%Y',dtick:1}),
                tickfont:{size:10,color:AXIS_CLR},
              },
              yaxis:{gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID,title:prodYLabel,title_font:{color:AXIS_CLR}},
              legend:{orientation:'h',yanchor:'bottom',y:1.02,xanchor:'left',x:0,font:{color:FONT_CLR},bgcolor:LEGEND_BG},
              barmode:prodBarmode||'group',
            }}
            config={{ displayModeBar:false,responsive:true }}
            style={{ width:'100%' }}
          />
        ) : (
          <div style={{ height:140,display:'flex',alignItems:'center',justifyContent:'center',color:'#334155' }}>No production data</div>
        )}
      </GlassCard>

      {/* Quarterly actual cards */}
      {selectedRegion && prodGran==='quarterly' && prodQCards && prodQCards.length>0 && (
        <div style={{ display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:'0.7rem',marginBottom:'0.75rem' }}>
          {['Q1','Q2','Q3','Q4'].map(q=>{
            const qrow=prodQCards.find(r=>r.quarter===q)
            if (!qrow) return <div key={q} style={{ background:'rgba(255,255,255,0.02)',border:'1px dashed rgba(255,255,255,0.08)',borderRadius:10,padding:'1rem',textAlign:'center' }}><div style={{ color:'#475569',fontSize:'0.8rem' }}>{q}</div><div style={{ color:'rgba(255,255,255,0.1)',fontSize:'1.5rem',marginTop:16 }}>—</div></div>
            const val=Number(qrow.value||0), qoq=qrow.qoq_growth!=null?Number(qrow.qoq_growth):null
            return (
              <div key={q} style={{ background:`linear-gradient(135deg,${rgba(activeRow.color,0.12)} 0%,${rgba(activeRow.color,0.04)} 100%)`,border:`1px solid ${rgba(activeRow.color,0.25)}`,borderRadius:10,padding:'0.9rem' }}>
                <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center' }}>
                  <div style={{ color:activeRow.color,fontWeight:700 }}>{q}</div>
                  <div style={{ background:'rgba(0,117,255,0.12)',color:'#63B3ED',fontSize:'0.65rem',padding:'1px 6px',borderRadius:4,fontWeight:600 }}>📊 Actual</div>
                </div>
                <div style={{ color:'#F1F5F9',fontSize:'1.4rem',fontWeight:700,marginTop:4 }}>{(val/1000).toFixed(1)}<span style={{ fontSize:'0.72rem',color:'#475569' }}>K {unit}</span></div>
                {qoq!=null&&<div style={{ fontSize:'0.78rem',marginTop:4,color:qoq>=0?'#01B574':'#E31A1A',fontWeight:600 }}>{qoq>=0?'+':''}{qoq.toFixed(1)}% QoQ</div>}
              </div>
            )
          })}
        </div>
      )}

      {/* ── FORECAST chart ────────────────────────────────────────────────── */}
      <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'0.6rem',marginTop:'0.5rem' }}>
        <div style={{ borderLeft:'4px solid #7551FF',paddingLeft:'0.7rem',fontWeight:700,color:'#E2E8F0',fontSize:'1rem' }}>
          📈 {selectedRegion ? `${selectedRegion} —` : 'All Basins —'} SARIMA Forecast
        </div>
        <GranularityToggle value={fcGran} onChange={setFcGran} />
      </div>

      <GlassCard style={{ marginBottom:'0.75rem',padding:'0.8rem 1rem' }}>
        {fcTraces.length > 0 ? (
          <Plot
            data={fcTraces}
            layout={{
              height:320,margin:{l:60,r:20,t:20,b:50},
              plot_bgcolor:CHART_BG,paper_bgcolor:CHART_BG,font:{color:FONT_CLR},
              xaxis:{
                gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID,
                title:fcGran==='monthly'?'Month':fcGran==='quarterly'?'Quarter':'Year',
                title_font:{color:AXIS_CLR},
                ...(fcGran==='monthly' ? {type:'date',tickformat:'%b %Y',dtick:'M6',tickangle:-35}
                  : fcGran==='quarterly' ? {tickangle:-35}
                  : {tickformat:'%Y',dtick:1}),
                tickfont:{size:10,color:AXIS_CLR},
              },
              yaxis:{gridcolor:GRID,color:AXIS_CLR,zerolinecolor:GRID,title:fcYLabel,title_font:{color:AXIS_CLR}},
              legend:{orientation:'h',yanchor:'bottom',y:1.02,xanchor:'left',x:0,font:{color:FONT_CLR},bgcolor:LEGEND_BG},
              barmode:fcBarmode||'group',
            }}
            config={{ displayModeBar:false,responsive:true }}
            style={{ width:'100%' }}
          />
        ) : (
          <div style={{ height:140,display:'flex',alignItems:'center',justifyContent:'center',color:'#334155' }}>No forecast data</div>
        )}
      </GlassCard>

      {/* Quarterly forecast cards */}
      {selectedRegion && fcGran==='quarterly' && fcQCards && fcQCards.length>0 && (
        <div style={{ display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:'0.7rem',marginBottom:'0.75rem' }}>
          {['Q1','Q2','Q3','Q4'].map(q=>{
            const qrow=fcQCards.find(r=>r.quarter===q)
            if (!qrow) return <div key={q} style={{ background:'rgba(255,255,255,0.02)',border:'1px dashed rgba(255,255,255,0.08)',borderRadius:10,padding:'1rem',textAlign:'center' }}><div style={{ color:'#475569',fontSize:'0.8rem' }}>{q}</div><div style={{ color:'rgba(255,255,255,0.1)',fontSize:'1.5rem',marginTop:16 }}>—</div></div>
            const val=Number(qrow.value||0), qoq=qrow.qoq_growth!=null?Number(qrow.qoq_growth):null
            return (
              <div key={q} style={{ background:'linear-gradient(135deg,rgba(117,81,255,0.12) 0%,rgba(117,81,255,0.04) 100%)',border:'1px solid rgba(117,81,255,0.25)',borderRadius:10,padding:'0.9rem' }}>
                <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center' }}>
                  <div style={{ color:'#A78BFA',fontWeight:700 }}>{q}</div>
                  <div style={{ background:'rgba(67,24,255,0.15)',color:'#A78BFA',fontSize:'0.65rem',padding:'1px 6px',borderRadius:4,fontWeight:600 }}>🔮 Forecast</div>
                </div>
                <div style={{ color:'#F1F5F9',fontSize:'1.4rem',fontWeight:700,marginTop:4 }}>{(val/1000).toFixed(1)}<span style={{ fontSize:'0.72rem',color:'#475569' }}>K {unit}</span></div>
                {qoq!=null&&<div style={{ fontSize:'0.78rem',marginTop:4,color:qoq>=0?'#01B574':'#E31A1A',fontWeight:600 }}>{qoq>=0?'+':''}{qoq.toFixed(1)}% QoQ</div>}
              </div>
            )
          })}
        </div>
      )}

      {/* Region Drill-down detail (when region selected) */}
      {activeRow && (
        <GlassCard style={{ marginBottom:'1rem' }}>
          <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'0.8rem' }}>
            <div>
              <span style={{ fontSize:'1.2rem',fontWeight:700,color:activeRow.color }}>📍 {activeRow.region}</span>
              <span style={{ fontSize:'0.85rem',color:'#475569',marginLeft:8 }}>({activeRow.state})</span>
            </div>
            <div style={{ display:'flex',gap:8,alignItems:'center' }}>
              <span style={{ background:gradeColor(activeRow.grade),color:'white',padding:'3px 10px',borderRadius:12,fontWeight:700,fontSize:'0.85rem' }}>Grade {activeRow.grade}</span>
              <span style={{ color:'#475569',fontSize:'0.85rem' }}>Rank #{activeRow.rank}</span>
            </div>
          </div>
          <div style={{ display:'grid',gridTemplateColumns:'repeat(6,1fr)',gap:'1rem' }}>
            {[
              ['Production',`${(activeRow.prod/1000).toFixed(1)}K ${unit}`],
              ['Revenue',`$${activeRow.rev.toLocaleString('en',{maximumFractionDigits:0})}M`],
              ['Score',`${activeRow.score.toFixed(0)}/100`],
              ['YoY Growth',fmtPct(activeRow.yoy), activeRow.yoy>=0?'#10B981':'#F43F5E'],
              ['Active Rigs',`🏗️ ${activeRow.rigs}`],
              ['Consistency',`${activeRow.cons.toFixed(0)}/100`],
            ].map(([l,v,c])=>(
              <div key={l}>
                <div style={{ fontSize:'0.7rem',color:'#475569',textTransform:'uppercase',letterSpacing:'0.05em' }}>{l}</div>
                <div style={{ fontSize:'1.05rem',fontWeight:700,color:c||'#F1F5F9',marginTop:2 }}>{v}</div>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      {/* Well Economics CTA */}
      {activeRow && (
        <div style={{ background:'linear-gradient(127.09deg,rgba(6,11,40,0.94) 19.41%,rgba(10,14,35,0.49) 76.65%)',border:'1px solid rgba(67,24,255,0.3)',borderRadius:16,padding:'1rem 1.4rem',display:'flex',justifyContent:'space-between',alignItems:'center' }}>
          <div>
            <div style={{ color:'#F1F5F9',fontWeight:700 }}>💰 Model a single well in {activeRow.region}</div>
            <div style={{ color:'#64748B',fontSize:'0.8rem',marginTop:2 }}>Region defaults pre-filled in Well Economics tab</div>
          </div>
          <button onClick={()=>onTabChange('well')} style={{ background:'rgba(67,24,255,0.25)',color:'#A78BFA',border:'1px solid rgba(67,24,255,0.5)',borderRadius:10,padding:'6px 14px',cursor:'pointer',fontSize:'0.82rem',fontWeight:600 }}>
            Open 💰 Well Economics →
          </button>
        </div>
      )}
    </div>
  )
}

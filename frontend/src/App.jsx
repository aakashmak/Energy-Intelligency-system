import React, { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchProduction, fetchForecasts, fetchScores, fetchQuarterly, fetchRigs, fetchValidation } from './api/client'

import MapTab         from './components/tabs/MapTab'
import ScoresTab      from './components/tabs/ScoresTab'
import RigsTab        from './components/tabs/RigsTab'
import ValidationTab  from './components/tabs/ValidationTab'
import ColoradoTab    from './components/tabs/ColoradoTab'
import WellEconTab    from './components/tabs/WellEconTab'
import SensitivityTab from './components/tabs/SensitivityTab'
import ChatBot        from './components/ChatBot'

/* SVG icon set — minimalist */
const Icons = {
  map:      <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M1 3.5L5 2l6 2 4-1.5v10L11 14 5 12 1 13.5V3.5z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round"/><path d="M5 2v10M11 4v10" stroke="currentColor" strokeWidth="1.25"/></svg>,
  scores:   <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><rect x="1" y="9" width="3" height="6" rx="1" fill="currentColor" opacity=".6"/><rect x="6" y="5" width="3" height="10" rx="1" fill="currentColor" opacity=".8"/><rect x="11" y="1" width="4" height="14" rx="1" fill="currentColor"/></svg>,
  rigs:     <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 1v14M4 3l4 2 4-2M3 8h10M5 13h6" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round"/></svg>,
  accuracy: <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.25"/><circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.25"/><circle cx="8" cy="8" r="1" fill="currentColor"/></svg>,
  colorado: <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M1 11l4-5 3 3 3-5 4 7" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  well:     <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M3 13V6a5 5 0 0 1 10 0v7" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round"/><path d="M1 13h14" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round"/><path d="M8 6v5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  sens:     <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><rect x="1" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.25"/><rect x="9" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.25"/><rect x="1" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.25"/><rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.25"/></svg>,
  refresh:  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><path d="M1.5 8A6.5 6.5 0 1 0 4 3.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><path d="M1.5 3.5v3.5H5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>,
}

const TABS = [
  { id: 'map',      icon: Icons.map,      label: 'Basin Map' },
  { id: 'scores',   icon: Icons.scores,   label: 'Scores' },
  { id: 'rigs',     icon: Icons.rigs,     label: 'Rigs' },
  { id: 'accuracy', icon: Icons.accuracy, label: 'Accuracy' },
  { id: 'colorado', icon: Icons.colorado, label: 'Colorado' },
  { id: 'well',     icon: Icons.well,     label: 'Well Econ' },
  { id: 'sens',     icon: Icons.sens,     label: 'Sensitivity' },
]

const REGIONS = ['Permian', 'Bakken', 'Eagle Ford', 'Appalachia', 'Gulf Coast']
const REGION_COLORS = {
  Permian: '#3B82F6', Bakken: '#10B981', 'Eagle Ford': '#F59E0B',
  Appalachia: '#A855F7', 'Gulf Coast': '#EF4444',
}
const CURRENT_YEAR = new Date().getFullYear()

export default function App() {
  const [activeTab,      setActiveTab]      = useState('map')
  const [selectedYear,   setSelectedYear]   = useState(CURRENT_YEAR)
  const [commodity,      setCommodity]      = useState('oil')
  const [selectedRegion, setSelectedRegion] = useState(null)
  const [wtiPrice,       setWtiPrice]       = useState(72)
  const [hhPrice,        setHhPrice]        = useState(2.5)
  const [sidebarOpen,    setSidebarOpen]    = useState(true)

  const { data: prodData   = [], isLoading: loadProd,   isFetching: pFetching,  refetch: refProd   } = useQuery({ queryKey: ['production'],  queryFn: () => fetchProduction() })
  const { data: fcData     = [], isLoading: loadFc,     isFetching: fcFetching, refetch: refFc     } = useQuery({ queryKey: ['forecasts'],   queryFn: () => fetchForecasts() })
  const { data: scoresData = [], isLoading: loadScores, isFetching: sFetching,  refetch: refScores } = useQuery({ queryKey: ['scores'],      queryFn: fetchScores })
  const { data: qData      = [], isLoading: loadQ,      isFetching: qFetching,  refetch: refQ      } = useQuery({ queryKey: ['quarterly'],   queryFn: () => fetchQuarterly() })
  const { data: rigsData   = [], isLoading: loadRigs,   isFetching: rFetching,  refetch: refRigs   } = useQuery({ queryKey: ['rigs'],        queryFn: () => fetchRigs() })
  const { data: valData    = [], isLoading: loadVal,    isFetching: vFetching,  refetch: refVal    } = useQuery({ queryKey: ['validation'],  queryFn: fetchValidation })

  const isLoading  = loadProd  || loadFc     || loadScores || loadQ    || loadRigs
  const isFetching = pFetching || fcFetching || sFetching  || qFetching || rFetching || vFetching

  const refreshAll = useCallback(() => {
    refProd(); refFc(); refScores(); refQ(); refRigs(); refVal()
  }, [refProd, refFc, refScores, refQ, refRigs, refVal])

  const handleRegionSelect = useCallback((region) => {
    setSelectedRegion(region)
    setActiveTab('map')
  }, [])

  const sharedProps = {
    prodData, fcData, scoresData, qData, rigsData, valData,
    selectedYear, commodity, selectedRegion, wtiPrice, hhPrice,
    currentYear: CURRENT_YEAR,
    onRegionSelect: handleRegionSelect,
    onTabChange: setActiveTab,
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', fontFamily: "'Inter', -apple-system, 'SF Pro Display', system-ui, sans-serif" }}>

      {/* ── Sidebar ─────────────────────────────────────────────── */}
      <aside style={{
        width: sidebarOpen ? 220 : 50,
        flexShrink: 0,
        background: 'rgba(4,4,7,0.96)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        backdropFilter: 'blur(40px)',
        WebkitBackdropFilter: 'blur(40px)',
        transition: 'width 0.2s cubic-bezier(0.4,0,0.2,1)',
        display: 'flex', flexDirection: 'column',
        overflowY: 'auto', overflowX: 'hidden',
        zIndex: 20,
      }}>

        {/* Logo */}
        <div style={{
          height: 50, display: 'flex', alignItems: 'center',
          padding: sidebarOpen ? '0 10px 0 14px' : '0 8px',
          gap: 9, borderBottom: '1px solid rgba(255,255,255,0.05)', flexShrink: 0,
        }}>
          <div style={{
            width: 28, height: 28, borderRadius: 8, flexShrink: 0,
            background: 'linear-gradient(135deg,#6366F1,#06B6D4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 16px rgba(99,102,241,0.5)',
            fontSize: '0.85rem',
          }}>⚡</div>
          {sidebarOpen && (
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontWeight: 800, fontSize: '0.95rem', letterSpacing: '-0.03em',
                background: 'linear-gradient(95deg,#A5B4FC 0%,#67E8F9 100%)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
                lineHeight: 1,
              }}>OilPulse</div>
              <div style={{ fontSize: '0.55rem', color: '#4B5563', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', marginTop: 2 }}>Energy Intelligence</div>
            </div>
          )}
          <button onClick={() => setSidebarOpen(o => !o)} style={{
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
            color: '#374151', cursor: 'pointer', width: 20, height: 20, borderRadius: 4,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '0.55rem', flexShrink: 0, transition: 'all 0.15s',
          }}>{sidebarOpen ? '◀' : '▶'}</button>
        </div>

        {sidebarOpen && (
          <div style={{ padding: '0.75rem 0.65rem', display: 'flex', flexDirection: 'column', gap: 0, flex: 1 }}>

            {/* Year */}
            <div style={{ padding: '0 4px', marginBottom: '0.9rem' }}>
              <div className="stat-label" style={{ marginBottom: 7 }}>Forecast Year</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                <input type="range" min={2015} max={2029} value={selectedYear}
                  onChange={e => setSelectedYear(Number(e.target.value))} style={{ flex: 1 }} />
                <div style={{
                  minWidth: 36, textAlign: 'center', fontSize: '0.78rem', fontWeight: 800,
                  color: '#A5B4FC', background: 'rgba(99,102,241,0.12)',
                  border: '1px solid rgba(99,102,241,0.22)', borderRadius: 5, padding: '2px 5px',
                  letterSpacing: '-0.02em',
                }}>{selectedYear}</div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.56rem', color: '#4B5563', marginTop: 3 }}>
                <span>2015</span><span>2029</span>
              </div>
            </div>

            <div className="sep" />

            {/* Commodity */}
            <div style={{ padding: '0 4px', marginBottom: '0.9rem', marginTop: '0.65rem' }}>
              <div className="stat-label" style={{ marginBottom: 7 }}>Commodity</div>
              <div style={{ display: 'flex', gap: 4 }}>
                {[['oil','🛢 Oil'],['gas','🔥 Gas']].map(([c, lbl]) => {
                  const on = commodity === c
                  return (
                    <button key={c} className="comm-btn" onClick={() => setCommodity(c)} style={{
                      flex: 1, padding: '6px 4px', borderRadius: 7, fontSize: '0.75rem', fontWeight: 700,
                      cursor: 'pointer',
                      background: on ? 'rgba(99,102,241,0.18)' : 'rgba(255,255,255,0.03)',
                      color: on ? '#A5B4FC' : '#374151',
                      border: on ? '1px solid rgba(99,102,241,0.4)' : '1px solid rgba(255,255,255,0.07)',
                      boxShadow: on ? '0 0 10px rgba(99,102,241,0.2)' : 'none',
                    }}>{lbl}</button>
                  )
                })}
              </div>
            </div>

            <div className="sep" />

            {/* Basin */}
            <div style={{ padding: '0 0', marginBottom: '0.9rem', marginTop: '0.65rem' }}>
              <div className="stat-label" style={{ marginBottom: 7, padding: '0 4px' }}>Basin</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {[null, ...REGIONS].map(r => {
                  const on = selectedRegion === r
                  const col = r ? REGION_COLORS[r] : '#6366F1'
                  return (
                    <button key={r ?? 'all'} className="region-btn" onClick={() => setSelectedRegion(r)} style={{
                      padding: '6px 10px', borderRadius: 7, fontSize: '0.76rem', fontWeight: on ? 600 : 400,
                      cursor: 'pointer', textAlign: 'left', display: 'flex', alignItems: 'center', gap: 8,
                      background: on ? `${col}12` : 'transparent',
                      color: on ? '#E5E7EB' : '#4B5563',
                      border: on ? `1px solid ${col}30` : '1px solid transparent',
                      borderLeft: on ? `2px solid ${col}` : '2px solid transparent',
                    }}>
                      <span style={{
                        width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
                        background: on ? col : '#374151',
                        boxShadow: on ? `0 0 6px ${col}` : 'none',
                        transition: 'all 0.15s',
                      }} />
                      {r || 'All Basins'}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="sep" />

            {/* Prices */}
            <div style={{ padding: '0 4px', marginBottom: '0.9rem', marginTop: '0.65rem' }}>
              <div className="stat-label" style={{ marginBottom: 7 }}>Price Assumptions</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                {[
                  ['WTI', wtiPrice, v => setWtiPrice(v), 20, 200, 1, '$/bbl'],
                  ['Henry Hub', hhPrice, v => setHhPrice(v), 1, 20, 0.1, '$/MMcf'],
                ].map(([lbl, val, fn, min, max, step, unit]) => (
                  <div key={lbl}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: '0.65rem', color: '#374151' }}>{lbl}</span>
                      <span style={{ fontSize: '0.65rem', color: '#6B7280', fontWeight: 700 }}>${val} {unit}</span>
                    </div>
                    <input type="number" value={val} min={min} max={max} step={step}
                      onChange={e => fn(Number(e.target.value))} />
                  </div>
                ))}
              </div>
            </div>

            <div className="sep" />

            {/* Refresh */}
            <div style={{ padding: '0 4px', marginTop: '0.65rem', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <button onClick={refreshAll} disabled={isFetching} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                padding: '8px 0', borderRadius: 8, fontSize: '0.76rem', fontWeight: 700,
                cursor: isFetching ? 'not-allowed' : 'pointer',
                background: isFetching ? 'rgba(255,255,255,0.03)' : 'rgba(99,102,241,0.14)',
                color: isFetching ? '#4B5563' : '#A5B4FC',
                border: `1px solid ${isFetching ? 'rgba(255,255,255,0.06)' : 'rgba(99,102,241,0.3)'}`,
                transition: 'all 0.15s',
                boxShadow: isFetching ? 'none' : '0 0 12px rgba(99,102,241,0.15)',
              }}>
                <span style={{
                  display: 'inline-flex',
                  animation: isFetching ? 'spin 0.8s linear infinite' : 'none',
                }}>{Icons.refresh}</span>
                {isFetching ? 'Refreshing…' : 'Refresh Data'}
              </button>

              {/* Live status */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {[
                  [prodData.length, 'Production', '#10B981'],
                  [fcData.length,   'Forecasts',  '#6366F1'],
                  [rigsData.length, 'Rigs',       '#F59E0B'],
                ].map(([n, lbl, col]) => (
                  <div key={lbl} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.62rem', color: '#4B5563' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      <span className={n ? 'live-dot' : ''} style={{ width: 4, height: 4, borderRadius: '50%', background: n ? col : '#374151', flexShrink: 0 }} />
                      {lbl}
                    </div>
                    <span style={{ color: n ? '#9CA3AF' : '#4B5563', fontVariantNumeric: 'tabular-nums' }}>{n.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Collapsed state — just icons */}
        {!sidebarOpen && (
          <div style={{ padding: '0.5rem 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, marginTop: 4 }}>
            {[
              [null,   '🌍'],
              [72,     '🛢'],
              [2.5,    '🔥'],
            ].map(([, ico], i) => (
              <div key={i} style={{ width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.9rem', color: '#374151' }}>{ico}</div>
            ))}
          </div>
        )}
      </aside>

      {/* ── Main ────────────────────────────────────────────────── */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflowX: 'hidden' }}>

        {/* Header */}
        <header style={{
          height: 50, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 1.4rem', gap: 12,
          background: 'rgba(4,4,7,0.9)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          position: 'sticky', top: 0, zIndex: 10,
        }}>
          {/* Tab context — active tab name + live badge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <span style={{ opacity: 0.7, display: 'flex', alignItems: 'center' }}>
                {TABS.find(t => t.id === activeTab)?.icon}
              </span>
              <h1 style={{
                margin: 0, fontSize: '0.9rem', fontWeight: 700, letterSpacing: '-0.02em',
                color: '#E5E7EB', whiteSpace: 'nowrap',
              }}>{TABS.find(t => t.id === activeTab)?.label}</h1>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 20, background: 'rgba(16,185,129,0.07)', border: '1px solid rgba(16,185,129,0.15)' }}>
              <span className="live-dot" style={{ width: 5, height: 5, borderRadius: '50%', background: '#10B981', display: 'inline-block' }} />
              <span style={{ fontSize: '0.58rem', color: '#10B981', fontWeight: 800, letterSpacing: '0.1em' }}>LIVE</span>
            </div>
          </div>

          {/* Right chips */}
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
            {selectedRegion && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '3px 10px', borderRadius: 20,
                background: `${REGION_COLORS[selectedRegion]}12`,
                color: REGION_COLORS[selectedRegion],
                border: `1px solid ${REGION_COLORS[selectedRegion]}30`,
                fontSize: '0.72rem', fontWeight: 700,
              }}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: REGION_COLORS[selectedRegion], boxShadow: `0 0 5px ${REGION_COLORS[selectedRegion]}` }} />
                {selectedRegion}
                <button onClick={() => setSelectedRegion(null)} style={{ background: 'none', border: 'none', color: '#374151', cursor: 'pointer', padding: 0, lineHeight: 1, fontSize: '0.65rem' }}>✕</button>
              </div>
            )}
            <div style={{
              padding: '3px 9px', borderRadius: 6,
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
              fontSize: '0.68rem', color: '#6B7280', fontWeight: 700, letterSpacing: '0.06em',
              fontVariantNumeric: 'tabular-nums',
            }}>
              {selectedYear} · {commodity.toUpperCase()}
            </div>
          </div>
        </header>

        {/* Tab nav — underline style */}
        <nav style={{
          height: 42, flexShrink: 0,
          display: 'flex', alignItems: 'stretch',
          padding: '0 1rem', gap: 0,
          background: 'rgba(4,4,7,0.75)',
          backdropFilter: 'blur(16px)',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          overflowX: 'auto',
        }}>
          {TABS.map(t => {
            const active = activeTab === t.id
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`tab-link${active ? ' active' : ''}`}
              >
                <span className="sb-icon" style={{ opacity: active ? 1 : 0.5, display: 'flex', alignItems: 'center' }}>{t.icon}</span>
                {t.label}
              </button>
            )
          })}
        </nav>

        {/* Content */}
        <div key={activeTab} className="anim-fade-up" style={{ flex: 1, overflowY: 'auto', padding: '1.2rem 1.4rem' }}>
          {activeTab === 'map'      && <MapTab         {...sharedProps} />}
          {activeTab === 'scores'   && <ScoresTab      {...sharedProps} />}
          {activeTab === 'rigs'     && <RigsTab        {...sharedProps} />}
          {activeTab === 'accuracy' && <ValidationTab  {...sharedProps} />}
          {activeTab === 'colorado' && <ColoradoTab    {...sharedProps} />}
          {activeTab === 'well'     && <WellEconTab    {...sharedProps} />}
          {activeTab === 'sens'     && <SensitivityTab {...sharedProps} />}
        </div>

        {/* Footer */}
        <footer style={{
          height: 32, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 1.4rem', gap: 8,
          borderTop: '1px solid rgba(255,255,255,0.04)',
          background: 'rgba(4,4,7,0.8)',
        }}>
          <span style={{ fontSize: '0.6rem', color: '#374151', letterSpacing: '0.03em' }}>
            OilPulse · CDF Energy AI Hackathon · EIA APIv2 + STEO + COGCC
          </span>
          <span style={{ fontSize: '0.6rem', color: '#374151', letterSpacing: '0.03em' }}>
            SARIMA(1,1,1)(1,1,0)[12] · Supabase · Groq LLaMA-3.3-70B
          </span>
        </footer>
      </main>

      <ChatBot scoresData={scoresData} selectedYear={selectedYear} commodity={commodity} wtiPrice={wtiPrice} hhPrice={hhPrice} />
    </div>
  )
}

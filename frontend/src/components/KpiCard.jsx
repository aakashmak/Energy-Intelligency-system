import Sparkline from './Sparkline'

export default function KpiCard({ label, value, sub, delta, deltaPositive, color = '#6366F1', sparkData, style = {} }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.028)',
      border: '1px solid rgba(255,255,255,0.065)',
      borderRadius: 12,
      padding: '0.85rem 1rem',
      position: 'relative',
      overflow: 'hidden',
      boxShadow: '0 1px 3px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)',
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      display: 'flex', flexDirection: 'column', gap: 0,
      ...style,
    }}>
      {/* Top color bar */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '1px', background: `linear-gradient(90deg, ${color}90, transparent 70%)` }} />

      {/* Label */}
      <div style={{ fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#6B7280', marginBottom: 8 }}>
        {label}
      </div>

      {/* Value row */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 8 }}>
        <div className="mono" style={{ fontSize: '1.55rem', fontWeight: 800, color: '#F9FAFB', lineHeight: 1, letterSpacing: '-0.03em' }}>
          {value}
        </div>
        {sparkData && sparkData.length > 1 && (
          <Sparkline data={sparkData} width={72} height={28} color={color} />
        )}
      </div>

      {/* Sub + delta */}
      {(sub || delta != null) && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 7 }}>
          {sub && <div style={{ fontSize: '0.68rem', color: '#6B7280', lineHeight: 1.3 }}>{sub}</div>}
          {delta != null && (
            <div style={{
              fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.02em',
              color: deltaPositive ? '#10B981' : '#EF4444',
              display: 'flex', alignItems: 'center', gap: 2,
            }}>
              {deltaPositive ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}%
            </div>
          )}
        </div>
      )}
    </div>
  )
}

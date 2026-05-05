export default function SectionHeader({ children, accent = '#6366F1' }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      margin: '1.5rem 0 0.85rem',
    }}>
      <div style={{
        width: 2, height: 14, borderRadius: 1,
        background: accent,
        boxShadow: `0 0 6px ${accent}`,
        flexShrink: 0,
      }} />
      <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#D1D5DB', letterSpacing: '-0.01em' }}>
        {children}
      </span>
      <div style={{ flex: 1, height: '1px', background: 'linear-gradient(90deg, rgba(255,255,255,0.07), transparent)' }} />
    </div>
  )
}

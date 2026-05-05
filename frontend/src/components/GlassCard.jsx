export default function GlassCard({ children, style = {}, className = '', hover = false }) {
  return (
    <div
      className={`glass-card${hover ? ' glass-card-hover' : ''}${className ? ` ${className}` : ''}`}
      style={{
        background: 'rgba(255,255,255,0.028)',
        border: '1px solid rgba(255,255,255,0.065)',
        borderRadius: 12,
        padding: '1rem 1.2rem',
        boxShadow: '0 1px 3px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        ...style,
      }}
    >
      {children}
    </div>
  )
}

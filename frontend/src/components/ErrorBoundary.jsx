import React from 'react'
import { IconAlertTriangle, IconRefreshCw } from './Icons'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    this.setState({ error, info })
    // Send error report to diagnostic service if available in development
    fetch('http://localhost:5001/__error', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: error?.message || 'Unknown error',
        stack: error?.stack,
        componentStack: info?.componentStack
      })
    }).catch(() => {})
  }

  handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem',
          background: 'radial-gradient(circle at top right, rgba(239, 68, 68, 0.05), transparent 70%), var(--bg-primary, #ffffff)',
          color: 'var(--text-primary, #09090b)',
          fontFamily: "'Inter', sans-serif"
        }}>
          <div style={{
            maxWidth: '480px',
            width: '100%',
            background: 'var(--bg-card, #ffffff)',
            border: '1px solid var(--border-secondary, #e4e4e7)',
            borderRadius: '1.5rem',
            padding: '2.5rem',
            textAlign: 'center',
            boxShadow: '0 20px 50px -12px rgba(0, 0, 0, 0.08)'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.75rem',
              marginBottom: '1.75rem'
            }}>
              <img src="/logo.png" alt="PolicyCrab Logo" style={{ width: '40px', height: '40px' }} />
              <span style={{ fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.025em' }}>PolicyCrab</span>
            </div>

            <div style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: '#fef2f2',
              color: '#dc2626',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1.25rem',
              border: '1px solid #fecaca'
            }}>
              <IconAlertTriangle size={28} />
            </div>

            <h1 style={{
              fontSize: '1.375rem',
              fontWeight: 800,
              color: 'var(--text-primary, #09090b)',
              marginBottom: '0.75rem'
            }}>
              Our servers are currently loading
            </h1>

            <p style={{
              fontSize: '0.9375rem',
              color: 'var(--text-secondary, #52525b)',
              lineHeight: '1.6',
              marginBottom: '2rem'
            }}>
              Please bear with us! We encountered an unexpected hiccup while preparing your session or experiencing high traffic. 
              <strong> The problem is definitely not with you or your document, but with us.</strong>
            </p>

            <button
              onClick={this.handleReload}
              className="btn btn-red"
              style={{
                width: '100%',
                padding: '0.875rem',
                fontSize: '0.9375rem',
                fontWeight: 700,
                borderRadius: '0.75rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                cursor: 'pointer',
                background: '#dc2626',
                color: '#ffffff',
                border: 'none',
                boxShadow: '0 4px 12px rgba(220, 38, 38, 0.25)'
              }}
            >
              Reload Application
            </button>

            <p style={{
              fontSize: '0.75rem',
              color: 'var(--text-tertiary, #a1a1aa)',
              marginTop: '1.5rem',
              marginBottom: 0
            }}>
              If the problem persists, our automated health check team is already on it. Thank you for your patience!
            </p>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

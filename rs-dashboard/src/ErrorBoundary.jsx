import { Component } from 'react';

export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('Dashboard error:', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            minHeight: '100vh',
            padding: '2rem',
            background: '#0f172a',
            color: '#f8fafc',
            fontFamily: 'system-ui, sans-serif',
          }}
        >
          <h1 style={{ fontSize: '1.25rem', marginBottom: '1rem' }}>შეცდომა — გვერდი ვერ ჩაიტვირთა</h1>
          <pre
            style={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontSize: '0.85rem',
              color: '#fca5a5',
              background: 'rgba(0,0,0,0.35)',
              padding: '1rem',
              borderRadius: 8,
            }}
          >
            {this.state.error?.message || String(this.state.error)}
          </pre>
          <p style={{ marginTop: '1rem', color: '#94a3b8', fontSize: '0.9rem' }}>
            გადატვირთე გვერდი (Ctrl+F5). თუ Simple Browser-შია — გახსენი ჩვეულებრივ ბრაუზერში:{' '}
            <code style={{ color: '#a5b4fc' }}>http://127.0.0.1:5173</code>
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

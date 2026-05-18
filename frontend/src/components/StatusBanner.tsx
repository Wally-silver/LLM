export function StatusBanner({ tone, text }: { tone: 'success' | 'error' | 'info'; text: string }) {
  return <div className={`status-banner ${tone}`}>{text}</div>
}

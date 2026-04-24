import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ResultsList from '../components/ResultsList'

const MOCK_RESULT = {
  memory_id: 'mem-001',
  url: 'https://example.com',
  title: 'Test Page',
  snippet: 'Some content here.',
  semantic_similarity: 0.9,
  visited_at: new Date().toISOString(),
  visit_count: 1,
  dwell_time: 60,
  blockchain_anchored: false,
}

describe('ResultsList', () => {
  it('shows empty state when not yet searched', () => {
    render(<ResultsList results={[]} loading={false} searched={false} query="" />)
    expect(screen.getByText(/search your memories/i)).toBeInTheDocument()
  })

  it('shows skeleton cards while loading', () => {
    render(<ResultsList results={[]} loading={true} searched={false} query="" />)
    // Skeletons render as divs with the skeleton class — the count header is absent
    expect(screen.queryByText(/results/i)).not.toBeInTheDocument()
  })

  it('shows no-results state after search returns empty', () => {
    render(<ResultsList results={[]} loading={false} searched={true} query="neural nets" />)
    expect(screen.getByText(/no results for/i)).toBeInTheDocument()
    expect(screen.getByText(/"neural nets"/i)).toBeInTheDocument()
  })

  it('renders correct result count', () => {
    render(
      <ResultsList results={[MOCK_RESULT]} loading={false} searched={true} query="test" />,
    )
    // The count header reads "1 results for …" — use the paragraph that wraps it
    const header = screen.getByText(/results/i, { selector: 'p' })
    expect(header).toBeInTheDocument()
    expect(header.textContent).toMatch(/^1/)
  })

  it('renders a MemoryCard for each result', () => {
    const results = [
      { ...MOCK_RESULT, memory_id: 'a', title: 'Alpha' },
      { ...MOCK_RESULT, memory_id: 'b', title: 'Beta' },
    ]
    render(<ResultsList results={results} loading={false} searched={true} query="q" />)
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
  })

  it('shows query text in result header', () => {
    render(
      <ResultsList results={[MOCK_RESULT]} loading={false} searched={true} query="machine learning" />,
    )
    expect(screen.getByText(/"machine learning"/i)).toBeInTheDocument()
  })

  it('shows re-ranked by XGBoost label', () => {
    render(
      <ResultsList results={[MOCK_RESULT]} loading={false} searched={true} query="q" />,
    )
    expect(screen.getByText(/re-ranked by xgboost/i)).toBeInTheDocument()
  })
})

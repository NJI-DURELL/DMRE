import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import MemoryCard from '../components/MemoryCard'
import * as api from '../services/api'

vi.mock('../services/api', () => ({
  verifyMemory: vi.fn(),
}))

const BASE_RESULT = {
  memory_id: 'mem-001',
  url: 'https://example.com/article',
  title: 'Machine Learning Basics',
  snippet: 'An introduction to machine learning concepts.',
  semantic_similarity: 0.85,
  visited_at: new Date(Date.now() - 3600000).toISOString(), // 1h ago
  visit_count: 3,
  dwell_time: 120,
  blockchain_anchored: true,
}

describe('MemoryCard', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders title and snippet', () => {
    render(<MemoryCard result={BASE_RESULT} rank={1} />)
    expect(screen.getByText('Machine Learning Basics')).toBeInTheDocument()
    expect(screen.getByText('An introduction to machine learning concepts.')).toBeInTheDocument()
  })

  it('renders domain from url', () => {
    render(<MemoryCard result={BASE_RESULT} rank={1} />)
    expect(screen.getByText('example.com')).toBeInTheDocument()
  })

  it('renders rank badge with correct number', () => {
    render(<MemoryCard result={BASE_RESULT} rank={2} />)
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('shows (Untitled page) when title is empty', () => {
    render(<MemoryCard result={{ ...BASE_RESULT, title: '' }} rank={1} />)
    expect(screen.getByText('(Untitled page)')).toBeInTheDocument()
  })

  it('shows relevance percentage', () => {
    render(<MemoryCard result={BASE_RESULT} rank={1} />)
    expect(screen.getByText('85%')).toBeInTheDocument()
  })

  it('shows dwell time when > 0', () => {
    render(<MemoryCard result={BASE_RESULT} rank={1} />)
    expect(screen.getByText(/on page/)).toBeInTheDocument()
  })

  it('hides dwell time when 0', () => {
    render(<MemoryCard result={{ ...BASE_RESULT, dwell_time: 0 }} rank={1} />)
    expect(screen.queryByText(/on page/)).not.toBeInTheDocument()
  })

  it('renders Verify button in idle state initially', () => {
    render(<MemoryCard result={BASE_RESULT} rank={1} />)
    expect(screen.getByRole('button', { name: /verify/i })).toBeInTheDocument()
  })

  it('calls verifyMemory with memory_id on click', async () => {
    api.verifyMemory.mockResolvedValueOnce({ verified: true, block_number: 42 })
    render(<MemoryCard result={BASE_RESULT} rank={1} />)
    fireEvent.click(screen.getByRole('button', { name: /verify/i }))
    await waitFor(() => expect(api.verifyMemory).toHaveBeenCalledWith('mem-001'))
  })

  it('shows Verified state after successful verification', async () => {
    api.verifyMemory.mockResolvedValueOnce({ verified: true, block_number: 7 })
    render(<MemoryCard result={BASE_RESULT} rank={1} />)
    fireEvent.click(screen.getByRole('button', { name: /verify/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /verified/i })).toBeInTheDocument())
    expect(screen.getByText(/block 7/i)).toBeInTheDocument()
  })

  it('shows Failed state when verification returns false', async () => {
    api.verifyMemory.mockResolvedValueOnce({ verified: false, block_number: 0 })
    render(<MemoryCard result={BASE_RESULT} rank={1} />)
    fireEvent.click(screen.getByRole('button', { name: /verify/i }))
    await waitFor(() => expect(screen.getByText(/failed/i)).toBeInTheDocument())
    expect(screen.getByText(/hash mismatch/i)).toBeInTheDocument()
  })

  it('shows Failed state on network error', async () => {
    api.verifyMemory.mockRejectedValueOnce(new Error('Network error'))
    render(<MemoryCard result={BASE_RESULT} rank={1} />)
    fireEvent.click(screen.getByRole('button', { name: /verify/i }))
    await waitFor(() => expect(screen.getByText(/failed/i)).toBeInTheDocument())
  })
})

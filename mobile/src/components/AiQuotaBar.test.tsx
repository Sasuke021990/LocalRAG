import React from 'react'
import { render, screen } from '@testing-library/react-native'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

jest.mock('lucide-react-native', () => ({ Sparkles: 'Sparkles' }))

const mockFetchSubscription = jest.fn()
jest.mock('../api/billing', () => ({
  fetchSubscription: () => mockFetchSubscription(),
}))

import AiQuotaBar from './AiQuotaBar'

let qc: QueryClient | null = null

function renderBar(props: { compact?: boolean } = {}) {
  qc = new QueryClient({
    defaultOptions: {
      queries: {
        // Settle a rejected query immediately instead of backing off.
        retry: false,
        // Without this, each cached query holds a 5-minute garbage-collection
        // timer open and Jest refuses to exit after the run completes.
        gcTime: 0,
      },
    },
  })
  return render(
    <QueryClientProvider client={qc}>
      <AiQuotaBar {...props} />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  // Drop any in-flight query and its cache entry so nothing outlives the test.
  qc?.clear()
  qc = null
})

const SUB = (over: Record<string, any> = {}) => ({
  plan: 'free',
  quota_bytes: 1000,
  ai_questions_used_today: 0,
  ai_questions_per_day: 20,
  ai_unlimited_plan_wide: false,
  features: {},
  ...over,
})

beforeEach(() => jest.clearAllMocks())

describe('rendering', () => {
  test('shows used-of-limit and the remaining count', async () => {
    mockFetchSubscription.mockResolvedValue(SUB({ ai_questions_used_today: 5 }))
    renderBar()
    expect(await screen.findByText('AI answers today')).toBeTruthy()
    expect(screen.getByText('5 of 20 used')).toBeTruthy()
    expect(screen.getByText('15')).toBeTruthy()
  })

  test('marks a plan-wide unlimited allowance as per-user', async () => {
    mockFetchSubscription.mockResolvedValue(SUB({ ai_questions_used_today: 2, ai_unlimited_plan_wide: true }))
    renderBar()
    expect(await screen.findByText(/per user/)).toBeTruthy()
  })

  test('stays silent on a failed fetch rather than showing a wrong count', async () => {
    // Supplementary indicator: a broken quota number would be worse than
    // none, and the screens owning this data surface their own errors.
    mockFetchSubscription.mockRejectedValue(new Error('offline'))
    renderBar()
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.queryByText('AI answers today')).toBeNull()
  })

  test('renders nothing when the plan reports no daily limit', async () => {
    mockFetchSubscription.mockResolvedValue(SUB({ ai_questions_per_day: 0 }))
    renderBar()
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.queryByText('AI answers today')).toBeNull()
  })
})

describe('warning states', () => {
  test('no warning while comfortably under the limit', async () => {
    mockFetchSubscription.mockResolvedValue(SUB({ ai_questions_used_today: 1 }))
    renderBar()
    await screen.findByText('AI answers today')
    expect(screen.queryByText(/Running low/)).toBeNull()
    expect(screen.queryByText(/resets tomorrow/)).toBeNull()
  })

  test('warns when running low (within 20% of the allowance)', async () => {
    mockFetchSubscription.mockResolvedValue(SUB({ ai_questions_used_today: 17 })) // 3 of 20 left
    renderBar()
    expect(await screen.findByText(/Running low/)).toBeTruthy()
  })

  test('warns on a small plan before it is too late to matter', async () => {
    // 20% of 5 rounds down to 1 — a one-question warning is useless, so the
    // threshold has a floor of 3.
    mockFetchSubscription.mockResolvedValue(SUB({ ai_questions_per_day: 5, ai_questions_used_today: 2 }))
    renderBar()
    expect(await screen.findByText(/Running low/)).toBeTruthy()
  })

  test('reports the limit reached at zero remaining', async () => {
    mockFetchSubscription.mockResolvedValue(SUB({ ai_questions_used_today: 20 }))
    renderBar()
    expect(await screen.findByText(/resets tomorrow/)).toBeTruthy()
    expect(screen.getByText('0')).toBeTruthy()
    // "Running low" would be contradictory once there's nothing left.
    expect(screen.queryByText(/Running low/)).toBeNull()
  })

  test('clamps an over-limit count instead of showing a negative remainder', async () => {
    // The backend counts a question at dispatch, so a race can briefly report
    // used > limit; that must never render as "-2 left".
    mockFetchSubscription.mockResolvedValue(SUB({ ai_questions_used_today: 22 }))
    renderBar()
    await screen.findByText(/resets tomorrow/)
    expect(screen.getByText('0')).toBeTruthy()
    expect(screen.getByText('20 of 20 used')).toBeTruthy()
  })
})

describe('compact variant', () => {
  test('shows just the remaining count for the chat header', async () => {
    mockFetchSubscription.mockResolvedValue(SUB({ ai_questions_used_today: 5 }))
    renderBar({ compact: true })
    expect(await screen.findByText('15 left')).toBeTruthy()
    // The full variant's chrome stays out of the header strip.
    expect(screen.queryByText('AI answers today')).toBeNull()
  })

  test('says the limit is reached when exhausted', async () => {
    mockFetchSubscription.mockResolvedValue(SUB({ ai_questions_used_today: 20 }))
    renderBar({ compact: true })
    expect(await screen.findByText('Limit reached')).toBeTruthy()
  })
})

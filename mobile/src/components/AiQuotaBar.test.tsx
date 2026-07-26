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

describe('warning states (paid plans — Free is covered separately below)', () => {
  test('no warning while comfortably above the 50% threshold', async () => {
    // limit 20 -> threshold is 10 remaining; 15 remaining is well clear of it.
    mockFetchSubscription.mockResolvedValue(SUB({ plan: 'pro', ai_questions_used_today: 5 }))
    renderBar()
    await screen.findByText('AI answers today')
    expect(screen.queryByText(/Running low/)).toBeNull()
    expect(screen.queryByText(/resets tomorrow/)).toBeNull()
  })

  test('does not warn one question above the 50% boundary', async () => {
    // limit 20 -> threshold is 10 remaining; 11 remaining must not warn yet.
    mockFetchSubscription.mockResolvedValue(SUB({ plan: 'pro', ai_questions_used_today: 9 }))
    renderBar()
    await screen.findByText('AI answers today')
    expect(screen.queryByText(/Running low/)).toBeNull()
  })

  test('warns exactly at the 50% boundary', async () => {
    // limit 20 -> threshold is 10 remaining; 10 remaining should warn.
    mockFetchSubscription.mockResolvedValue(SUB({ plan: 'pro', ai_questions_used_today: 10 }))
    renderBar()
    expect(await screen.findByText(/Running low/)).toBeTruthy()
  })

  test('warns on a small plan before it is too late to matter', async () => {
    // floor(5 * 0.5) = 2, but the floor of 3 wins: max(3, 2) = 3. Without
    // that floor, a 5/day plan would only warn with 2 questions left.
    mockFetchSubscription.mockResolvedValue(
      SUB({ plan: 'pro', ai_questions_per_day: 5, ai_questions_used_today: 2 }),
    )
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

describe('Free plan skips the "running low" stage', () => {
  // Free's allowance is small enough, and the upgrade nudge pointed enough,
  // that an early warning reads as nagging rather than useful notice — it
  // goes straight from normal to exhausted with nothing amber in between.
  test('no warning even at the boundary that would trigger it on a paid plan', async () => {
    mockFetchSubscription.mockResolvedValue(SUB({ plan: 'free', ai_questions_used_today: 10 })) // 10 of 20 left
    renderBar()
    await screen.findByText('AI answers today')
    expect(screen.queryByText(/Running low/)).toBeNull()
  })

  test('no warning one question before exhaustion', async () => {
    mockFetchSubscription.mockResolvedValue(SUB({ plan: 'free', ai_questions_used_today: 19 }))
    renderBar()
    await screen.findByText('AI answers today')
    expect(screen.queryByText(/Running low/)).toBeNull()
  })

  test('still reports exhausted at zero remaining', async () => {
    // The floor doesn't apply here — only the amber "running low" stage is
    // skipped. Free still gets the rose "limit reached" state.
    mockFetchSubscription.mockResolvedValue(SUB({ plan: 'free', ai_questions_used_today: 20 }))
    renderBar()
    expect(await screen.findByText(/resets tomorrow/)).toBeTruthy()
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

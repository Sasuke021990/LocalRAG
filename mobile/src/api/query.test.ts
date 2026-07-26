jest.mock('expo/fetch', () => ({ fetch: jest.fn() }))
jest.mock('./client', () => ({
  request: jest.fn(),
  jsonBody: (method: string, body: unknown) => ({ method, body: JSON.stringify(body) }),
  getToken: jest.fn().mockResolvedValue('jwt-123'),
  API_BASE: 'https://api.test',
}))

import { fetch as expoFetch } from 'expo/fetch'
import { request } from './client'
import { streamQuery } from './query'

beforeEach(() => jest.clearAllMocks())

function fakeReader(frames: string[]) {
  let i = 0
  return {
    read: async () => {
      if (i >= frames.length) return { done: true, value: undefined }
      const value = new TextEncoder().encode(frames[i])
      i += 1
      return { done: false, value }
    },
  }
}

function fakeStreamResponse(ok: boolean, status: number, frames: string[] = [], jsonBody: any = {}) {
  return {
    ok,
    status,
    json: async () => jsonBody,
    body: { getReader: () => fakeReader(frames) },
  }
}

describe('streamQuery', () => {
  test('a real stream (via expo/fetch) delivers tokens/sources/done as they arrive', async () => {
    ;(expoFetch as jest.Mock).mockResolvedValue(fakeStreamResponse(true, 200, [
      'event: sources\ndata: [{"file_name":"a.pdf","pool":"General","chunk_index":0,"score":0.9,"content":"x"}]\n\n',
      'event: token\ndata: "Hello"\n\n',
      'event: done\ndata: {"answer":"Hello","conversation_id":"c1"}\n\n',
    ]))

    const h = { onSources: jest.fn(), onToken: jest.fn(), onDone: jest.fn(), onError: jest.fn() }
    await streamQuery('hi', {}, h)

    expect(h.onSources).toHaveBeenCalledWith([{ file_name: 'a.pdf', pool: 'General', chunk_index: 0, score: 0.9, content: 'x' }])
    expect(h.onToken).toHaveBeenCalledWith('Hello')
    expect(h.onDone).toHaveBeenCalledWith({ answer: 'Hello', conversation_id: 'c1' })
    expect(h.onError).not.toHaveBeenCalled()
    expect(request).not.toHaveBeenCalled() // real stream worked -- never touched the fallback endpoint
  })

  // Regression test: a 429/500 used to either get misread as SSE frames or
  // silently trigger a second request before reaching onError.
  test('a non-ok response (quota exceeded) reaches onError directly, without retrying the query', async () => {
    ;(expoFetch as jest.Mock).mockResolvedValue(fakeStreamResponse(false, 429, [], { detail: 'Daily AI question limit reached' }))

    const h = { onError: jest.fn(), onDone: jest.fn() }
    await streamQuery('hi', {}, h)

    expect(h.onError).toHaveBeenCalledTimes(1)
    expect(h.onError.mock.calls[0][0].message).toBe('Daily AI question limit reached')
    expect(request).not.toHaveBeenCalled()
  })

  test('a stream that breaks mid-flight reaches onError, without retrying the query', async () => {
    const reader = {
      read: jest.fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode('event: token\ndata: "partial') })
        .mockRejectedValueOnce(new Error('connection dropped')),
    }
    ;(expoFetch as jest.Mock).mockResolvedValue({ ok: true, status: 200, body: { getReader: () => reader } })

    const h = { onError: jest.fn(), onToken: jest.fn() }
    await streamQuery('hi', {}, h)

    expect(h.onError).toHaveBeenCalledWith(expect.objectContaining({ message: 'connection dropped' }))
    expect(request).not.toHaveBeenCalled()
  })

  test('no readable body falls back to the plain /query endpoint', async () => {
    ;(expoFetch as jest.Mock).mockResolvedValue({ ok: true, status: 200, body: null })
    ;(request as jest.Mock).mockResolvedValue({ answer: 'from fallback', sources: [], processing_time: 1 })

    const h = { onToken: jest.fn(), onDone: jest.fn(), onError: jest.fn() }
    await streamQuery('hi', {}, h)

    expect(request).toHaveBeenCalledTimes(1)
    expect(h.onDone).toHaveBeenCalled()
    expect(h.onError).not.toHaveBeenCalled()
  })

  test('a network-level failure before any response falls back to the plain /query endpoint', async () => {
    ;(expoFetch as jest.Mock).mockRejectedValue(new Error('Network request failed'))
    ;(request as jest.Mock).mockResolvedValue({ answer: 'from fallback', sources: [], processing_time: 1 })

    const h = { onDone: jest.fn(), onError: jest.fn() }
    await streamQuery('hi', {}, h)

    expect(request).toHaveBeenCalledTimes(1)
    expect(h.onDone).toHaveBeenCalled()
  })

  test('a failure in the fallback path itself reaches onError exactly once', async () => {
    ;(expoFetch as jest.Mock).mockResolvedValue({ ok: true, status: 200, body: null })
    ;(request as jest.Mock).mockRejectedValue(new Error('Server unavailable'))

    const h = { onError: jest.fn() }
    await streamQuery('hi', {}, h)

    expect(h.onError).toHaveBeenCalledTimes(1)
    expect(h.onError).toHaveBeenCalledWith(expect.objectContaining({ message: 'Server unavailable' }))
  })
})

// ── Stop generation (task.md P2 #22) ───────────────────────────────────────

test('the abort signal is forwarded so the backend can cancel generation', async () => {
  const controller = new AbortController()
  ;(expoFetch as jest.Mock).mockResolvedValue(
    fakeStreamResponse(true, 200, ['event: done\ndata: {"answer":"hi"}\n\n']),
  )

  await streamQuery('q', { signal: controller.signal }, {})

  // main.py's query_stream watches for the closed connection this produces.
  expect((expoFetch as jest.Mock).mock.calls[0][1].signal).toBe(controller.signal)
})

test('an aborted request is not reported as an error', async () => {
  const controller = new AbortController()
  controller.abort()
  ;(expoFetch as jest.Mock).mockRejectedValue(
    Object.assign(new Error('Aborted'), { name: 'AbortError' }),
  )
  const onError = jest.fn()

  await streamQuery('q', { signal: controller.signal }, { onError })

  // A deliberate stop must not paint a red failure bubble over the answer
  // the user chose to end.
  expect(onError).not.toHaveBeenCalled()
})

test('an aborted request does not fall back and re-run the query', async () => {
  // Falling back would re-charge the daily AI quota for a question the user
  // just cancelled.
  const controller = new AbortController()
  controller.abort()
  ;(expoFetch as jest.Mock).mockRejectedValue(new Error('Aborted'))

  await streamQuery('q', { signal: controller.signal }, {})

  expect(request).not.toHaveBeenCalled()
})

test('a mid-stream abort stops dispatching further frames', async () => {
  const controller = new AbortController()
  const onToken = jest.fn((t: string) => {
    // Cancel as soon as the first token lands.
    if (t === 'one') controller.abort()
  })
  ;(expoFetch as jest.Mock).mockResolvedValue(
    fakeStreamResponse(true, 200, [
      'event: token\ndata: "one"\n\n',
      'event: token\ndata: "two"\n\n',
      'event: token\ndata: "three"\n\n',
    ]),
  )

  await streamQuery('q', { signal: controller.signal }, { onToken })

  expect(onToken).toHaveBeenCalledWith('one')
  expect(onToken).not.toHaveBeenCalledWith('three')
})

test('a normal request without a signal still works', async () => {
  ;(expoFetch as jest.Mock).mockResolvedValue(
    fakeStreamResponse(true, 200, ['event: token\ndata: "hello"\n\n']),
  )
  const onToken = jest.fn()
  const onError = jest.fn()

  await streamQuery('q', {}, { onToken, onError })

  expect(onToken).toHaveBeenCalledWith('hello')
  expect(onError).not.toHaveBeenCalled()
})

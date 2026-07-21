import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamQuery } from './query.js'

afterEach(() => { vi.restoreAllMocks() })

/** Fake a fetch Response whose body.getReader() yields the given string chunks. */
function mockStream(chunks) {
  const encoder = new TextEncoder()
  let i = 0
  const reader = {
    read: async () =>
      i < chunks.length
        ? { value: encoder.encode(chunks[i++]), done: false }
        : { value: undefined, done: true },
  }
  global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, body: { getReader: () => reader } })
}

function runStream(chunks) {
  mockStream(chunks)
  const tokens = []
  let sources, done
  return new Promise((resolve) => {
    streamQuery('hi', {}, {
      onSources: (s) => { sources = s },
      onToken: (t) => tokens.push(t),
      onDone: (d) => { done = d; resolve({ tokens, sources, done }) },
      onError: () => resolve({ tokens, sources, done, errored: true }),
    })
  })
}

describe('streamQuery SSE parsing', () => {
  // sse_starlette emits \r\n line endings (\r\n\r\n between frames) — the bug
  // that made the chat hang was splitting frames on \n\n, which never matches.
  it('parses CRLF-framed SSE (sse_starlette default)', async () => {
    const body =
      'event: sources\r\ndata: []\r\n\r\n' +
      'event: token\r\ndata: "Hi there!"\r\n\r\n' +
      'event: done\r\ndata: {"answer":"Hi there!","refused":false}\r\n\r\n'
    const { tokens, sources, done } = await runStream([body])
    expect(sources).toEqual([])
    expect(tokens.join('')).toBe('Hi there!')
    expect(done.answer).toBe('Hi there!')
    expect(done.refused).toBe(false)
  })

  it('handles a CRLF separator split across two chunks', async () => {
    // The blank-line separator is torn between reads: "...\r\n\r" | "\n..."
    const chunks = [
      'event: token\r\ndata: "part"\r\n\r',
      '\nevent: done\r\ndata: {"answer":"part"}\r\n\r\n',
    ]
    const { tokens, done } = await runStream(chunks)
    expect(tokens.join('')).toBe('part')
    expect(done.answer).toBe('part')
  })

  it('still parses plain LF-framed SSE', async () => {
    const body = 'event: token\ndata: "x"\n\nevent: done\ndata: {"answer":"x"}\n\n'
    const { tokens, done } = await runStream([body])
    expect(tokens.join('')).toBe('x')
    expect(done.answer).toBe('x')
  })
})

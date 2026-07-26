jest.mock('../api/query', () => ({ streamQuery: jest.fn() }))
jest.mock('../api/chat', () => ({
  listConversations: jest.fn().mockResolvedValue({ conversations: [] }),
  getConversation: jest.fn(),
  renameConversation: jest.fn(),
  deleteConversation: jest.fn(),
}))

import { useChatStore } from './chatStore'
import { streamQuery } from '../api/query'

beforeEach(() => {
  jest.clearAllMocks()
  useChatStore.setState({
    history: [], loading: false, activeConversationId: '', pool: '', poolChosen: false,
    conversations: [], conversationsLoading: true,
  })
})

// Regression test: a failed query used to leave the bubble streaming:false
// with no error message at all (an empty grey box) -- the actual reported
// "chat not working properly" bug.
test('a failed query surfaces the backend error message on the bubble', async () => {
  ;(streamQuery as jest.Mock).mockImplementation(async (_q, _opts, handlers) => {
    handlers.onError(new Error('Daily AI question limit reached'))
  })

  useChatStore.getState().submit('what is in my docs?')
  await new Promise((r) => setTimeout(r, 0))

  const msg = useChatStore.getState().history[0]
  expect(msg.error).toBe('Daily AI question limit reached')
  expect(msg.streaming).toBe(false)
  expect(useChatStore.getState().loading).toBe(false)
})

test('a failed query with no message falls back to a generic one', async () => {
  ;(streamQuery as jest.Mock).mockImplementation(async (_q, _opts, handlers) => {
    handlers.onError(new Error())
  })

  useChatStore.getState().submit('hello')
  await new Promise((r) => setTimeout(r, 0))

  expect(useChatStore.getState().history[0].error).toBe('Something went wrong. Please try again.')
})

test('a successful query never sets an error', async () => {
  ;(streamQuery as jest.Mock).mockImplementation(async (_q, _opts, handlers) => {
    handlers.onToken('Here is your answer.')
    handlers.onDone({ answer: 'Here is your answer.', conversation_id: 'c1' })
  })

  useChatStore.getState().submit('hello')
  await new Promise((r) => setTimeout(r, 0))

  const msg = useChatStore.getState().history[0]
  expect(msg.error).toBeUndefined()
  expect(msg.answer).toBe('Here is your answer.')
})

// ── Stop generation + retry (task.md P2 #22) ────────────────────────────────

test('stop aborts the in-flight request so the backend stops generating', async () => {
  let capturedSignal: AbortSignal | undefined
  ;(streamQuery as jest.Mock).mockImplementation(async (_q, opts) => {
    capturedSignal = opts.signal
    // Never resolves — simulates an answer still streaming.
    await new Promise(() => {})
  })

  useChatStore.getState().submit('a long question')
  await new Promise((r) => setTimeout(r, 0))
  expect(useChatStore.getState().loading).toBe(true)
  expect(capturedSignal?.aborted).toBe(false)

  useChatStore.getState().stop()

  // Aborting closes the connection, which is what main.py's query_stream
  // watches to cancel generation server-side.
  expect(capturedSignal?.aborted).toBe(true)
  expect(useChatStore.getState().loading).toBe(false)
})

test('stop keeps the partial answer rather than wiping or erroring it', async () => {
  ;(streamQuery as jest.Mock).mockImplementation(async (_q, _opts, handlers) => {
    handlers.onToken('Half an ans')
    await new Promise(() => {})
  })

  useChatStore.getState().submit('q')
  await new Promise((r) => setTimeout(r, 0))
  useChatStore.getState().stop()

  const msg = useChatStore.getState().history[0]
  expect(msg.answer).toBe('Half an ans')
  expect(msg.streaming).toBe(false)
  // A deliberate stop is not a failure — no red error state.
  expect(msg.error).toBeUndefined()
})

test('stop is a no-op when nothing is in flight', () => {
  useChatStore.setState({ loading: false, history: [] })
  expect(() => useChatStore.getState().stop()).not.toThrow()
  expect(useChatStore.getState().loading).toBe(false)
})

test('retry re-sends the last question without duplicating it in the transcript', async () => {
  ;(streamQuery as jest.Mock).mockImplementation(async (_q, _opts, handlers) => {
    handlers.onError(new Error('server exploded'))
  })

  useChatStore.getState().submit('what is in my docs?')
  await new Promise((r) => setTimeout(r, 0))
  expect(useChatStore.getState().history).toHaveLength(1)

  // Second attempt succeeds.
  ;(streamQuery as jest.Mock).mockImplementation(async (_q, _opts, handlers) => {
    handlers.onToken('It worked this time.')
    handlers.onDone({ answer: 'It worked this time.' })
  })

  useChatStore.getState().retry()
  await new Promise((r) => setTimeout(r, 0))

  const history = useChatStore.getState().history
  // The failed turn was replaced, not appended to.
  expect(history).toHaveLength(1)
  expect(history[0].query).toBe('what is in my docs?')
  expect(history[0].answer).toBe('It worked this time.')
  expect(history[0].error).toBeUndefined()
})

test('retry is ignored while a request is still in flight', async () => {
  ;(streamQuery as jest.Mock).mockImplementation(async () => { await new Promise(() => {}) })

  useChatStore.getState().submit('q')
  await new Promise((r) => setTimeout(r, 0))
  ;(streamQuery as jest.Mock).mockClear()

  useChatStore.getState().retry()
  expect(streamQuery).not.toHaveBeenCalled()
})

test('retry is a no-op on an empty transcript', () => {
  useChatStore.setState({ loading: false, history: [] })
  useChatStore.getState().retry()
  expect(streamQuery).not.toHaveBeenCalled()
})

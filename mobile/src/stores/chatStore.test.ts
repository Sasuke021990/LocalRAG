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

import { QueryClient } from '@tanstack/react-query'

/**
 * The app's single React Query client.
 *
 * Lives in its own module (rather than inside App.tsx) so non-React code can
 * invalidate cached queries too — chatStore needs this to refresh the AI
 * quota after an answer completes, since sending a question consumes one.
 */
export const queryClient = new QueryClient()

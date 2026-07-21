import { request, jsonBody } from './client.js'

export const sendQuery = (query, topK = 10, rerankTopK = 5) =>
  request('/query', jsonBody('POST', { query, top_k: topK, rerank_top_k: rerankTopK }))

export const fetchHealth = () => request('/health')

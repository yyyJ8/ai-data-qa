export interface Session {
  session_id: number
  title: string
  pinned: number
  created_at: string
  updated_at: string
  message_count: number
  preview?: string | null
}

export interface Stage {
  step: number
  title: string
  detail: string
}

export interface TableData {
  columns: string[]
  rows: (string | number | null)[][]
}

export interface DraftMeta {
  sql?: string
  elapsed_ms?: number
  prompt_tokens?: number
  completion_tokens?: number
}

export interface AssistantDraft {
  question?: string
  stages: Stage[]
  table?: TableData
  chart?: string
  insight?: string
  meta?: DraftMeta
  error?: string
  streaming: boolean
}

export type ChatItem =
  | { kind: 'user'; text: string }
  | { kind: 'assistant'; draft: AssistantDraft }

export interface AppConfig {
  greeting: boolean
  greetingText: string
  greetingQuestions: string[]
  suggestions: boolean
  hotThreshold: number
}

export interface PagedTable {
  table: string
  columns: string[]
  rows: (string | number | null)[][]
  total: number
  page: number
  page_size: number
}

export interface ModelConfig {
  base_url: string
  model: string
  thinking: boolean
  reasoning_effort: 'low' | 'medium' | 'high'
  api_key_masked: string
  configured: boolean
}

export interface ModelTestResult {
  ok: boolean
  model?: string
  latency_ms?: number
  total_ms?: number
  reply?: string
  error?: string
}

export interface FeedbackItem {
  feedback_id: number
  session_id: number | null
  question: string
  sql: string | null
  reason: string | null
  status: '待处理' | '已处理'
  remark: string | null
  created_at: string
}

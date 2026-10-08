export interface DocumentMetadata {
  doc_id: string;
  filename: string;
  file_type: string;
  upload_time: string;
  file_size: number;
  total_chunks: number;
  chunking_strategy?: 'standard' | 'semantic' | 'agentic' | 'late' | string;
}


export interface SourceCitation {
  content: string;
  doc_id: string;
  filename: string;
  chunk_index: number;
  score: number;
}

export interface SystemExecutionResult {
  system: 'agent' | 'workflow';
  answer: string;
  latency_ms: number;
  total_tokens: number;
  cost: number;
  iterations: number;
  termination_reason: string;
  sources: SourceCitation[];
  used_fallback: boolean;
  trace: AgentStepTrace[];
  mcp_results?: McpToolResult[];
}

export interface ComparisonMetrics {
  latency_winner: 'agent' | 'workflow' | 'tie';
  tokens_winner: 'agent' | 'workflow' | 'tie';
  cost_winner: 'agent' | 'workflow' | 'tie';
  accuracy_winner: 'agent' | 'workflow' | 'tie';
  summary_verdict: string;
}

export type ArtifactType = 'key_points' | 'table' | 'timeline' | 'chart' | 'mindmap';

export interface Artifact {
  artifact_id: string;
  type: ArtifactType;
  title: string;
  description: string;
  data: Record<string, any>;
  markdown: string;
  source_files: string[];
  generated_by: string;
  created_at: string;
}

/** A tool the backend agent called on an external MCP server. A result with `type` and `data` is an Artifact. */
export interface McpToolResult {
  server_id: string;
  server_name: string;
  tool_name: string;
  arguments: Record<string, any>;
  success: boolean;
  result?: any;
  error?: string | null;
}

export const isArtifact = (value: any): value is Artifact =>
  Boolean(value) && typeof value === 'object' && 'type' in value && 'data' in value;

/** The document a user question was asked about. */
export interface ChatAttachment {
  doc_id: string;
  filename: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  attachment?: ChatAttachment;
  error?: boolean; // an assistant message reporting that the question could not be answered
  sources?: SourceCitation[];
  used_fallback?: boolean;
  mode?: 'compare' | 'agent' | 'workflow' | 'standard';
  agent_result?: SystemExecutionResult;
  workflow_result?: SystemExecutionResult;
  comparison?: ComparisonMetrics;
  mcp_results?: McpToolResult[];
}

/** A conversation in the sidebar; kept in the browser (localStorage), per user. */
export interface ChatSession {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
}

export interface DocumentUploadResponse {
  message: string;
  document: DocumentMetadata;
}

export interface DocumentListResponse {
  documents: DocumentMetadata[];
  total_documents: number;
}

export interface ChatResponse {
  question: string;
  answer: string;
  sources: SourceCitation[];
  used_fallback: boolean;
  mode?: 'compare' | 'agent' | 'workflow' | 'standard';
  agent_result?: SystemExecutionResult;
  workflow_result?: SystemExecutionResult;
  comparison?: ComparisonMetrics;
  mcp_results?: McpToolResult[];
}

export interface HealthResponse {
  status: string;
  vector_db_connected: boolean;
}

export interface AgentStepTrace {
  step_number: number;
  action: string;
  input_summary: string;
  result_summary: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  step_cost: number;
  cumulative_cost: number;
  details?: Record<string, any>;
}


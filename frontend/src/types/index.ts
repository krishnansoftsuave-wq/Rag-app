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

export interface ArtifactState {
  status: 'loading' | 'ready' | 'error';
  artifact?: Artifact;
  serverName?: string;
  error?: string;
}

export interface GenerateArtifactResponse {
  success: boolean;
  artifact?: Artifact;
  server_id?: string;
  server_name?: string;
  error?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  question?: string;
  sources?: SourceCitation[];
  used_fallback?: boolean;
  mode?: 'compare' | 'agent' | 'workflow' | 'standard';
  agent_result?: SystemExecutionResult;
  workflow_result?: SystemExecutionResult;
  comparison?: ComparisonMetrics;
  artifact?: ArtifactState;
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
}

export interface HealthResponse {
  status: string;
  vector_db_connected: boolean;
  total_documents: number;
  total_chunks: number;
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

export interface QuestionResult {
  system: 'agent' | 'workflow';
  question_id: string;
  question: string;
  question_type: string;
  passed: boolean;
  score: number;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  iterations: number;
  termination_reason: string;
  final_answer: string;
  trace?: AgentStepTrace[];
}

export interface SystemMetrics {
  pass_rate: number;
  outcome_pass_rate?: number;
  trajectory_pass_rate?: number;
  outcome_vs_trajectory_gap?: number;
  tool_choice_accuracy?: number;
  argument_validity_rate?: number;
  step_efficiency?: number;
  p50_latency_ms: number;
  cost_p50?: number;
  cost_max?: number;
  total_tokens: number;
  total_cost: number;
  cost_per_question: number;
  total_questions: number;
  failure_modes?: Record<string, number>;
  gap_cases?: Array<{
    question_id: string;
    question: string;
    actual_trajectory: string[];
    expected_trajectory: string[];
    reason: string;
  }>;
}

export interface MitigationPrice {
  mitigation_description: string;
  latency_delta_ms: number;
  token_delta_per_question: number;
  cost_delta_per_question: number;
  outcome_pass_rate_delta: number;
  trajectory_pass_rate_delta: number;
}

export interface RegressionRow {
  failure_mode: string;
  original_agent: number;
  fixed_agent: number;
  change: string;
}

export interface EvaluationSummary {
  agent: SystemMetrics;
  workflow: SystemMetrics;
  verdict: string;
  mitigation_price?: MitigationPrice;
  regression_matrix?: RegressionRow[];
  agent_question_results: QuestionResult[];
  workflow_question_results: QuestionResult[];
}


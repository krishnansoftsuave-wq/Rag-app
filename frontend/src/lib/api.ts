import {
  DocumentUploadResponse,
  DocumentListResponse,
  ChatResponse,
  HealthResponse,
  EvaluationSummary,
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export function getAuthToken(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('docubrain_token');
  }
  return null;
}

export function setAuthToken(token: string) {
  if (typeof window !== 'undefined') {
    localStorage.setItem('docubrain_token', token);
  }
}

export function removeAuthToken() {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('docubrain_token');
    localStorage.removeItem('docubrain_user');
  }
}

function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

// Authentication API
export async function registerUser(username: string, email: string, password: string) {
  const res = await fetch(`${API_BASE_URL}/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
    throw new Error(err.detail || 'Failed to register account');
  }
  const data = await res.json();
  setAuthToken(data.access_token);
  if (typeof window !== 'undefined') {
    localStorage.setItem('docubrain_user', JSON.stringify(data.user));
  }
  return data;
}

export async function loginUser(username_or_email: string, password: string) {
  const res = await fetch(`${API_BASE_URL}/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username_or_email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Login failed' }));
    throw new Error(err.detail || 'Invalid username or password');
  }
  const data = await res.json();
  setAuthToken(data.access_token);
  if (typeof window !== 'undefined') {
    localStorage.setItem('docubrain_user', JSON.stringify(data.user));
  }
  return data;
}

export async function fetchCurrentUser() {
  const res = await fetch(`${API_BASE_URL}/v1/auth/me`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) return null;
  return res.json();
}

// MCP Tools Execution
export async function callMcpTool(name: string, args: Record<string, any> = {}) {
  const res = await fetch(`${API_BASE_URL}/v1/mcp/tools/call`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ name, arguments: args }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'MCP Tool execution failed' }));
    throw new Error(err.detail || 'MCP Tool call failed');
  }
  return res.json();
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) {
    throw new Error('Backend health check failed');
  }
  return res.json();
}

export async function uploadDocument(
  file: File,
  chunkingStrategy: 'standard' | 'semantic' | 'agentic' | 'late' = 'agentic'
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const url = `${API_BASE_URL}/upload?chunking_strategy=${chunkingStrategy}`;

  const res = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(errorData.detail || 'Failed to upload document');
  }

  return res.json();
}

export async function fetchDocuments(): Promise<DocumentListResponse> {
  const res = await fetch(`${API_BASE_URL}/documents`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to fetch documents');
  }
  return res.json();
}

export async function deleteDocument(docId: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE_URL}/documents/${docId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to delete document');
  }
  return res.json();
}

export async function sendChatMessage(
  question: string,
  docIds?: string[],
  apiKey?: string,
  mode: 'compare' | 'agent' | 'workflow' | 'standard' = 'agent'
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      question,
      doc_ids: docIds,
      api_key: apiKey,
      mode,
    }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Chat query failed' }));
    throw new Error(errorData.detail || 'Failed to process question');
  }

  return res.json();
}

export async function fetchEvaluationResults(): Promise<EvaluationSummary> {
  const res = await fetch(`${API_BASE_URL}/evaluation/results`);
  if (!res.ok) {
    throw new Error('Failed to fetch evaluation benchmark results');
  }
  return res.json();
}

export async function runEvaluationBenchmark(): Promise<{ message: string; summary: EvaluationSummary }> {
  const res = await fetch(`${API_BASE_URL}/evaluation/run?system=both`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to run benchmark');
  }
  return res.json();
}

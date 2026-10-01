import {
  DocumentUploadResponse,
  DocumentListResponse,
  ChatResponse,
  HealthResponse,
  EvaluationSummary,
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

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
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(errorData.detail || 'Failed to upload document');
  }

  return res.json();
}


export async function fetchDocuments(): Promise<DocumentListResponse> {
  const res = await fetch(`${API_BASE_URL}/documents`);
  if (!res.ok) {
    throw new Error('Failed to fetch documents');
  }
  return res.json();
}

export async function deleteDocument(docId: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE_URL}/documents/${docId}`, {
    method: 'DELETE',
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
  });
  if (!res.ok) {
    throw new Error('Failed to run benchmark');
  }
  return res.json();
}


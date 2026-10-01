'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { ApiKeyModal } from '@/components/ApiKeyModal';
import { MetricsCards } from '@/components/evaluation/MetricsCards';
import { ComparisonTable } from '@/components/evaluation/ComparisonTable';
import { QuestionResults } from '@/components/evaluation/QuestionResults';
import { AgentTrace } from '@/components/evaluation/AgentTrace';
import { BudgetMonitor } from '@/components/evaluation/BudgetMonitor';
import { VerdictCard } from '@/components/evaluation/VerdictCard';
import { fetchHealth, fetchDocuments, fetchEvaluationResults, runEvaluationBenchmark } from '@/lib/api';
import { EvaluationSummary, DocumentMetadata } from '@/types';
import { Play, RotateCw, ArrowLeft, Cpu, Layers } from 'lucide-react';

export default function EvaluationPage() {
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [totalChunks, setTotalChunks] = useState<number>(0);
  const [apiKey, setApiKey] = useState<string>('');
  const [isApiKeyModalOpen, setIsApiKeyModalOpen] = useState<boolean>(false);

  const [summary, setSummary] = useState<EvaluationSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRunningBenchmark, setIsRunningBenchmark] = useState<boolean>(false);
  const [selectedQid, setSelectedQid] = useState<string | null>('Q9');

  useEffect(() => {
    const savedKey = localStorage.getItem('rag_gemini_api_key');
    if (savedKey) setApiKey(savedKey);
  }, []);

  const loadData = async () => {
    try {
      const health = await fetchHealth();
      setIsBackendConnected(health.status === 'healthy');
      setTotalChunks(health.total_chunks);

      const docsRes = await fetchDocuments();
      setDocuments(docsRes.documents);

      const evalRes = await fetchEvaluationResults();
      setSummary(evalRes);
    } catch (err) {
      console.warn('Could not load evaluation summary:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRunBenchmark = async () => {
    setIsRunningBenchmark(true);
    try {
      const res = await runEvaluationBenchmark();
      setSummary(res.summary);
    } catch (err) {
      alert('Failed to execute benchmark. Ensure backend server is running.');
    } finally {
      setIsRunningBenchmark(false);
    }
  };

  const selectedAgentQ = summary?.agent_question_results.find((q) => q.question_id === selectedQid);
  const selectedWorkflowQ = summary?.workflow_question_results.find((q) => q.question_id === selectedQid);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50/60">
      <Header
        isBackendConnected={isBackendConnected}
        totalDocuments={documents.length}
        totalChunks={totalChunks}
        hasApiKey={Boolean(apiKey)}
        onOpenApiKeyModal={() => setIsApiKeyModalOpen(true)}
      />

      {/* Sub-header Navigation */}
      <div className="bg-white border-b border-slate-200 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Link
              href="/"
              className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to RAG Chat</span>
            </Link>
            <span className="text-slate-300">|</span>
            <div className="flex items-center space-x-2 text-xs font-bold text-slate-900">
              <Cpu className="w-4 h-4 text-indigo-600" />
              <span>Week 7 Module 4 Evaluation Dashboard</span>
            </div>
          </div>

          <button
            onClick={handleRunBenchmark}
            disabled={isRunningBenchmark}
            className={`inline-flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-bold text-white shadow-md transition-all ${
              isRunningBenchmark
                ? 'bg-slate-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-indigo-500/20 active:scale-[0.98]'
            }`}
          >
            {isRunningBenchmark ? (
              <>
                <RotateCw className="w-4 h-4 animate-spin" />
                <span>Running 10-Question Benchmark...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                <span>Run Full Benchmark</span>
              </>
            )}
          </button>
        </div>
      </div>

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {isLoading ? (
          <div className="py-20 text-center space-y-3">
            <RotateCw className="w-8 h-8 text-indigo-600 animate-spin mx-auto" />
            <p className="text-sm font-semibold text-slate-600">Loading benchmark evaluation metrics...</p>
          </div>
        ) : summary ? (
          <>
            {/* 1. TOP METRICS CARDS */}
            <MetricsCards agent={summary.agent} workflow={summary.workflow} />

            {/* 2. SIDE-BY-SIDE COMPARISON TABLE */}
            <ComparisonTable
              agent={summary.agent}
              workflow={summary.workflow}
              mitigationPrice={summary.mitigation_price}
              regressionMatrix={summary.regression_matrix}
            />

            {/* 3. PER-QUESTION BENCHMARK TABLE */}
            <QuestionResults
              agentResults={summary.agent_question_results || []}
              workflowResults={summary.workflow_question_results || []}
              selectedQid={selectedQid}
              onSelectQuestion={(qid) => setSelectedQid(qid)}
            />

            {/* 4. EXECUTION TRACE VISUALIZER */}
            {selectedQid && (
              <AgentTrace
                agentResult={selectedAgentQ}
                workflowResult={selectedWorkflowQ}
                questionId={selectedQid}
              />
            )}

            {/* 5. AGENT SAFETY BUDGET MONITOR */}
            <BudgetMonitor
              iterationsUsed={selectedAgentQ?.iterations || summary.agent.total_questions > 0 ? 4 : 0}
              maxIterations={8}
              tokensUsed={selectedAgentQ?.total_tokens || 2341}
              maxTokens={8000}
              costUsed={selectedAgentQ?.cost || 0.005}
              maxCost={0.05}
              wallClockUsed={selectedAgentQ ? selectedAgentQ.latency_ms / 1000 : 1.8}
              maxWallClock={15.0}
              terminationReason={selectedAgentQ?.termination_reason || 'completed'}
            />

            {/* 6. DYNAMIC FINAL VERDICT CARD */}
            <VerdictCard verdict={summary.verdict} />
          </>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl p-12 text-center space-y-4">
            <Layers className="w-12 h-12 text-slate-400 mx-auto" />
            <div>
              <h3 className="text-base font-bold text-slate-900">No Benchmark Results Available</h3>
              <p className="text-xs text-slate-500 mt-1">Click "Run Full Benchmark" to execute the 10 questions against Agent and Fixed Workflow.</p>
            </div>
            <button
              onClick={handleRunBenchmark}
              disabled={isRunningBenchmark}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-lg shadow-md transition-colors"
            >
              Run Benchmark Now
            </button>
          </div>
        )}
      </main>

      <ApiKeyModal
        isOpen={isApiKeyModalOpen}
        onClose={() => setIsApiKeyModalOpen(false)}
        currentApiKey={apiKey}
        onSaveApiKey={(key) => {
          setApiKey(key);
          if (key) localStorage.setItem('rag_gemini_api_key', key);
          else localStorage.removeItem('rag_gemini_api_key');
        }}
      />
    </div>
  );
}

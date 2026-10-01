'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { SystemExecutionResult, ComparisonMetrics } from '@/types';
import { SourceCard } from './SourceCard';
import {
  Trophy,
  Zap,
  Coins,
  Target,
  ChevronDown,
  ChevronUp,
  Cpu,
  Layers
} from 'lucide-react';

interface ComparisonCardProps {
  agentResult?: SystemExecutionResult;
  workflowResult?: SystemExecutionResult;
  comparison?: ComparisonMetrics;
}

export const ComparisonCard: React.FC<ComparisonCardProps> = ({
  agentResult,
  workflowResult,
  comparison,
}) => {
  const [activeTab, setActiveTab] = useState<'both' | 'agent' | 'workflow'>('both');
  const [showAgentTrace, setShowAgentTrace] = useState(false);
  const [showWorkflowTrace, setShowWorkflowTrace] = useState(false);

  if (!agentResult || !workflowResult || !comparison) {
    return null;
  }

  const getWinnerBadge = (type: 'latency' | 'tokens' | 'cost' | 'accuracy') => {
    let winner = 'tie';
    if (type === 'latency') winner = comparison.latency_winner;
    if (type === 'tokens') winner = comparison.tokens_winner;
    if (type === 'cost') winner = comparison.cost_winner;
    if (type === 'accuracy') winner = comparison.accuracy_winner;

    if (winner === 'tie') {
      return <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-200 text-slate-700">TIE</span>;
    }
    if (winner === 'agent') {
      return (
        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-100 text-indigo-800 border border-indigo-200">
          AGENT WIN
        </span>
      );
    }
    return (
      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-purple-100 text-purple-800 border border-purple-200">
        WORKFLOW WIN
      </span>
    );
  };

  return (
    <div className="mt-3 space-y-4 border border-indigo-200 bg-white rounded-xl shadow-xs overflow-hidden text-slate-800">
      {/* 1. TOP VERDICT BAR */}
      <div className="bg-gradient-to-r from-indigo-950 via-slate-900 to-purple-950 text-white p-3.5 px-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
        <div className="flex items-center space-x-2">
          <div className="w-7 h-7 rounded-lg bg-amber-500/20 text-amber-300 flex items-center justify-center shrink-0 border border-amber-400/30">
            <Trophy className="w-4 h-4 fill-amber-400" />
          </div>
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
              <span>Dual Execution Comparison Verdict</span>
            </div>
            <p className="text-xs font-medium text-slate-200">{comparison.summary_verdict}</p>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center bg-slate-800/80 p-1 rounded-lg border border-slate-700 text-[11px] font-medium shrink-0 self-start sm:self-center">
          <button
            onClick={() => setActiveTab('both')}
            className={`px-2.5 py-1 rounded-md transition-all ${
              activeTab === 'both' ? 'bg-indigo-600 text-white shadow-xs font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Side-by-Side
          </button>
          <button
            onClick={() => setActiveTab('agent')}
            className={`px-2.5 py-1 rounded-md transition-all ${
              activeTab === 'agent' ? 'bg-indigo-600 text-white shadow-xs font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Agent Only
          </button>
          <button
            onClick={() => setActiveTab('workflow')}
            className={`px-2.5 py-1 rounded-md transition-all ${
              activeTab === 'workflow' ? 'bg-purple-600 text-white shadow-xs font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Workflow Only
          </button>
        </div>
      </div>

      {/* 2. METRICS COMPARISON GRID */}
      <div className="px-4 grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {/* Latency */}
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Zap className="w-3 h-3 text-amber-500 fill-amber-500" />
              <span>Latency</span>
            </span>
            {getWinnerBadge('latency')}
          </div>
          <div className="mt-1.5 flex items-baseline justify-between text-xs">
            <span className="font-semibold text-indigo-700">{agentResult.latency_ms} ms</span>
            <span className="text-slate-400 text-[10px]">vs</span>
            <span className="font-semibold text-purple-700">{workflowResult.latency_ms} ms</span>
          </div>
        </div>

        {/* Tokens */}
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Coins className="w-3 h-3 text-blue-500" />
              <span>Tokens</span>
            </span>
            {getWinnerBadge('tokens')}
          </div>
          <div className="mt-1.5 flex items-baseline justify-between text-xs">
            <span className="font-semibold text-indigo-700">{agentResult.total_tokens}</span>
            <span className="text-slate-400 text-[10px]">vs</span>
            <span className="font-semibold text-purple-700">{workflowResult.total_tokens}</span>
          </div>
        </div>

        {/* Cost */}
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Coins className="w-3 h-3 text-emerald-500" />
              <span>Cost (USD)</span>
            </span>
            {getWinnerBadge('cost')}
          </div>
          <div className="mt-1.5 flex items-baseline justify-between text-xs font-mono">
            <span className="font-semibold text-indigo-700">${agentResult.cost.toFixed(5)}</span>
            <span className="text-slate-400 text-[10px]">vs</span>
            <span className="font-semibold text-purple-700">${workflowResult.cost.toFixed(5)}</span>
          </div>
        </div>

        {/* Accuracy / Completeness */}
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Target className="w-3 h-3 text-emerald-600" />
              <span>Evidence</span>
            </span>
            {getWinnerBadge('accuracy')}
          </div>
          <div className="mt-1.5 flex items-baseline justify-between text-xs font-mono">
            <span className="font-semibold text-indigo-700">{agentResult.sources.length} sources</span>
            <span className="text-slate-400 text-[10px]">vs</span>
            <span className="font-semibold text-purple-700">{workflowResult.sources.length} sources</span>
          </div>
        </div>
      </div>

      {/* 3. DUAL ANSWERS CONTENT */}
      <div className="px-4 pb-4">
        <div className={`grid gap-4 ${activeTab === 'both' ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1'}`}>
          {/* LEFT: ADAPTIVE AGENT CARD */}
          {(activeTab === 'both' || activeTab === 'agent') && (
            <div className="border border-indigo-200 rounded-xl bg-indigo-50/30 p-4 space-y-3 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-indigo-100 pb-2 mb-2">
                  <div className="flex items-center space-x-2">
                    <Cpu className="w-4 h-4 text-indigo-600" />
                    <span className="text-xs font-bold text-indigo-950">Adaptive RAG Agent</span>
                  </div>
                  <span className="text-[10px] font-semibold text-indigo-700 bg-indigo-100/80 px-2 py-0.5 rounded-full">
                    {agentResult.iterations} iteration(s)
                  </span>
                </div>

                <div className="prose prose-xs max-w-none text-xs text-slate-800 leading-relaxed">
                  <ReactMarkdown>{agentResult.answer}</ReactMarkdown>
                </div>

                {agentResult.sources && agentResult.sources.length > 0 && (
                  <div className="mt-3">
                    <SourceCard sources={agentResult.sources} />
                  </div>
                )}
              </div>

              {/* Execution Trace Expandable */}
              {agentResult.trace && agentResult.trace.length > 0 && (
                <div className="pt-2 border-t border-indigo-100/80">
                  <button
                    onClick={() => setShowAgentTrace(!showAgentTrace)}
                    className="text-[11px] font-semibold text-indigo-700 hover:text-indigo-900 flex items-center gap-1 transition-colors"
                  >
                    {showAgentTrace ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    <span>{showAgentTrace ? 'Hide Agent Execution Trace' : 'View Agent Execution Trace'}</span>
                  </button>

                  {showAgentTrace && (
                    <div className="mt-2 space-y-1.5 text-[10px] font-mono bg-white p-2.5 rounded-lg border border-indigo-100 max-h-48 overflow-y-auto">
                      {agentResult.trace.map((step, idx) => (
                        <div key={idx} className="p-1.5 rounded bg-slate-50 border border-slate-100">
                          <div className="flex justify-between text-indigo-900 font-bold">
                            <span>Step {step.step_number}: {step.action}</span>
                            <span>{step.latency_ms}ms</span>
                          </div>
                          <div className="text-slate-600 truncate">{step.input_summary}</div>
                          <div className="text-slate-500 text-[9px]">{step.result_summary}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* RIGHT: FIXED WORKFLOW CARD */}
          {(activeTab === 'both' || activeTab === 'workflow') && (
            <div className="border border-purple-200 rounded-xl bg-purple-50/30 p-4 space-y-3 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-purple-100 pb-2 mb-2">
                  <div className="flex items-center space-x-2">
                    <Layers className="w-4 h-4 text-purple-600" />
                    <span className="text-xs font-bold text-purple-950">Fixed RAG Workflow</span>
                  </div>
                  <span className="text-[10px] font-semibold text-purple-700 bg-purple-100/80 px-2 py-0.5 rounded-full">
                    Fixed 4 Steps
                  </span>
                </div>

                <div className="prose prose-xs max-w-none text-xs text-slate-800 leading-relaxed">
                  <ReactMarkdown>{workflowResult.answer}</ReactMarkdown>
                </div>

                {workflowResult.sources && workflowResult.sources.length > 0 && (
                  <div className="mt-3">
                    <SourceCard sources={workflowResult.sources} />
                  </div>
                )}
              </div>

              {/* Execution Trace Expandable */}
              {workflowResult.trace && workflowResult.trace.length > 0 && (
                <div className="pt-2 border-t border-purple-100/80">
                  <button
                    onClick={() => setShowWorkflowTrace(!showWorkflowTrace)}
                    className="text-[11px] font-semibold text-purple-700 hover:text-purple-900 flex items-center gap-1 transition-colors"
                  >
                    {showWorkflowTrace ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    <span>{showWorkflowTrace ? 'Hide Workflow Execution Trace' : 'View Workflow Execution Trace'}</span>
                  </button>

                  {showWorkflowTrace && (
                    <div className="mt-2 space-y-1.5 text-[10px] font-mono bg-white p-2.5 rounded-lg border border-purple-100 max-h-48 overflow-y-auto">
                      {workflowResult.trace.map((step, idx) => (
                        <div key={idx} className="p-1.5 rounded bg-slate-50 border border-slate-100">
                          <div className="flex justify-between text-purple-900 font-bold">
                            <span>Step {step.step_number}: {step.action}</span>
                            <span>{step.latency_ms}ms</span>
                          </div>
                          <div className="text-slate-600 truncate">{step.input_summary}</div>
                          <div className="text-slate-500 text-[9px]">{step.result_summary}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

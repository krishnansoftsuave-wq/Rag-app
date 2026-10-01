'use client';

import React from 'react';
import { QuestionResult } from '@/types';
import { ArrowDown, CheckCircle, XCircle, Wrench, Clock, Zap, DollarSign } from 'lucide-react';

interface AgentTraceProps {
  agentResult?: QuestionResult;
  workflowResult?: QuestionResult;
  questionId: string;
}

export const AgentTrace: React.FC<AgentTraceProps> = ({ agentResult, workflowResult, questionId }) => {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AGENT EXECUTION TRACE */}
        <div className="bg-slate-900 text-slate-100 rounded-xl p-5 border border-slate-800 shadow-md">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-purple-400">Adaptive Agent Execution</span>
              <h4 className="text-sm font-semibold text-slate-200 mt-0.5">{agentResult?.question || questionId}</h4>
            </div>
            {agentResult && (
              <span
                className={`px-2.5 py-1 text-xs font-bold rounded-full ${
                  agentResult.passed ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                }`}
              >
                {agentResult.passed ? 'PASSED' : 'FAILED'}
              </span>
            )}
          </div>

          {agentResult?.trace && agentResult.trace.length > 0 ? (
            <div className="space-y-3">
              {agentResult.trace.map((step, idx) => (
                <React.Fragment key={idx}>
                  <div className="bg-slate-800/80 border border-slate-700/60 rounded-lg p-3 text-xs space-y-1">
                    <div className="flex items-center justify-between font-semibold text-slate-200">
                      <div className="flex items-center space-x-2">
                        <Wrench className="w-3.5 h-3.5 text-purple-400" />
                        <span>Step {step.step_number}: <code className="text-purple-300 font-mono">{step.action}</code></span>
                      </div>
                      <span className="text-slate-400 font-mono">{step.latency_ms.toFixed(0)}ms</span>
                    </div>
                    <div className="text-slate-400 text-[11px] font-mono truncate">{step.input_summary}</div>
                    <div className="text-slate-300 text-[11px] bg-slate-950/60 p-1.5 rounded font-mono border border-slate-800">{step.result_summary}</div>
                    <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-700/40">
                      <span>Tokens: {step.total_tokens}</span>
                      <span>Cost: ${step.step_cost.toFixed(5)}</span>
                    </div>
                  </div>
                  {agentResult.trace && idx < agentResult.trace.length - 1 && (
                    <div className="flex justify-center my-1 text-slate-600">
                      <ArrowDown className="w-4 h-4" />
                    </div>
                  )}
                </React.Fragment>
              ))}

              <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                <span>Termination: <strong className="text-purple-300">{agentResult.termination_reason}</strong></span>
                <span>Total: <strong className="text-slate-200">{agentResult.total_tokens} tokens</strong> (${agentResult.cost.toFixed(5)})</span>
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-500 py-6 text-center">No trace data available for agent</div>
          )}
        </div>

        {/* FIXED WORKFLOW EXECUTION TRACE */}
        <div className="bg-slate-900 text-slate-100 rounded-xl p-5 border border-slate-800 shadow-md">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">Fixed Workflow Execution</span>
              <h4 className="text-sm font-semibold text-slate-200 mt-0.5">{workflowResult?.question || questionId}</h4>
            </div>
            {workflowResult && (
              <span
                className={`px-2.5 py-1 text-xs font-bold rounded-full ${
                  workflowResult.passed ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                }`}
              >
                {workflowResult.passed ? 'PASSED' : 'FAILED'}
              </span>
            )}
          </div>

          {workflowResult?.trace && workflowResult.trace.length > 0 ? (
            <div className="space-y-3">
              {workflowResult.trace.map((step, idx) => (
                <React.Fragment key={idx}>
                  <div className="bg-slate-800/80 border border-slate-700/60 rounded-lg p-3 text-xs space-y-1">
                    <div className="flex items-center justify-between font-semibold text-slate-200">
                      <div className="flex items-center space-x-2">
                        <Wrench className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Step {step.step_number}: <code className="text-emerald-300 font-mono">{step.action}</code></span>
                      </div>
                      <span className="text-slate-400 font-mono">{step.latency_ms.toFixed(0)}ms</span>
                    </div>
                    <div className="text-slate-400 text-[11px] font-mono truncate">{step.input_summary}</div>
                    <div className="text-slate-300 text-[11px] bg-slate-950/60 p-1.5 rounded font-mono border border-slate-800">{step.result_summary}</div>
                    <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-700/40">
                      <span>Tokens: {step.total_tokens}</span>
                      <span>Cost: ${step.step_cost.toFixed(5)}</span>
                    </div>
                  </div>
                  {workflowResult.trace && idx < workflowResult.trace.length - 1 && (
                    <div className="flex justify-center my-1 text-slate-600">
                      <ArrowDown className="w-4 h-4" />
                    </div>
                  )}
                </React.Fragment>
              ))}

              <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                <span>Sequence: <strong className="text-emerald-300">Deterministic Hardcoded</strong></span>
                <span>Total: <strong className="text-slate-200">{workflowResult.total_tokens} tokens</strong> (${workflowResult.cost.toFixed(5)})</span>
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-500 py-6 text-center">No trace data available for workflow</div>
          )}
        </div>
      </div>
    </div>
  );
};

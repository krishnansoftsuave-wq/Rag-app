'use client';

import React from 'react';
import { SystemMetrics } from '@/types';
import { CheckCircle2, Clock, Zap, DollarSign } from 'lucide-react';

interface MetricsCardsProps {
  agent: SystemMetrics;
  workflow: SystemMetrics;
}

export const MetricsCards: React.FC<MetricsCardsProps> = ({ agent, workflow }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. PASS RATE */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Pass Rate</span>
          <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <CheckCircle2 className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline justify-between">
          <div>
            <div className="text-2xl font-extrabold text-slate-900">{agent.pass_rate}%</div>
            <div className="text-xs text-slate-500 font-medium mt-0.5">Agent</div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-extrabold text-slate-700">{workflow.pass_rate}%</div>
            <div className="text-xs text-slate-500 font-medium mt-0.5">Workflow</div>
          </div>
        </div>
      </div>

      {/* 2. P50 LATENCY */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">P50 Latency</span>
          <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
            <Clock className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline justify-between">
          <div>
            <div className="text-2xl font-extrabold text-slate-900">{(agent.p50_latency_ms / 1000).toFixed(2)}s</div>
            <div className="text-xs text-slate-500 font-medium mt-0.5">Agent ({agent.p50_latency_ms.toFixed(0)}ms)</div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-extrabold text-slate-700">{(workflow.p50_latency_ms / 1000).toFixed(2)}s</div>
            <div className="text-xs text-slate-500 font-medium mt-0.5">Workflow ({workflow.p50_latency_ms.toFixed(0)}ms)</div>
          </div>
        </div>
      </div>

      {/* 3. TOTAL TOKENS */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Tokens</span>
          <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
            <Zap className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline justify-between">
          <div>
            <div className="text-2xl font-extrabold text-slate-900">{agent.total_tokens.toLocaleString()}</div>
            <div className="text-xs text-slate-500 font-medium mt-0.5">Agent</div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-extrabold text-slate-700">{workflow.total_tokens.toLocaleString()}</div>
            <div className="text-xs text-slate-500 font-medium mt-0.5">Workflow</div>
          </div>
        </div>
      </div>

      {/* 4. COST PER QUESTION */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Cost / Question</span>
          <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
            <DollarSign className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline justify-between">
          <div>
            <div className="text-2xl font-extrabold text-slate-900">${agent.cost_per_question.toFixed(4)}</div>
            <div className="text-xs text-slate-500 font-medium mt-0.5">Agent</div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-extrabold text-slate-700">${workflow.cost_per_question.toFixed(4)}</div>
            <div className="text-xs text-slate-500 font-medium mt-0.5">Workflow</div>
          </div>
        </div>
      </div>
    </div>
  );
};

'use client';

import React from 'react';
import { SystemMetrics, MitigationPrice, RegressionRow } from '@/types';
import { Trophy, ShieldCheck, AlertTriangle } from 'lucide-react';

interface ComparisonTableProps {
  agent: SystemMetrics;
  workflow: SystemMetrics;
  mitigationPrice?: MitigationPrice;
  regressionMatrix?: RegressionRow[];
}

export const ComparisonTable: React.FC<ComparisonTableProps> = ({
  agent,
  workflow,
  mitigationPrice,
  regressionMatrix,
}) => {
  const compareHigher = (val1: number, val2: number) => {
    if (val1 > val2) return 'Agent';
    if (val2 > val1) return 'Fixed Workflow';
    return 'Tie';
  };

  const compareLower = (val1: number, val2: number) => {
    if (val1 < val2) return 'Agent';
    if (val2 < val1) return 'Fixed Workflow';
    return 'Tie';
  };

  const agentGap = Math.abs(agent.outcome_vs_trajectory_gap ?? 0);
  const workflowGap = Math.abs(workflow.outcome_vs_trajectory_gap ?? 0);

  const rows = [
    {
      metric: 'Tool-Choice Accuracy',
      description: 'Correctly selected tool decisions / Total tool decisions (Higher is better)',
      agentVal: `${agent.tool_choice_accuracy ?? 100}%`,
      workflowVal: `${workflow.tool_choice_accuracy ?? 100}%`,
      better: compareHigher(agent.tool_choice_accuracy ?? 100, workflow.tool_choice_accuracy ?? 100),
    },
    {
      metric: 'Argument Validity Rate',
      description: 'Valid tool call parameters / Total tool arguments (Higher is better)',
      agentVal: `${agent.argument_validity_rate ?? 100}%`,
      workflowVal: `${workflow.argument_validity_rate ?? 100}%`,
      better: compareHigher(agent.argument_validity_rate ?? 100, workflow.argument_validity_rate ?? 100),
    },
    {
      metric: 'Step Efficiency',
      description: 'Steps taken / Minimum steps needed (Lower is better)',
      agentVal: `${agent.step_efficiency ?? 1.0}`,
      workflowVal: `${workflow.step_efficiency ?? 1.0}`,
      better: compareLower(agent.step_efficiency ?? 1.0, workflow.step_efficiency ?? 1.0),
    },
    {
      metric: 'Cost P50 (Median)',
      description: 'Median cost per question ($ USD)',
      agentVal: `$${agent.cost_p50 ?? agent.cost_per_question.toFixed(5)}`,
      workflowVal: `$${workflow.cost_p50 ?? workflow.cost_per_question.toFixed(5)}`,
      better: compareLower(agent.cost_p50 ?? agent.cost_per_question, workflow.cost_p50 ?? workflow.cost_per_question),
    },
    {
      metric: 'Cost Max (P100)',
      description: 'Maximum cost incurred on outlier test cases',
      agentVal: `$${agent.cost_max ?? agent.cost_per_question.toFixed(5)}`,
      workflowVal: `$${workflow.cost_max ?? workflow.cost_per_question.toFixed(5)}`,
      better: compareLower(agent.cost_max ?? agent.cost_per_question, workflow.cost_max ?? workflow.cost_per_question),
    },
    {
      metric: 'Outcome Pass Rate',
      description: 'Correctly answered questions / Total (10)',
      agentVal: `${agent.outcome_pass_rate ?? agent.pass_rate}%`,
      workflowVal: `${workflow.outcome_pass_rate ?? workflow.pass_rate}%`,
      better: compareHigher(agent.outcome_pass_rate ?? agent.pass_rate, workflow.outcome_pass_rate ?? workflow.pass_rate),
    },
    {
      metric: 'Trajectory Pass Rate',
      description: 'Followed valid tool trajectory sequence',
      agentVal: `${agent.trajectory_pass_rate ?? 100}%`,
      workflowVal: `${workflow.trajectory_pass_rate ?? 100}%`,
      better: compareHigher(agent.trajectory_pass_rate ?? 100, workflow.trajectory_pass_rate ?? 100),
    },
    {
      metric: 'Outcome-vs-Trajectory Gap',
      description: 'Outcome pass rate - Trajectory pass rate (0% = Perfect alignment, lower is better)',
      agentVal: `${agent.outcome_vs_trajectory_gap ?? 0}%`,
      workflowVal: `${workflow.outcome_vs_trajectory_gap ?? 0}%`,
      better: compareLower(agentGap, workflowGap),
    },
  ];

  return (
    <div className="space-y-6">
      {/* 1. WEEK 8 COMPARISON TABLE */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900">Week 8 Trajectory Metrics & Architectural Comparison</h3>
            <p className="text-xs text-slate-500 mt-0.5">Comprehensive trajectory evaluation comparing Original Agent vs Fixed Mitigated Workflow</p>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3.5 px-6">Metric</th>
                <th className="py-3.5 px-6">Original Agent</th>
                <th className="py-3.5 px-6">Fixed Agent (Mitigated)</th>
                <th className="py-3.5 px-6 text-right">Better System</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {rows.map((row, idx) => (
                <tr key={idx} className="hover:bg-slate-50/50 transition-colors">
                  <td className="py-4 px-6">
                    <div className="font-semibold text-slate-900">{row.metric}</div>
                    <div className="text-xs text-slate-400 font-normal">{row.description}</div>
                  </td>
                  <td className="py-4 px-6 text-slate-800 font-bold">{row.agentVal}</td>
                  <td className="py-4 px-6 text-slate-700 font-bold">{row.workflowVal}</td>
                  <td className="py-4 px-6 text-right">
                    <span
                      className={`inline-flex items-center space-x-1 px-3 py-1 rounded-full text-xs font-bold ${
                        row.better === 'Agent'
                          ? 'bg-indigo-100 text-indigo-700 border border-indigo-200'
                          : row.better === 'Fixed Workflow'
                          ? 'bg-purple-100 text-purple-800 border border-purple-200'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      <Trophy className="w-3.5 h-3.5 mr-1" />
                      {row.better}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 2. MITIGATION PRICE CARD */}
      {mitigationPrice && (
        <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-purple-950 text-white p-5 rounded-xl border border-indigo-200 shadow-md">
          <div className="flex items-center space-x-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-300 flex items-center justify-center border border-indigo-400/30">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold uppercase tracking-wider text-indigo-300">Mitigation Price Analysis</h4>
              <p className="text-xs text-slate-300">{mitigationPrice.mitigation_description}</p>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs pt-2 border-t border-slate-800 font-mono">
            <div className="p-3 bg-slate-800/60 rounded-lg border border-slate-700">
              <span className="text-slate-400 block text-[10px] uppercase">Latency Delta</span>
              <span className="text-indigo-300 font-bold text-sm">{mitigationPrice.latency_delta_ms} ms</span>
            </div>
            <div className="p-3 bg-slate-800/60 rounded-lg border border-slate-700">
              <span className="text-slate-400 block text-[10px] uppercase">Token Delta / Question</span>
              <span className="text-purple-300 font-bold text-sm">{mitigationPrice.token_delta_per_question} tokens</span>
            </div>
            <div className="p-3 bg-slate-800/60 rounded-lg border border-slate-700">
              <span className="text-slate-400 block text-[10px] uppercase">Cost Delta / Question</span>
              <span className="text-emerald-300 font-bold text-sm">${mitigationPrice.cost_delta_per_question}</span>
            </div>
          </div>
        </div>
      )}

      {/* 3. REGRESSION CHECK MATRIX */}
      {regressionMatrix && regressionMatrix.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                <span>Failure Mode Regression Check</span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">Failure modes detected before vs. after mitigation</p>
            </div>
          </div>
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-6">Failure Mode</th>
                <th className="py-3 px-6">Original Agent</th>
                <th className="py-3 px-6">Fixed Agent</th>
                <th className="py-3 px-6 text-right">Change</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {regressionMatrix.map((row, idx) => (
                <tr key={idx} className="hover:bg-slate-50/50">
                  <td className="py-3 px-6 font-semibold text-slate-900">{row.failure_mode}</td>
                  <td className="py-3 px-6 text-slate-800">{row.original_agent}</td>
                  <td className="py-3 px-6 text-slate-800">{row.fixed_agent}</td>
                  <td className="py-3 px-6 text-right font-mono font-bold text-slate-600">{row.change}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

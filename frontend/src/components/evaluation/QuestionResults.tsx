'use client';

import React from 'react';
import { QuestionResult } from '@/types';
import { Check, X, ChevronRight, HelpCircle } from 'lucide-react';

interface QuestionResultsProps {
  agentResults: QuestionResult[];
  workflowResults: QuestionResult[];
  selectedQid: string | null;
  onSelectQuestion: (qid: string) => void;
}

export const QuestionResults: React.FC<QuestionResultsProps> = ({
  agentResults,
  workflowResults,
  selectedQid,
  onSelectQuestion,
}) => {
  // Combine results by question_id
  const qids = Array.from(
    new Set([...agentResults.map((q) => q.question_id), ...workflowResults.map((q) => q.question_id)])
  );

  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
      <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-slate-900">Per-Question Benchmark Performance (10 Questions)</h3>
          <p className="text-xs text-slate-500 mt-0.5">Click any question row to inspect step-by-step agent & workflow execution traces</p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200 text-xs uppercase tracking-wider">
            <tr>
              <th className="py-3 px-6">ID</th>
              <th className="py-3 px-6">Question & Category</th>
              <th className="py-3 px-4 text-center">Agent Status</th>
              <th className="py-3 px-4 text-center">Workflow Status</th>
              <th className="py-3 px-4 text-right">Agent Tokens / Cost</th>
              <th className="py-3 px-4 text-right">Workflow Tokens / Cost</th>
              <th className="py-3 px-4 text-center">Trace</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-medium">
            {qids.map((qid) => {
              const ag = agentResults.find((r) => r.question_id === qid);
              const wf = workflowResults.find((r) => r.question_id === qid);
              const isSelected = selectedQid === qid;

              const questionText = ag?.question || wf?.question || qid;
              const qType = ag?.question_type || wf?.question_type || 'factual';

              return (
                <tr
                  key={qid}
                  onClick={() => onSelectQuestion(qid)}
                  className={`cursor-pointer transition-colors ${
                    isSelected ? 'bg-indigo-50/60 border-l-4 border-l-indigo-600' : 'hover:bg-slate-50/60'
                  }`}
                >
                  <td className="py-3.5 px-6 font-mono text-xs font-bold text-slate-600">{qid}</td>
                  <td className="py-3.5 px-6 max-w-md">
                    <div className="text-xs font-semibold text-slate-900 line-clamp-2">{questionText}</div>
                    <span className="inline-block mt-1 px-2 py-0.5 text-[10px] font-bold rounded bg-slate-100 text-slate-600 border border-slate-200 uppercase">
                      {qType.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    {ag ? (
                      <span
                        className={`inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold ${
                          ag.passed ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {ag.passed ? <Check className="w-3 h-3 stroke-[3]" /> : <X className="w-3 h-3 stroke-[3]" />}
                        <span>{ag.passed ? 'PASS' : 'FAIL'}</span>
                      </span>
                    ) : (
                      <span className="text-slate-400 text-xs">-</span>
                    )}
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    {wf ? (
                      <span
                        className={`inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold ${
                          wf.passed ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {wf.passed ? <Check className="w-3 h-3 stroke-[3]" /> : <X className="w-3 h-3 stroke-[3]" />}
                        <span>{wf.passed ? 'PASS' : 'FAIL'}</span>
                      </span>
                    ) : (
                      <span className="text-slate-400 text-xs">-</span>
                    )}
                  </td>
                  <td className="py-3.5 px-4 text-right font-mono text-xs text-slate-700">
                    {ag ? (
                      <div>
                        <div>{ag.total_tokens.toLocaleString()} tok</div>
                        <div className="text-[10px] text-slate-400">${ag.cost.toFixed(4)}</div>
                      </div>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td className="py-3.5 px-4 text-right font-mono text-xs text-slate-700">
                    {wf ? (
                      <div>
                        <div>{wf.total_tokens.toLocaleString()} tok</div>
                        <div className="text-[10px] text-slate-400">${wf.cost.toFixed(4)}</div>
                      </div>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    <ChevronRight className={`w-4 h-4 text-slate-400 inline-block transition-transform ${isSelected ? 'rotate-90 text-indigo-600' : ''}`} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

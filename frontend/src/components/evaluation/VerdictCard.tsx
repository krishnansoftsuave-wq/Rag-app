'use client';

import React from 'react';
import { Award, Lightbulb, CheckCircle2 } from 'lucide-react';

interface VerdictCardProps {
  verdict: string;
}

export const VerdictCard: React.FC<VerdictCardProps> = ({ verdict }) => {
  return (
    <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 text-white rounded-xl p-6 shadow-md border border-slate-700/80">
      <div className="flex items-start space-x-4">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-teal-500 to-emerald-400 text-slate-950 flex items-center justify-center shrink-0 shadow-lg shadow-teal-500/20 mt-0.5">
          <Award className="w-6 h-6" />
        </div>
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-extrabold uppercase tracking-wider text-teal-400 bg-teal-950/80 border border-teal-800/80 px-2.5 py-0.5 rounded-md">
              Empirical Conclusion
            </span>
            <h3 className="text-lg font-bold text-white">FINAL VERDICT</h3>
          </div>
          <p className="text-sm text-slate-200 leading-relaxed font-normal">
            {verdict || 'Running benchmark evaluation to compute dynamic final verdict based on empirical measurements...'}
          </p>
          <div className="pt-2 flex items-center space-x-2 text-xs text-teal-300 font-medium">
            <Lightbulb className="w-4 h-4 text-amber-400" />
            <span>Decision Rule Applied: "Does the path vary by input?"</span>
          </div>
        </div>
      </div>
    </div>
  );
};

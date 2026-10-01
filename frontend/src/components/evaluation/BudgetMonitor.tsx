'use client';

import React from 'react';
import { ShieldCheck, ShieldAlert, Activity, RefreshCw, Zap, DollarSign, Clock } from 'lucide-react';

interface BudgetMonitorProps {
  iterationsUsed?: number;
  maxIterations?: number;
  tokensUsed?: number;
  maxTokens?: number;
  costUsed?: number;
  maxCost?: number;
  wallClockUsed?: number;
  maxWallClock?: number;
  terminationReason?: string;
}

export const BudgetMonitor: React.FC<BudgetMonitorProps> = ({
  iterationsUsed = 4,
  maxIterations = 8,
  tokensUsed = 2341,
  maxTokens = 8000,
  costUsed = 0.005,
  maxCost = 0.05,
  wallClockUsed = 1.8,
  maxWallClock = 15.0,
  terminationReason = 'completed',
}) => {
  const isBudgetTerminated = terminationReason && terminationReason !== 'completed' && terminationReason !== 'running';

  const iterPct = Math.min(100, (iterationsUsed / maxIterations) * 100);
  const tokenPct = Math.min(100, (tokensUsed / maxTokens) * 100);
  const costPct = Math.min(100, (costUsed / maxCost) * 100);
  const clockPct = Math.min(100, (wallClockUsed / maxWallClock) * 100);

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-5">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">Agent Safety Budget Monitor</h3>
            <p className="text-xs text-slate-500">Real-time enforcement of the 4 strict safety limits</p>
          </div>
        </div>

        <div>
          {isBudgetTerminated ? (
            <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200">
              <ShieldAlert className="w-4 h-4 text-amber-600" />
              <span>Budget Terminated: <code className="font-mono text-amber-900">{terminationReason}</code></span>
            </span>
          ) : (
            <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Clean Execution Completed</span>
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* 1. ITERATIONS */}
        <div className="bg-slate-50 border border-slate-200/80 rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-600">
            <span className="flex items-center space-x-1.5">
              <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
              <span>Iterations</span>
            </span>
            <span className="font-mono text-slate-900">{iterationsUsed} / {maxIterations}</span>
          </div>
          <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${iterPct > 80 ? 'bg-amber-500' : 'bg-indigo-600'}`}
              style={{ width: `${iterPct}%` }}
            />
          </div>
        </div>

        {/* 2. TOKENS */}
        <div className="bg-slate-50 border border-slate-200/80 rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-600">
            <span className="flex items-center space-x-1.5">
              <Zap className="w-3.5 h-3.5 text-slate-500" />
              <span>Tokens</span>
            </span>
            <span className="font-mono text-slate-900">{tokensUsed.toLocaleString()} / {maxTokens.toLocaleString()}</span>
          </div>
          <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${tokenPct > 80 ? 'bg-amber-500' : 'bg-indigo-600'}`}
              style={{ width: `${tokenPct}%` }}
            />
          </div>
        </div>

        {/* 3. COST */}
        <div className="bg-slate-50 border border-slate-200/80 rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-600">
            <span className="flex items-center space-x-1.5">
              <DollarSign className="w-3.5 h-3.5 text-slate-500" />
              <span>Cost Limit</span>
            </span>
            <span className="font-mono text-slate-900">${costUsed.toFixed(4)} / ${maxCost.toFixed(2)}</span>
          </div>
          <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${costPct > 80 ? 'bg-amber-500' : 'bg-indigo-600'}`}
              style={{ width: `${costPct}%` }}
            />
          </div>
        </div>

        {/* 4. WALL CLOCK */}
        <div className="bg-slate-50 border border-slate-200/80 rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-600">
            <span className="flex items-center space-x-1.5">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              <span>Wall Clock</span>
            </span>
            <span className="font-mono text-slate-900">{wallClockUsed.toFixed(1)}s / {maxWallClock.toFixed(0)}s</span>
          </div>
          <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${clockPct > 80 ? 'bg-amber-500' : 'bg-indigo-600'}`}
              style={{ width: `${clockPct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

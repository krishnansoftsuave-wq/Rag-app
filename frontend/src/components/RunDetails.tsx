'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronUp, CircleCheck, CircleX, User, Users } from 'lucide-react';
import { AgentStepTrace, ChatMessage } from '@/types';

const formatTokens = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}K` : `${n}`);
const formatCost = (usd: number) => `$${usd.toFixed(4)}`;
const formatSeconds = (ms: number) => `${(ms / 1000).toFixed(1)}s`;
const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** How an answer was produced: who answered (single agent or team) with the measured LLM calls, tokens, cost and
 * time. Expands into the team's plan and each specialist's findings, or the single agent's steps. */
export const RunDetails: React.FC<{ message: ChatMessage }> = ({ message }) => {
  const [isOpen, setIsOpen] = useState(false);
  const result = message.team_result || message.agent_result;
  if (!result) return null;

  const isTeam = Boolean(message.team_result);
  const Icon = isTeam ? Users : User;
  const stats = [
    result.llm_calls ? `${result.llm_calls} LLM calls` : null,
    `${formatTokens(result.total_tokens)} tokens`,
    formatCost(result.cost),
    formatSeconds(result.latency_ms),
  ].filter(Boolean);

  return (
    <div className="mt-3">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50 transition-colors"
      >
        <Icon className={`w-3.5 h-3.5 ${isTeam ? 'text-indigo-600' : 'text-zinc-500'}`} />
        <span className="font-medium">{isTeam ? 'Team' : 'Single agent'}</span>
        <span className="text-zinc-400 truncate max-w-[260px]">· {stats.join(' · ')}</span>
        {isOpen ? <ChevronUp className="w-3.5 h-3.5 text-zinc-400" /> : <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />}
      </button>

      {isOpen && (
        <div className="mt-2 rounded-xl border border-zinc-200 bg-zinc-50/60 p-3 text-xs text-zinc-700 space-y-3">
          {isTeam ? <TeamSteps trace={result.trace} /> : <AgentSteps trace={result.trace} />}
          {result.models && result.models.length > 0 && (
            <p className="text-zinc-400 border-t border-zinc-200 pt-2">
              Model{result.models.length > 1 ? 's' : ''}: {result.models.join(', ')}
              {result.models.length > 1 && ' (a call fell back to another model)'}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

const StepHeader: React.FC<{ title: string; step: AgentStepTrace }> = ({ title, step }) => (
  <p className="flex items-center justify-between gap-2">
    <span className="font-semibold text-zinc-800">{title}</span>
    <span className="text-zinc-400 shrink-0">
      {formatTokens(step.total_tokens)} tokens · {formatSeconds(step.latency_ms)}
    </span>
  </p>
);

/** The team's run: the manager's plan, what each specialist found, then the manager's answer. */
const TeamSteps: React.FC<{ trace: AgentStepTrace[] }> = ({ trace }) => {
  const plan = trace.find((s) => s.action === 'manager_plan');
  const tasks = trace.filter((s) => s.action.startsWith('a2a_task:'));
  const synthesis = trace.find((s) => s.action === 'manager_synthesize');
  const subTasks: { to: string; ask: string }[] = plan?.details?.sub_tasks || [];

  return (
    <>
      {plan && (
        <section>
          <StepHeader title="1. The manager splits the question" step={plan} />
          <ul className="mt-1.5 space-y-1">
            {subTasks.map((st) => (
              <li key={st.to}>
                <span className="font-medium text-indigo-700">{capitalize(st.to)}</span>
                <span className="text-zinc-400"> ← </span>
                {st.ask}
              </li>
            ))}
          </ul>
          {plan.details?.fallback_plan && (
            <p className="mt-1 text-amber-700">The plan was unusable, so every specialist got the whole question.</p>
          )}
        </section>
      )}

      {tasks.length > 0 && (
        <section>
          <p className="font-semibold text-zinc-800">2. The specialists search in parallel</p>
          <div className={`mt-1.5 grid gap-2 ${tasks.length > 1 ? 'sm:grid-cols-2' : ''}`}>
            {tasks.map((step) => (
              <SpecialistCard key={step.action} step={step} />
            ))}
          </div>
        </section>
      )}

      {synthesis && (
        <section>
          <StepHeader title="3. The manager writes the answer from their findings" step={synthesis} />
        </section>
      )}
    </>
  );
};

const SpecialistCard: React.FC<{ step: AgentStepTrace }> = ({ step }) => {
  const name = capitalize(step.action.split(':')[1] || 'specialist');
  const report = step.details?.findings || {};
  const findings: { fact: string; source?: string }[] = report.findings || [];
  const notFound: string[] = report.not_found || [];
  const status = step.details?.task?.status || {};
  const failed = status.state === 'failed';

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-2.5 min-w-0">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-zinc-800 flex items-center gap-1.5">
          {failed ? <CircleX className="w-3.5 h-3.5 text-rose-500" /> : <CircleCheck className="w-3.5 h-3.5 text-emerald-500" />}
          {name}
        </span>
        <span className="text-zinc-400 shrink-0">
          {report.searches ?? 0} search{report.searches === 1 ? '' : 'es'} · {formatTokens(step.total_tokens)} tokens
        </span>
      </div>
      {failed ? (
        <p className="mt-1.5 text-rose-700 break-words">{status.message}</p>
      ) : (
        <ul className="mt-1.5 list-disc pl-4 space-y-0.5 text-zinc-600">
          {findings.map((f, i) => (
            <li key={i} className="break-words">
              {f.fact}
              {f.source && <span className="text-zinc-400"> [{f.source}]</span>}
            </li>
          ))}
        </ul>
      )}
      {notFound.length > 0 && <p className="mt-1.5 text-zinc-500 break-words">Not found: {notFound.join('; ')}</p>}
    </div>
  );
};

const stepName = (action: string) =>
  action.replace(/^tool_call:/, '').replace(/^mcp_call:/, 'MCP tool: ').replace(/_/g, ' ');

/** The single agent's steps in order. Per-step tokens are left out: its own step counters are estimates (the total
 * above is measured). */
const AgentSteps: React.FC<{ trace: AgentStepTrace[] }> = ({ trace }) => (
  <ol className="space-y-1">
    {trace.map((step) => (
      <li key={step.step_number} className="flex items-start justify-between gap-3">
        <span className="min-w-0 break-words">
          <span className="text-zinc-400">{step.step_number}.</span> {stepName(step.action)}
          {step.raw_args?.query && <span className="text-zinc-400"> “{step.raw_args.query}”</span>}
        </span>
        <span className="text-zinc-400 shrink-0">{formatSeconds(step.latency_ms)}</span>
      </li>
    ))}
  </ol>
);

'use client';

import React from 'react';
import { AlertTriangle, Wrench } from 'lucide-react';
import { McpToolResult, isArtifact } from '@/types';
import { ArtifactCard } from './ArtifactCard';
import { MarkdownMessage } from './MarkdownMessage';

interface McpResultsProps {
  results: McpToolResult[];
}

/** Results of MCP tools the backend agent chose to call for this question: artifacts as cards, other tools as raw output. */
export const McpResults: React.FC<McpResultsProps> = ({ results }) => (
  <>
    {results.map((r, i) => {
      if (!r.success) {
        return (
          <div key={i} className="mt-3 flex items-start gap-2 text-[11px] text-slate-600 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
            <span>
              Could not run <span className="font-mono">{r.tool_name}</span> on {r.server_name}: {r.error || 'unknown error'}
            </span>
          </div>
        );
      }
      if (isArtifact(r.result)) {
        return <ArtifactCard key={i} artifact={r.result} serverName={r.server_name} />;
      }
      return (
        <details key={i} className="mt-3 bg-white border border-slate-200 rounded-xl px-3 py-2 text-[11px]">
          <summary className="cursor-pointer flex items-center gap-1.5 font-semibold text-slate-700">
            <Wrench className="w-3.5 h-3.5 text-indigo-500" />
            Result from <span className="font-mono">{r.tool_name}</span>
            <span className="font-normal text-slate-400">· via {r.server_name}</span>
          </summary>
          <div className="mt-2 text-slate-700">
            {typeof r.result === 'string' ? (
              <MarkdownMessage>{r.result}</MarkdownMessage>
            ) : (
              <pre className="bg-slate-50 border border-slate-100 rounded-lg p-2 overflow-x-auto font-mono text-[10px]">
                {JSON.stringify(r.result, null, 2)}
              </pre>
            )}
          </div>
        </details>
      );
    })}
  </>
);

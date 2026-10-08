'use client';

import React, { useState } from 'react';
import { FileText, ChevronDown, ChevronUp } from 'lucide-react';
import { SourceCitation } from '@/types';

interface SourceCardProps {
  sources: SourceCitation[];
}

/** The passages an answer was built from: a "Sources" pill that expands into the retrieved chunks. */
export const SourceCard: React.FC<SourceCardProps> = ({ sources }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!sources || sources.length === 0) return null;
  const files = Array.from(new Set(sources.map((s) => s.filename)));

  return (
    <div className="mt-3">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50 transition-colors"
      >
        <FileText className="w-3.5 h-3.5 text-zinc-500" />
        <span className="font-medium">
          {sources.length} source{sources.length === 1 ? '' : 's'}
        </span>
        <span className="text-zinc-400 truncate max-w-[220px]">· {files.join(', ')}</span>
        {isOpen ? <ChevronUp className="w-3.5 h-3.5 text-zinc-400" /> : <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />}
      </button>

      {isOpen && (
        <div className="mt-2 space-y-2">
          {sources.map((source, index) => (
            <div
              key={`${source.doc_id}_${source.chunk_index}_${index}`}
              className="rounded-xl border border-zinc-200 bg-zinc-50/60 p-3 space-y-1.5"
            >
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="font-medium text-zinc-800 flex items-center gap-1.5 min-w-0">
                  <span className="w-5 h-5 rounded-full bg-zinc-200 text-zinc-700 font-semibold inline-flex items-center justify-center text-[10px] shrink-0">
                    {index + 1}
                  </span>
                  <span className="truncate">{source.filename}</span>
                  <span className="text-zinc-400 font-normal shrink-0">· chunk {source.chunk_index}</span>
                </span>
                <span className="text-zinc-500 font-mono shrink-0">{Math.round(source.score * 100)}%</span>
              </div>
              <p className="text-zinc-600 text-xs leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
                {source.content}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

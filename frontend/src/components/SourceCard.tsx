'use client';

import React, { useState } from 'react';
import { FileText, ChevronDown, ChevronUp, ExternalLink, Percent } from 'lucide-react';
import { SourceCitation } from '@/types';

interface SourceCardProps {
  sources: SourceCitation[];
}

export const SourceCard: React.FC<SourceCardProps> = ({ sources }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3 border border-emerald-200/80 bg-emerald-50/30 rounded-xl overflow-hidden text-xs">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3.5 py-2.5 flex items-center justify-between hover:bg-emerald-50/60 transition-colors text-slate-700 font-medium"
      >
        <div className="flex items-center space-x-2">
          <FileText className="w-3.5 h-3.5 text-emerald-600" />
          <span>Retrieved Context ({sources.length} sources)</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-[11px] text-emerald-700 bg-emerald-100/80 px-2 py-0.5 rounded-full font-semibold">
            Top match: {Math.round(sources[0].score * 100)}% match
          </span>
          {isOpen ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </button>

      {isOpen && (
        <div className="px-3.5 pb-3.5 pt-1 space-y-2.5 border-t border-emerald-100">
          {sources.map((source, index) => (
            <div
              key={`${source.doc_id}_${source.chunk_index}_${index}`}
              className="bg-white p-3 rounded-lg border border-slate-200 shadow-2xs space-y-1.5"
            >
              <div className="flex items-center justify-between text-[11px]">
                <span className="font-semibold text-slate-800 flex items-center gap-1">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 font-bold inline-flex items-center justify-center text-[10px]">
                    {index + 1}
                  </span>
                  {source.filename}
                  <span className="text-slate-400 font-normal">
                    (Chunk #{source.chunk_index})
                  </span>
                </span>
                <span className="text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded font-mono font-medium">
                  {Math.round(source.score * 100)}% score
                </span>
              </div>
              <p className="text-slate-600 bg-slate-50 p-2 rounded font-mono text-[11px] leading-relaxed whitespace-pre-wrap border border-slate-100">
                {source.content}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

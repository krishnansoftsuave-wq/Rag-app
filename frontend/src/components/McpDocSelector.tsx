'use client';

import React, { useState } from 'react';
import { DocumentMetadata } from '@/types';
import { callMcpTool } from '@/lib/api';

interface McpDocSelectorProps {
  documents: DocumentMetadata[];
  selectedDocId: string | null;
  onSelectDoc: (docId: string | null) => void;
  onRefreshDocs: () => void;
}

export const McpDocSelector: React.FC<McpDocSelectorProps> = ({
  documents,
  selectedDocId,
  onSelectDoc,
  onRefreshDocs,
}) => {
  const [summarizingId, setSummarizingId] = useState<string | null>(null);
  const [summaryText, setSummaryText] = useState<string | null>(null);

  const handleSummarize = async (docId: string) => {
    setSummarizingId(docId);
    setSummaryText(null);
    try {
      const res = await callMcpTool('summarize_document', { doc_id: docId });
      if (res.success) {
        setSummaryText(res.summary);
      } else {
        setSummaryText(`Error: ${res.error}`);
      }
    } catch (err: any) {
      setSummaryText(`Failed to generate summary: ${err.message}`);
    } finally {
      setSummarizingId(null);
    }
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <span className="text-cyan-400 text-lg font-bold">📄 My Documents & MCP Tools</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-cyan-950 text-cyan-400 border border-cyan-800">
            {documents.length} Available
          </span>
        </div>
        {selectedDocId && (
          <button
            onClick={() => onSelectDoc(null)}
            className="text-xs text-slate-400 hover:text-cyan-400 underline"
          >
            Clear Document Scope (Search All)
          </button>
        )}
      </div>

      {documents.length === 0 ? (
        <p className="text-xs text-slate-500 py-2">No documents uploaded yet. Upload a document to start querying or summarizing!</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {documents.map((doc) => {
            const isSelected = selectedDocId === doc.doc_id;
            return (
              <div
                key={doc.doc_id}
                className={`p-3 rounded-lg border text-xs transition-all ${
                  isSelected
                    ? 'bg-cyan-950/40 border-cyan-500/80 shadow-lg shadow-cyan-500/10'
                    : 'bg-slate-850 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="truncate font-semibold text-slate-200" title={doc.filename}>
                    {doc.filename}
                  </div>
                  {isSelected && (
                    <span className="px-1.5 py-0.5 rounded bg-cyan-500 text-slate-950 font-bold text-[9px]">
                      ACTIVE TARGET
                    </span>
                  )}
                </div>

                <div className="text-[11px] text-slate-400 mt-1 flex items-center justify-between">
                  <span>{doc.total_chunks} chunks</span>
                  <span className="capitalize text-slate-500">{doc.chunking_strategy}</span>
                </div>

                <div className="mt-3 flex items-center space-x-2">
                  <button
                    onClick={() => onSelectDoc(isSelected ? null : doc.doc_id)}
                    className={`flex-1 py-1 px-2 rounded text-[11px] font-semibold transition-all ${
                      isSelected
                        ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                        : 'bg-cyan-600/20 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-600/30'
                    }`}
                  >
                    {isSelected ? 'Deselect' : '🎯 Target this Doc'}
                  </button>

                  <button
                    onClick={() => handleSummarize(doc.doc_id)}
                    disabled={summarizingId === doc.doc_id}
                    className="py-1 px-2 rounded bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-600/30 text-[11px] font-semibold disabled:opacity-50"
                  >
                    {summarizingId === doc.doc_id ? 'Summarizing...' : '⚡ MCP Summary'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Summary Modal / View */}
      {summaryText && (
        <div className="mt-4 p-4 rounded-xl bg-slate-950 border border-indigo-500/30 text-xs text-slate-200">
          <div className="flex items-center justify-between mb-2">
            <span className="font-bold text-indigo-400 text-sm">⚡ Executive Document Summary (Generated via MCP Tool)</span>
            <button onClick={() => setSummaryText(null)} className="text-slate-400 hover:text-white">✕</button>
          </div>
          <div className="whitespace-pre-wrap font-sans text-slate-300 leading-relaxed max-h-60 overflow-y-auto">
            {summaryText}
          </div>
        </div>
      )}
    </div>
  );
};

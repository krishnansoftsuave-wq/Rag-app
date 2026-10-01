'use client';

import React, { useState } from 'react';
import { FileText, Trash2, Layers, HardDrive, CheckSquare, Square, Filter } from 'lucide-react';
import { DocumentMetadata } from '@/types';

interface DocumentListProps {
  documents: DocumentMetadata[];
  selectedDocIds: string[];
  onToggleSelectDoc: (docId: string) => void;
  onDeleteDoc: (docId: string) => void;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  selectedDocIds,
  onToggleSelectDoc,
  onDeleteDoc,
}) => {
  const [strategyFilter, setStrategyFilter] = useState<string>('all');

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const renderStrategyBadge = (strategy?: string) => {
    const s = (strategy || 'standard').toLowerCase();
    if (s === 'agentic') {
      return (
        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 shrink-0">
          Agentic (LLM)
        </span>
      );
    }
    if (s === 'semantic') {
      return (
        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 shrink-0">
          Semantic
        </span>
      );
    }
    if (s === 'late') {
      return (
        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 shrink-0">
          Late Chunk
        </span>
      );
    }
    return (
      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 shrink-0">
        Standard
      </span>
    );
  };

  const filteredDocuments = documents.filter((doc) => {
    if (strategyFilter === 'all') return true;
    const docStrat = (doc.chunking_strategy || 'standard').toLowerCase();
    return docStrat === strategyFilter.toLowerCase();
  });

  return (
    <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col h-full space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-100">
        <h2 className="text-sm font-bold text-slate-800 flex items-center gap-2">
          <FileText className="w-4 h-4 text-emerald-600" />
          Indexed Documents
          <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-semibold">
            {filteredDocuments.length} / {documents.length}
          </span>
        </h2>

        {/* Filter by Chunking Strategy */}
        <div className="flex items-center gap-1.5">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <select
            value={strategyFilter}
            onChange={(e) => setStrategyFilter(e.target.value)}
            className="text-[11px] font-medium bg-slate-50 text-slate-700 border border-slate-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
          >
            <option value="all">All Strategies</option>
            <option value="standard">Standard</option>
            <option value="semantic">Semantic</option>
            <option value="agentic">Agentic (LLM)</option>
            <option value="late">Late Chunking</option>
          </select>
        </div>
      </div>


      {selectedDocIds.length > 0 && (
        <div className="text-[11px] text-emerald-700 font-medium bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-100 flex items-center justify-between">
          <span>Filtering chat query to {selectedDocIds.length} selected doc(s)</span>
        </div>
      )}

      {filteredDocuments.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-400">
          <FileText className="w-10 h-10 stroke-1 mb-2 text-slate-300" />
          <p className="text-xs font-medium text-slate-500">
            {documents.length === 0 ? 'No documents uploaded yet' : `No documents match strategy '${strategyFilter}'`}
          </p>
          <p className="text-[11px] text-slate-400 mt-1">
            {documents.length === 0
              ? 'Upload files above to build your vector knowledge base.'
              : 'Try changing the strategy filter above.'}
          </p>
        </div>
      ) : (
        <div className="space-y-2 overflow-y-auto max-h-[380px] pr-1">
          {filteredDocuments.map((doc) => {
            const isSelected = selectedDocIds.includes(doc.doc_id);
            return (
              <div
                key={doc.doc_id}
                className={`group flex items-center justify-between p-3 rounded-xl border transition-all ${
                  isSelected
                    ? 'border-emerald-300 bg-emerald-50/40 shadow-sm'
                    : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                <div
                  onClick={() => onToggleSelectDoc(doc.doc_id)}
                  className="flex items-start space-x-3 cursor-pointer flex-1 min-w-0"
                >
                  <button className="mt-0.5 text-slate-400 hover:text-emerald-600">
                    {isSelected ? (
                      <CheckSquare className="w-4 h-4 text-emerald-600 fill-emerald-100" />
                    ) : (
                      <Square className="w-4 h-4 text-slate-300" />
                    )}
                  </button>
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-center justify-between gap-2 pr-2">
                      <p className="text-xs font-semibold text-slate-800 truncate" title={doc.filename}>
                        {doc.filename}
                      </p>
                      {renderStrategyBadge(doc.chunking_strategy)}
                    </div>
                    <div className="flex items-center space-x-3 text-[11px] text-slate-400">
                      <span className="flex items-center gap-1">
                        <Layers className="w-3 h-3" />
                        {doc.total_chunks} chunks
                      </span>
                      <span className="flex items-center gap-1">
                        <HardDrive className="w-3 h-3" />
                        {formatFileSize(doc.file_size)}
                      </span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(`Remove "${doc.filename}" and its vector embeddings?`)) {
                      onDeleteDoc(doc.doc_id);
                    }
                  }}
                  className="p-1.5 text-slate-300 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                  title="Delete Document"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};


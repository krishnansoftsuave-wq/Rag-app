'use client';

import React, { useState, useRef } from 'react';
import { UploadCloud, File, Loader2, CheckCircle2, AlertCircle, Sparkles, Layers, Cpu, Brain, Bot } from 'lucide-react';
import { uploadDocument } from '@/lib/api';
import { DocumentMetadata } from '@/types';

interface DocumentUploadProps {
  onUploadSuccess: (document: DocumentMetadata) => void;
}

export type ChunkingStrategyOption = 'standard' | 'semantic' | 'agentic' | 'late';

export const DocumentUpload: React.FC<DocumentUploadProps> = ({ onUploadSuccess }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [chunkingStrategy] = useState<ChunkingStrategyOption>('agentic');
  const [uploadMessage, setUploadMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const getStrategyLabel = (strategy: ChunkingStrategyOption) => {
    switch (strategy) {
      case 'agentic':
        return 'Agentic / LLM-Based Chunking';
      case 'semantic':
        return 'Semantic (Embedding-Based) Chunking';
      case 'late':
        return 'Late Chunking (Contextual Span Pooling)';
      case 'standard':
      default:
        return 'Standard (Recursive Character Chunking)';
    }
  };

  const getStrategyBadgeText = (strategy: ChunkingStrategyOption) => {
    switch (strategy) {
      case 'agentic':
        return 'LLM Reasoning';
      case 'semantic':
        return 'Sentence Embeddings';
      case 'late':
        return 'Contextual Span Pooling';
      case 'standard':
      default:
        return 'Recursive Delimiters';
    }
  };

  const getStrategyDescription = (strategy: ChunkingStrategyOption) => {
    switch (strategy) {
      case 'agentic':
        return 'Uses LLM proposition reasoning to detect high-level semantic topic transitions and form optimal chunks.';
      case 'semantic':
        return 'Groups text dynamically by sentence embedding distance thresholds to preserve semantic concepts.';
      case 'late':
        return 'Passes entire document through Transformer encoder first, then mean-pools token representations across chunk spans.';
      case 'standard':
      default:
        return 'Splits text recursively using paragraphs, sentences, and character delimiters with fixed window size and overlap.';
    }
  };

  const handleFileChange = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    const file = files[0];
    setIsUploading(true);
    setUploadMessage(null);

    try {
      const res = await uploadDocument(file, chunkingStrategy);
      onUploadSuccess(res.document);
      setUploadMessage({
        text: `Indexed "${file.name}" into ${res.document.total_chunks} chunks using ${getStrategyLabel(chunkingStrategy)}!`,
        type: 'success',
      });
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err: any) {
      setUploadMessage({
        text: err.message || 'Failed to process document',
        type: 'error',
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileChange(e.dataTransfer.files);
  };

  return (
    <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-slate-800 flex items-center gap-2">
          <UploadCloud className="w-4 h-4 text-emerald-600" />
          Upload Knowledge Document
        </h2>
        <span className="text-[11px] font-medium text-slate-400">
          PDF, DOCX, TXT, MD
        </span>
      </div>

      {/* Automatic Agentic Chunking Info Badge */}
      <div className="bg-gradient-to-r from-emerald-50 to-indigo-50 border border-emerald-200/80 rounded-xl p-3 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="w-7 h-7 rounded-lg bg-emerald-600 text-white flex items-center justify-center font-bold">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
              Smart LLM Proposition Chunking
            </span>
            <p className="text-[11px] text-slate-500 leading-tight">
              Automatic semantic boundary detection & dynamic vector indexing
            </p>
          </div>
        </div>
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 shrink-0">
          Agentic AI
        </span>
      </div>




      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
          isDragging
            ? 'border-emerald-500 bg-emerald-50/50 scale-[0.99]'
            : 'border-slate-200 hover:border-emerald-400 hover:bg-slate-50/80'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt,.md,.csv,.json"
          className="hidden"
          onChange={(e) => handleFileChange(e.target.files)}
          disabled={isUploading}
        />

        {isUploading ? (
          <div className="flex flex-col items-center justify-center space-y-2 py-2">
            <Loader2 className="w-8 h-8 text-emerald-600 animate-spin" />
            <p className="text-xs font-semibold text-slate-700">
              Parsing document & indexing vectors...
            </p>
            <p className="text-[11px] text-slate-400">
              Applying {getStrategyLabel(chunkingStrategy)}
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center space-y-2">
            <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <File className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-700">
                Click or drag & drop file here
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Up to 25MB per document
              </p>
            </div>
          </div>
        )}
      </div>

      {uploadMessage && (
        <div
          className={`flex items-start gap-2 p-2.5 rounded-lg text-xs ${
            uploadMessage.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
              : 'bg-rose-50 text-rose-800 border border-rose-200'
          }`}
        >
          {uploadMessage.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          )}
          <span>{uploadMessage.text}</span>
        </div>
      )}
    </div>
  );
};


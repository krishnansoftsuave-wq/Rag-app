'use client';

import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, Trash2, Check, Loader2, AlertCircle, Search, X, Layers, HardDrive, Library } from 'lucide-react';
import { uploadDocument } from '@/lib/api';
import { DocumentMetadata } from '@/types';

interface DocumentLibraryProps {
  open: boolean;
  placement: 'top' | 'bottom'; // above or below the composer it belongs to
  documents: DocumentMetadata[];
  selectedDocId: string | null;
  onSelectDoc: (docId: string | null) => void;
  onUploadSuccess: (document: DocumentMetadata) => void;
  onDeleteDoc: (docId: string) => void;
  onClose: () => void;
}

const SEARCH_THRESHOLD = 5; // show the filter box once the library has more documents than this

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

/**
 * The user's uploaded documents, opened from the chat input: pick one to ask about, go back to searching
 * all of them, or upload a new one (which is then picked). Stays mounted while closed so an upload in
 * progress keeps running.
 */
export const DocumentLibrary: React.FC<DocumentLibraryProps> = ({
  open,
  placement,
  documents,
  selectedDocId,
  onSelectDoc,
  onUploadSuccess,
  onDeleteDoc,
  onClose,
}) => {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadingName, setUploadingName] = useState('');
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [filter, setFilter] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0 || isUploading) return;
    const file = files[0];
    setIsUploading(true);
    setUploadingName(file.name);
    setUploadError(null);
    try {
      const res = await uploadDocument(file);
      onUploadSuccess(res.document);
      onSelectDoc(res.document.doc_id);
      onClose();
    } catch (err: any) {
      setUploadError(err.message || 'Failed to process document');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const pick = (docId: string | null) => {
    onSelectDoc(docId);
    onClose();
  };

  const visibleDocs = documents.filter((d) => d.filename.toLowerCase().includes(filter.trim().toLowerCase()));

  return (
    <div
      className={`absolute left-0 w-full sm:w-[400px] bg-white border border-zinc-200 rounded-2xl shadow-2xl shadow-zinc-900/15 z-20 flex flex-col max-h-[min(460px,60vh)] ${
        placement === 'top' ? 'bottom-full mb-2' : 'top-full mt-2'
      } ${open ? '' : 'hidden'}`}
    >
      {/* Title */}
      <div className="px-4 pt-3.5 pb-2.5 flex items-start justify-between border-b border-zinc-100">
        <div>
          <h3 className="text-sm font-bold text-zinc-800 flex items-center gap-2">
            <Library className="w-4 h-4 text-indigo-600" />
            Your documents
            <span className="text-[11px] bg-zinc-100 text-zinc-600 px-2 py-0.5 rounded-full font-semibold">
              {documents.length}
            </span>
          </h3>
          <p className="text-[11px] text-zinc-500 mt-0.5">Stored in your library. Pick one to ask about, or upload a new one.</p>
        </div>
        <button onClick={onClose} className="p-1 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-100" title="Close">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Upload */}
      <div className="p-3 border-b border-zinc-100">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            handleFiles(e.dataTransfer.files);
          }}
          onClick={() => !isUploading && fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl px-3 py-3 flex items-center gap-3 transition-all ${
            isUploading
              ? 'border-indigo-300 bg-indigo-50/60 cursor-wait'
              : isDragging
              ? 'border-indigo-500 bg-indigo-50 cursor-copy'
              : 'border-zinc-200 hover:border-indigo-400 hover:bg-zinc-50 cursor-pointer'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.doc,.txt,.md,.csv,.json"
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
            disabled={isUploading}
          />
          <div className="w-9 h-9 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center shrink-0">
            {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
          </div>
          {isUploading ? (
            <div className="min-w-0">
              <p className="text-xs font-semibold text-zinc-700 truncate">Indexing {uploadingName}...</p>
              <p className="text-[11px] text-zinc-500">Smart LLM chunking & vector indexing</p>
            </div>
          ) : (
            <div>
              <p className="text-xs font-semibold text-zinc-700">Upload a new document</p>
              <p className="text-[11px] text-zinc-500">Click or drop a file · PDF, DOCX, TXT, MD · up to 25MB</p>
            </div>
          )}
        </div>
        {uploadError && (
          <div className="mt-2 flex items-start gap-2 p-2 rounded-lg text-[11px] bg-rose-50 text-rose-800 border border-rose-200">
            <AlertCircle className="w-3.5 h-3.5 text-rose-600 shrink-0 mt-0.5" />
            <span>{uploadError}</span>
          </div>
        )}
      </div>

      {/* Library */}
      {documents.length > SEARCH_THRESHOLD && (
        <div className="px-3 pt-3">
          <div className="flex items-center gap-2 bg-zinc-50 border border-zinc-200 rounded-lg px-2.5 py-1.5 focus-within:border-indigo-400">
            <Search className="w-3.5 h-3.5 text-zinc-400" />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Find a document..."
              className="flex-1 bg-transparent text-xs text-zinc-800 placeholder:text-zinc-400 focus:outline-none"
            />
          </div>
        </div>
      )}

      <div className="p-2 overflow-y-auto flex-1 space-y-1">
        {documents.length > 0 && (
          <button
            onClick={() => pick(null)}
            className={`w-full flex items-center gap-3 px-2.5 py-2 rounded-xl text-left transition-colors ${
              selectedDocId === null ? 'bg-indigo-50 border border-indigo-200' : 'border border-transparent hover:bg-zinc-50'
            }`}
          >
            <div className="w-8 h-8 rounded-lg bg-zinc-100 text-zinc-500 flex items-center justify-center shrink-0">
              <Layers className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-zinc-800">All documents</p>
              <p className="text-[11px] text-zinc-500">Search across your whole library</p>
            </div>
            {selectedDocId === null && <Check className="w-4 h-4 text-indigo-600 shrink-0" />}
          </button>
        )}

        {visibleDocs.map((doc) => {
          const isSelected = doc.doc_id === selectedDocId;
          return (
            <div
              key={doc.doc_id}
              onClick={() => pick(doc.doc_id)}
              className={`group w-full flex items-center gap-3 px-2.5 py-2 rounded-xl cursor-pointer transition-colors ${
                isSelected ? 'bg-indigo-50 border border-indigo-200' : 'border border-transparent hover:bg-zinc-50'
              }`}
            >
              <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
                <FileText className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-zinc-800 truncate" title={doc.filename}>
                  {doc.filename}
                </p>
                <p className="text-[11px] text-zinc-500 flex items-center gap-2">
                  <span className="flex items-center gap-1">
                    <Layers className="w-3 h-3" />
                    {doc.total_chunks} chunks
                  </span>
                  <span className="flex items-center gap-1">
                    <HardDrive className="w-3 h-3" />
                    {formatFileSize(doc.file_size)}
                  </span>
                </p>
              </div>
              {isSelected && <Check className="w-4 h-4 text-indigo-600 shrink-0" />}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`Remove "${doc.filename}" and its vector embeddings?`)) {
                    onDeleteDoc(doc.doc_id);
                  }
                }}
                className="p-1.5 text-zinc-300 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                title="Delete document"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}

        {documents.length === 0 && (
          <div className="py-6 text-center">
            <FileText className="w-8 h-8 mx-auto stroke-1 text-zinc-300" />
            <p className="text-xs font-medium text-zinc-500 mt-1">No documents yet</p>
            <p className="text-[11px] text-zinc-400">Upload one above to start asking questions.</p>
          </div>
        )}
        {documents.length > 0 && visibleDocs.length === 0 && (
          <p className="py-4 text-center text-[11px] text-zinc-400">No document matches &quot;{filter}&quot;</p>
        )}
      </div>
    </div>
  );
};

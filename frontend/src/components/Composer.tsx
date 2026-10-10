'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Plus, ArrowUp, FileText, Layers, ChevronDown, X, Loader2, User, Users } from 'lucide-react';
import { DocumentLibrary } from './DocumentLibrary';
import { AnswerMode, DocumentMetadata } from '@/types';

const MAX_TEXTAREA_HEIGHT = 200;

const ANSWER_MODES = [
  { mode: 'agent' as const, label: 'Single', icon: User, title: 'Single agent: one agent with every search tool' },
  { mode: 'team' as const, label: 'Team', icon: Users, title: 'Team: a manager splits the question between a Concepts and a Reference specialist' },
];

interface ComposerProps {
  onSend: (text: string) => void;
  isPending: boolean;
  documents: DocumentMetadata[];
  selectedDocId: string | null;
  onSelectDoc: (docId: string | null) => void;
  onUploadSuccess: (document: DocumentMetadata) => void;
  onDeleteDoc: (docId: string) => void;
  isLibraryOpen: boolean;
  onLibraryOpenChange: (open: boolean) => void;
  libraryPlacement: 'top' | 'bottom';
  answerMode: AnswerMode;
  onAnswerModeChange: (mode: AnswerMode) => void;
}

/** The message box: grows with its text, Enter sends (Shift+Enter for a new line), + opens the document library,
 * and the Single / Team switch picks who answers. */
export const Composer: React.FC<ComposerProps> = ({
  onSend,
  isPending,
  documents,
  selectedDocId,
  onSelectDoc,
  onUploadSuccess,
  onDeleteDoc,
  isLibraryOpen,
  onLibraryOpenChange,
  libraryPlacement,
  answerMode,
  onAnswerModeChange,
}) => {
  const [text, setText] = useState('');
  const rootRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const selectedDoc = documents.find((d) => d.doc_id === selectedDocId) || null;
  const canSend = text.trim().length > 0 && !isPending;

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
  }, [text]);

  // Close the library on a click outside the composer or on Escape
  useEffect(() => {
    if (!isLibraryOpen) return;
    const onMouseDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) onLibraryOpenChange(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onLibraryOpenChange(false);
    };
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [isLibraryOpen, onLibraryOpenChange]);

  const submit = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText('');
    onLibraryOpenChange(false);
    textareaRef.current?.focus();
  };

  return (
    <div ref={rootRef} className="relative w-full">
      <DocumentLibrary
        open={isLibraryOpen}
        placement={libraryPlacement}
        documents={documents}
        selectedDocId={selectedDoc ? selectedDoc.doc_id : null}
        onSelectDoc={onSelectDoc}
        onUploadSuccess={onUploadSuccess}
        onDeleteDoc={onDeleteDoc}
        onClose={() => onLibraryOpenChange(false)}
      />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        onClick={() => textareaRef.current?.focus()}
        className="rounded-[26px] border border-zinc-200 bg-white px-3 pt-3 pb-2.5 shadow-[0_4px_20px_rgba(0,0,0,0.06)] focus-within:border-zinc-300 transition-colors cursor-text"
      >
        <textarea
          ref={textareaRef}
          rows={1}
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={
            selectedDoc
              ? `Ask about ${selectedDoc.filename}`
              : documents.length > 0
              ? 'Ask anything about your documents'
              : 'Upload a document with + to get started'
          }
          className="block w-full resize-none bg-transparent px-2 text-[15px] leading-6 text-zinc-900 placeholder:text-zinc-400 focus:outline-none"
          style={{ maxHeight: MAX_TEXTAREA_HEIGHT }}
        />

        <div className="mt-2 flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            onClick={() => onLibraryOpenChange(!isLibraryOpen)}
            className={`w-9 h-9 rounded-full border flex items-center justify-center shrink-0 transition-colors ${
              isLibraryOpen ? 'bg-zinc-100 border-zinc-300 text-zinc-900' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-100'
            }`}
            title="Upload or choose a document"
          >
            <Plus className="w-[18px] h-[18px]" />
          </button>

          {selectedDoc ? (
            <span className="min-w-0 inline-flex items-center gap-1.5 h-9 pl-3 pr-1.5 rounded-full bg-indigo-50 text-indigo-700 text-sm">
              <FileText className="w-4 h-4 shrink-0" />
              <span className="truncate max-w-[180px] sm:max-w-[280px]">{selectedDoc.filename}</span>
              <button
                type="button"
                onClick={() => onSelectDoc(null)}
                className="p-1 rounded-full hover:bg-indigo-100"
                title="Stop using this document (search all documents)"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          ) : (
            documents.length > 0 && (
              <button
                type="button"
                onClick={() => onLibraryOpenChange(!isLibraryOpen)}
                className="inline-flex items-center gap-1.5 h-9 px-3 rounded-full text-sm text-zinc-600 hover:bg-zinc-100"
                title="Choose which documents to search"
              >
                <Layers className="w-4 h-4" />
                All documents
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
            )
          )}

          <div role="radiogroup" aria-label="Who answers" className="ml-auto inline-flex items-center rounded-full bg-zinc-100 p-0.5 shrink-0">
            {ANSWER_MODES.map(({ mode, label, icon: Icon, title }) => (
              <button
                key={mode}
                type="button"
                role="radio"
                aria-checked={answerMode === mode}
                onClick={() => onAnswerModeChange(mode)}
                title={title}
                className={`inline-flex items-center gap-1.5 h-8 px-2.5 sm:px-3 rounded-full text-xs transition-colors ${
                  answerMode === mode ? 'bg-white text-zinc-900 font-medium shadow-sm' : 'text-zinc-500 hover:text-zinc-800'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </div>

          <button
            type="submit"
            disabled={!canSend}
            className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 bg-zinc-900 text-white hover:bg-zinc-700 disabled:bg-zinc-200 disabled:text-zinc-400 transition-colors"
            title={isPending ? 'Answering…' : 'Send'}
          >
            {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowUp className="w-[18px] h-[18px]" />}
          </button>
        </div>
      </form>
    </div>
  );
};

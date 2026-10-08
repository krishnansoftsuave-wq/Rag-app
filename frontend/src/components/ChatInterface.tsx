'use client';

import React, { useEffect, useRef } from 'react';
import { FileText, BarChart3, CalendarClock, ListChecks, UploadCloud } from 'lucide-react';
import { ChatMessage, DocumentMetadata } from '@/types';
import { Composer } from './Composer';
import { ChatMessageItem, ThinkingMessage } from './ChatMessageItem';

interface ChatInterfaceProps {
  chatKey: string; // the open conversation ("new" before the first message), to reset scrolling when it changes
  messages: ChatMessage[];
  isPending: boolean;
  userName?: string;
  documents: DocumentMetadata[];
  selectedDocId: string | null;
  onSelectDoc: (docId: string | null) => void;
  onUploadSuccess: (document: DocumentMetadata) => void;
  onDeleteDoc: (docId: string) => void;
  isLibraryOpen: boolean;
  onLibraryOpenChange: (open: boolean) => void;
  onSend: (text: string) => void;
  onRetry: (messageId: string) => void;
}

const SUGGESTIONS = [
  { icon: FileText, title: 'Summarize', prompt: 'Summarize the main topics in the document.' },
  { icon: ListChecks, title: 'Key findings', prompt: 'What are the key conclusions or findings?' },
  { icon: CalendarClock, title: 'Dates & metrics', prompt: 'List all important dates and metrics mentioned.' },
  { icon: BarChart3, title: 'Visualize', prompt: 'Show the most important numbers as a chart.' },
];

/** One conversation, ChatGPT style: a centered greeting and composer when empty, otherwise the thread with the composer docked below. */
export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  chatKey,
  messages,
  isPending,
  userName,
  documents,
  selectedDocId,
  onSelectDoc,
  onUploadSuccess,
  onDeleteDoc,
  isLibraryOpen,
  onLibraryOpenChange,
  onSend,
  onRetry,
}) => {
  const endRef = useRef<HTMLDivElement>(null);
  const isEmpty = messages.length === 0 && !isPending;
  // The document the pending question was asked about (the selection may have changed since)
  const pendingDoc = isPending ? [...messages].reverse().find((m) => m.sender === 'user')?.attachment?.filename : undefined;

  // Jump to the latest message when switching chats; follow new messages smoothly
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'auto' });
  }, [chatKey]);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, isPending]);

  const composer = (placement: 'top' | 'bottom') => (
    <Composer
      key={chatKey}
      onSend={onSend}
      isPending={isPending}
      documents={documents}
      selectedDocId={selectedDocId}
      onSelectDoc={onSelectDoc}
      onUploadSuccess={onUploadSuccess}
      onDeleteDoc={onDeleteDoc}
      isLibraryOpen={isLibraryOpen}
      onLibraryOpenChange={onLibraryOpenChange}
      libraryPlacement={placement}
    />
  );

  if (isEmpty) {
    return (
      <div className="flex-1 overflow-y-auto">
        <div className="min-h-full flex flex-col items-center justify-center px-4 pb-[12vh] pt-8">
          <div className="w-full max-w-3xl">
            <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-center">
              <span className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 bg-clip-text text-transparent">
                Hello{userName ? `, ${userName}` : ''}
              </span>
            </h1>
            <p className="mt-2 mb-8 text-center text-lg text-zinc-500">
              {documents.length > 0 ? 'What would you like to know from your documents?' : 'Upload a document and ask me anything about it.'}
            </p>

            {composer('bottom')}

            {documents.length > 0 ? (
              <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
                {SUGGESTIONS.map(({ icon: Icon, title, prompt }) => (
                  <button
                    key={title}
                    onClick={() => onSend(prompt)}
                    className="text-left rounded-2xl border border-zinc-200 px-4 py-3 hover:bg-zinc-50 transition-colors"
                  >
                    <Icon className="w-5 h-5 text-zinc-500 mb-2" />
                    <p className="text-sm font-medium text-zinc-800">{title}</p>
                    <p className="text-xs text-zinc-500 line-clamp-2 mt-0.5">{prompt}</p>
                  </button>
                ))}
              </div>
            ) : (
              <button
                onClick={() => onLibraryOpenChange(true)}
                className="mt-6 mx-auto flex items-center gap-2 rounded-full border border-zinc-200 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50"
              >
                <UploadCloud className="w-4 h-4" />
                Upload your first document
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-8">
          {messages.map((m) => (
            <ChatMessageItem key={m.id} message={m} onRetry={m.error ? () => onRetry(m.id) : undefined} />
          ))}
          {isPending && <ThinkingMessage scoped={pendingDoc} />}
          <div ref={endRef} />
        </div>
      </div>

      <div className="shrink-0 px-4 pb-3">
        <div className="max-w-3xl mx-auto">
          {composer('top')}
          <p className="mt-2 text-center text-xs text-zinc-400">
            DocuBrain answers from your uploaded documents and can make mistakes. Check important info.
          </p>
        </div>
      </div>
    </>
  );
};

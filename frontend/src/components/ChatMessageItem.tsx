'use client';

import React, { useState } from 'react';
import { Copy, Check, CircleAlert, RotateCcw, FileText, Sparkles } from 'lucide-react';
import { ChatMessage } from '@/types';
import { MarkdownMessage } from './MarkdownMessage';
import { SourceCard } from './SourceCard';
import { McpResults } from './McpResults';
import { ComparisonCard } from './ComparisonCard';

export const AssistantAvatar: React.FC<{ thinking?: boolean }> = ({ thinking }) => (
  <div
    className={`w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 flex items-center justify-center text-white shrink-0 ${
      thinking ? 'animate-pulse' : ''
    }`}
  >
    <Sparkles className="w-4 h-4" />
  </div>
);

const CopyButton: React.FC<{ text: string }> = ({ text }) => {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard?.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
      className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
      title={copied ? 'Copied' : 'Copy'}
    >
      {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
    </button>
  );
};

const fileKind = (filename: string) => (filename.includes('.') ? filename.split('.').pop()!.toUpperCase() : 'FILE');

interface ChatMessageItemProps {
  message: ChatMessage;
  onRetry?: () => void;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({ message, onRetry }) => {
  if (message.sender === 'user') {
    return (
      <div className="flex flex-col items-end gap-2">
        {message.attachment && (
          <div className="flex items-center gap-2.5 rounded-2xl border border-zinc-200 bg-white pl-2 pr-4 py-2 max-w-[80%]">
            <div className="w-9 h-9 rounded-lg bg-indigo-600 text-white flex items-center justify-center shrink-0">
              <FileText className="w-[18px] h-[18px]" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-zinc-800 truncate">{message.attachment.filename}</p>
              <p className="text-xs text-zinc-500">{fileKind(message.attachment.filename)}</p>
            </div>
          </div>
        )}
        <div className="max-w-[80%] rounded-3xl bg-zinc-100 px-5 py-2.5 text-[15px] leading-7 text-zinc-900 whitespace-pre-wrap break-words">
          {message.text}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4">
      <AssistantAvatar />
      <div className="flex-1 min-w-0 pt-0.5">
        {message.error ? (
          <div className="flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            <CircleAlert className="w-4 h-4 mt-0.5 shrink-0 text-rose-600" />
            <div className="flex-1 min-w-0">
              <p className="break-words">{message.text}</p>
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-rose-200 bg-white text-rose-700 hover:bg-rose-100"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Try again
                </button>
              )}
            </div>
          </div>
        ) : message.comparison ? (
          <ComparisonCard
            agentResult={message.agent_result}
            workflowResult={message.workflow_result}
            comparison={message.comparison}
          />
        ) : (
          <div className="text-[15px] leading-7 text-zinc-800 break-words">
            <MarkdownMessage>{message.text}</MarkdownMessage>
          </div>
        )}

        {message.mcp_results && message.mcp_results.length > 0 && <McpResults results={message.mcp_results} />}
        {message.sources && message.sources.length > 0 && <SourceCard sources={message.sources} />}

        {!message.error && (
          <div className="mt-1.5 -ml-1.5 flex items-center">
            <CopyButton text={message.text} />
          </div>
        )}
      </div>
    </div>
  );
};

/** Shown while the agent works on an answer. */
export const ThinkingMessage: React.FC<{ scoped?: string }> = ({ scoped }) => (
  <div className="flex gap-4">
    <AssistantAvatar thinking />
    <div className="pt-1.5 flex items-center gap-2 text-[15px] text-zinc-500">
      <span>{scoped ? `Reading ${scoped}` : 'Searching your documents'}</span>
      <span className="flex gap-1">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
    </div>
  </div>
);

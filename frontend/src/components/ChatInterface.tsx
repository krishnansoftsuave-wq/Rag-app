'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, Sparkles, AlertTriangle, RefreshCw, Swords, Cpu, Layers, Zap } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { ChatMessage, SourceCitation } from '@/types';
import { SourceCard } from './SourceCard';
import { ComparisonCard } from './ComparisonCard';
import { sendChatMessage } from '@/lib/api';

interface ChatInterfaceProps {
  selectedDocIds: string[];
  apiKey?: string;
  hasDocuments: boolean;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  selectedDocIds,
  apiKey,
  hasDocuments,
}) => {
  const [inputQuestion, setInputQuestion] = useState('');
  const [executionMode] = useState<'compare' | 'agent' | 'workflow' | 'standard'>('agent');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: '👋 **Welcome to Agentic RAG Assistant!**\n\nAsk any question about your documents. The **Autonomous LLM Agent** will dynamically select tools (semantic search, exact keyword search, proposition chunking, math evaluation, and evidence verification) to provide precise answers.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (questionText?: string) => {
    const rawQuery = questionText || inputQuestion;
    const query = rawQuery ? rawQuery.trim() : '';
    if (!query || isLoading) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuestion('');
    setIsLoading(true);

    try {
      const response = await sendChatMessage(query, selectedDocIds, apiKey, executionMode);

      const botMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: response.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources: response.sources,
        used_fallback: response.used_fallback,
        mode: response.mode,
        agent_result: response.agent_result,
        workflow_result: response.workflow_result,
        comparison: response.comparison,
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: `⚠️ **Error Processing Question**: ${err.message || 'Unable to connect to backend server.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const suggestedQuestions = [
    'Summarize the main topics in the uploaded document.',
    'What are the key conclusions or findings?',
    'List all important dates and metrics mentioned.',
  ];

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col h-[740px]">
      {/* Header bar */}
      <div className="px-5 py-3.5 border-b border-slate-100 flex flex-wrap items-center justify-between gap-3 bg-slate-50/50 rounded-t-2xl">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
              <span>Agentic RAG Assistant</span>
              <span className="text-[10px] bg-indigo-100 text-indigo-800 font-extrabold px-2 py-0.5 rounded-full border border-indigo-200">
                DYNAMIC TOOLS ACTIVE
              </span>
            </h2>
            <p className="text-[11px] text-slate-500">
              {selectedDocIds.length > 0
                ? `Searching ${selectedDocIds.length} selected file(s)`
                : 'Searching across all uploaded documents'}
            </p>
          </div>
        </div>

        {/* Clear Conversation button */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() =>
              setMessages([
                {
                  id: 'welcome',
                  sender: 'assistant',
                  text: 'Chat history cleared. What would you like to know about your documents?',
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                },
              ])
            }
            className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-100 transition-colors"
            title="Clear Conversation"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Clear Chat</span>
          </button>
        </div>
      </div>

      {/* Chat Messages Container */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start space-x-3 ${
              msg.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''
            }`}
          >
            {/* Avatar */}
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-white font-medium text-xs shadow-xs ${
                msg.sender === 'user'
                  ? 'bg-slate-800'
                  : 'bg-gradient-to-tr from-indigo-600 to-purple-600'
              }`}
            >
              {msg.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            {/* Bubble */}
            <div
              className={`rounded-2xl px-4 py-3 text-xs leading-relaxed shadow-2xs ${
                msg.sender === 'user'
                  ? 'max-w-[82%] bg-slate-900 text-slate-100 rounded-tr-none'
                  : msg.comparison
                  ? 'w-full max-w-[95%] bg-transparent p-0 border-none shadow-none'
                  : 'max-w-[85%] bg-slate-50 border border-slate-200/80 text-slate-800 rounded-tl-none'
              }`}
            >
              {msg.used_fallback && !msg.comparison && (
                <div className="mb-2 flex items-center gap-1 text-[11px] text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded-md">
                  <AlertTriangle className="w-3 h-3 shrink-0" />
                  <span>Using Local Vector Matcher (Add Gemini Key in settings for full LLM answers)</span>
                </div>
              )}

              {/* Standard text response if not comparison card */}
              {!msg.comparison && (
                <>
                  <div className="prose prose-xs max-w-none text-xs dark:prose-invert">
                    <ReactMarkdown>{msg.text}</ReactMarkdown>
                  </div>

                  {msg.sources && msg.sources.length > 0 && (
                    <SourceCard sources={msg.sources} />
                  )}

                  <div className="text-[10px] mt-1.5 text-right font-mono text-slate-400">
                    {msg.timestamp}
                  </div>
                </>
              )}

              {/* Render Dual Comparison Card when present */}
              {msg.comparison && (
                <ComparisonCard
                  agentResult={msg.agent_result}
                  workflowResult={msg.workflow_result}
                  comparison={msg.comparison}
                />
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-start space-x-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center text-white shrink-0">
              <Bot className="w-4 h-4 animate-bounce" />
            </div>
            <div className="bg-slate-50 border border-slate-200 rounded-2xl rounded-tl-none px-4 py-3 flex items-center space-x-2 text-xs text-slate-600">
              <Loader2 className="w-4 h-4 text-indigo-600 animate-spin" />
              <span>
                {executionMode === 'compare'
                  ? '⚡ Running Adaptive Agent & Fixed Workflow side-by-side...'
                  : executionMode === 'agent'
                  ? '🧠 Running Adaptive RAG Agent evaluation loop...'
                  : executionMode === 'workflow'
                  ? '⚙️ Executing 4-step Fixed RAG Workflow...'
                  : 'Retrieving context & generating answer...'}
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts when documents exist */}
      {hasDocuments && messages.length <= 2 && (
        <div className="px-6 py-2 flex flex-wrap gap-2">
          {suggestedQuestions.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(q)}
              className="text-[11px] bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-200 border border-slate-200 text-slate-600 px-3 py-1.5 rounded-full transition-all flex items-center gap-1"
            >
              <Sparkles className="w-3 h-3 text-indigo-500" />
              <span>{q}</span>
            </button>
          ))}
        </div>
      )}

      {/* Input Box */}
      <div className="p-4 border-t border-slate-100 bg-white rounded-b-2xl">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-2"
        >
          <input
            type="text"
            value={inputQuestion}
            onChange={(e) => setInputQuestion(e.target.value)}
            placeholder={
              hasDocuments
                ? executionMode === 'compare'
                  ? 'Ask a question to compare Agentic vs Fixed Workflow...'
                  : 'Ask a question about your uploaded documents...'
                : 'Upload a document on the left, then ask a question...'
            }
            className="flex-1 bg-slate-50 border border-slate-200 focus:border-indigo-500 focus:bg-white focus:outline-none rounded-xl px-4 py-2.5 text-xs text-slate-800 transition-all placeholder:text-slate-400"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !inputQuestion.trim()}
            className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50 text-white flex items-center justify-center shadow-md shadow-indigo-500/20 transition-all shrink-0"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
      </div>
    </div>
  );
};

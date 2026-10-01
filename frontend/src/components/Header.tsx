'use client';

import React from 'react';
import Link from 'next/link';
import { Database, Key, CheckCircle, AlertCircle, FileText, Sparkles, BarChart2 } from 'lucide-react';

interface HeaderProps {
  isBackendConnected: boolean;
  totalDocuments: number;
  totalChunks: number;
  hasApiKey: boolean;
  onOpenApiKeyModal: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  isBackendConnected,
  totalDocuments,
  totalChunks,
  hasApiKey,
  onOpenApiKeyModal,
}) => {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 px-6 py-4 shadow-sm">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand logo & title */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center text-white shadow-md shadow-emerald-500/20">
            <Sparkles className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-slate-900 via-slate-800 to-slate-700 bg-clip-text text-transparent">
              DocuBrain RAG
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              Document Retrieval & AI Question Answering
            </p>
          </div>
        </div>

        {/* Status badges & controls */}
        <div className="flex items-center space-x-4">
          {/* Agent Evaluation Nav Link */}
          <Link
            href="/evaluation"
            className="flex items-center space-x-1.5 text-xs font-bold px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition-all"
          >
            <BarChart2 className="w-3.5 h-3.5 text-indigo-600" />
            <span>Agent Evaluation</span>
          </Link>

          {/* Document stats */}
          <div className="hidden sm:flex items-center space-x-3 text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-slate-600">
            <div className="flex items-center space-x-1">
              <FileText className="w-3.5 h-3.5 text-slate-400" />
              <span className="font-semibold">{totalDocuments}</span>
              <span>docs</span>
            </div>
            <span className="text-slate-300">|</span>
            <div className="flex items-center space-x-1">
              <Database className="w-3.5 h-3.5 text-slate-400" />
              <span className="font-semibold">{totalChunks}</span>
              <span>chunks</span>
            </div>
          </div>

          {/* Connection status */}
          <div
            className={`flex items-center space-x-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${
              isBackendConnected
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-rose-50 text-rose-700 border-rose-200'
            }`}
          >
            {isBackendConnected ? (
              <>
                <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
                <span>Backend Online</span>
              </>
            ) : (
              <>
                <AlertCircle className="w-3.5 h-3.5 text-rose-500" />
                <span>Backend Offline</span>
              </>
            )}
          </div>

          {/* API Key Modal Button */}
          <button
            onClick={onOpenApiKeyModal}
            className={`flex items-center space-x-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-all ${
              hasApiKey
                ? 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200'
                : 'bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-300'
            }`}
          >
            <Key className="w-3.5 h-3.5" />
            <span>{hasApiKey ? 'API Key Set' : 'Configure LLM Key'}</span>
          </button>
        </div>
      </div>
    </header>
  );
};

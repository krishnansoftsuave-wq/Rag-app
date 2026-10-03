'use client';

import React from 'react';
import Link from 'next/link';
import { Database, Key, CheckCircle, AlertCircle, FileText, Sparkles, BarChart2, User, LogOut, Lock } from 'lucide-react';

interface HeaderProps {
  isBackendConnected: boolean;
  totalDocuments: number;
  totalChunks: number;
  hasApiKey: boolean;
  onOpenApiKeyModal: () => void;
  currentUser?: any;
  onOpenAuthModal?: () => void;
  onLogout?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  isBackendConnected,
  totalDocuments,
  totalChunks,
  hasApiKey,
  onOpenApiKeyModal,
  currentUser,
  onOpenAuthModal,
  onLogout,
}) => {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 px-6 py-4 shadow-sm">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand logo & title */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 via-teal-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-emerald-500/20">
            <Sparkles className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-900 bg-clip-text text-transparent">
              DocuBrain RAG & MCP
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              Enterprise Document RAG with Authenticated MCP Tools
            </p>
          </div>
        </div>

        {/* Status badges & controls */}
        <div className="flex items-center space-x-3 sm:space-x-4">
          {/* Agent Evaluation Nav Link */}
          <Link
            href="/evaluation"
            className="hidden md:flex items-center space-x-1.5 text-xs font-bold px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition-all"
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
            className={`hidden lg:flex items-center space-x-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${
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
            <span className="hidden sm:inline">{hasApiKey ? 'API Key Set' : 'Configure Key'}</span>
          </button>

          {/* User Auth Profile / Login Button */}
          {currentUser ? (
            <div className="flex items-center space-x-2 bg-indigo-50/80 border border-indigo-200/80 rounded-lg px-2.5 py-1 text-xs">
              <User className="w-3.5 h-3.5 text-indigo-600" />
              <span className="font-bold text-indigo-900 max-w-[100px] truncate">{currentUser.username}</span>
              <button
                onClick={onLogout}
                title="Log Out"
                className="text-slate-400 hover:text-rose-600 ml-1"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <button
              onClick={onOpenAuthModal}
              className="flex items-center space-x-1.5 text-xs font-bold px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white shadow-md shadow-indigo-500/20 transition-all"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Log In</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};

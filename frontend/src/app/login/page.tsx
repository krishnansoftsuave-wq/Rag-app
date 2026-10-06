'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Shield, Key, Lock, User, ArrowRight, CheckCircle2, AlertCircle, Copy, Check } from 'lucide-react';
import { loginUser, registerUser, saveAuthToken } from '@/lib/api';

function LoginContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const isOAuth = searchParams.get('oauth_authorize') === '1';
  const redirectUri = searchParams.get('redirect_uri');
  const clientId = searchParams.get('client_id');
  const state = searchParams.get('state');

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [mcpConfigJson, setMcpConfigJson] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      let res;
      if (mode === 'login') {
        res = await loginUser(username, password);
      } else {
        res = await registerUser(username, email, password);
      }

      saveAuthToken(res.access_token);
      localStorage.setItem('docubrain_user', JSON.stringify(res.user));
      setSuccessMsg(`Welcome, ${res.user.username}! Authenticating session...`);

      // Compute ready-to-use Antigravity snippet
      const hostIp = window.location.hostname || '192.168.12.212';
      const configObj = {
        mcpServers: {
          "docubrain-rag": {
            command: "npx",
            args: [
              "-y",
              "@modelcontextprotocol/server-sse",
              `http://${hostIp}:8000/mcp/sse`,
              "--header",
              `Authorization: Bearer ${res.access_token}`
            ]
          }
        }
      };
      setMcpConfigJson(JSON.stringify(configObj, null, 2));

      // If this login was triggered by an OAuth / MCP Connector authorization flow:
      if (isOAuth && redirectUri) {
        const apiBase = `http://${hostIp}:8000`;
        let authUrl = `${apiBase}/api/v1/oauth/authorize?token=${encodeURIComponent(res.access_token)}&redirect_uri=${encodeURIComponent(redirectUri)}&client_id=${encodeURIComponent(clientId || 'docubrain_client')}`;
        if (state) authUrl += `&state=${encodeURIComponent(state)}`;

        setTimeout(() => {
          window.location.href = authUrl;
        }, 1200);
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (mcpConfigJson) {
      navigator.clipboard.writeText(mcpConfigJson);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl space-y-6">
        {/* Header Branding */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center p-3 bg-cyan-500/10 rounded-2xl border border-cyan-500/20 mb-2">
            <Shield className="w-8 h-8 text-cyan-400" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            {isOAuth ? 'Connect MCP Client' : mode === 'login' ? 'DocuBrain RAG Portal' : 'Create an Account'}
          </h1>
          <p className="text-sm text-slate-400">
            {isOAuth
              ? 'Sign in to authorize your Claude / IDE MCP Connector'
              : 'Sign in to generate your authenticated Antigravity MCP snippet'}
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="bg-rose-950/40 border border-rose-500/30 text-rose-300 p-3 rounded-xl flex items-center space-x-2 text-sm">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Success Alert & Antigravity Config Output */}
        {mcpConfigJson ? (
          <div className="space-y-4">
            <div className="bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 p-3 rounded-xl flex items-center space-x-2 text-sm">
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              <span>Authentication successful!</span>
            </div>

            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-cyan-400 uppercase tracking-wider">
                  Antigravity .agents/mcp_config.json
                </span>
                <button
                  type="button"
                  onClick={handleCopy}
                  className="px-2.5 py-1 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 rounded-lg text-xs font-medium flex items-center space-x-1 transition-all"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied!' : 'Copy Config'}</span>
                </button>
              </div>
              <pre className="text-xs text-slate-300 bg-slate-900 p-3 rounded-lg overflow-x-auto font-mono">
                {mcpConfigJson}
              </pre>
            </div>

            <button
              type="button"
              onClick={() => router.push('/')}
              className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-xl transition-all"
            >
              Go to App Dashboard
            </button>
          </div>
        ) : (
          /* Login Form */
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Username
              </label>
              <div className="relative">
                <User className="w-4 h-4 absolute left-3 top-3.5 text-slate-500" />
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username or email"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            {mode === 'register' && (
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Email Address
                </label>
                <div className="relative">
                  <User className="w-4 h-4 absolute left-3 top-3.5 text-slate-500" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="colleague@company.com"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 absolute left-3 top-3.5 text-slate-500" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-medium rounded-xl shadow-lg transition-all flex items-center justify-center space-x-2"
            >
              <span>{loading ? 'Authenticating...' : isOAuth ? 'Authorize & Connect' : mode === 'login' ? 'Sign In' : 'Register Account'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        )}

        {/* Mode Toggle */}
        {!mcpConfigJson && (
          <div className="text-center pt-2">
            <button
              type="button"
              onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
              className="text-xs text-slate-400 hover:text-cyan-400 transition-colors"
            >
              {mode === 'login'
                ? "Don't have an account? Register here"
                : 'Already have an account? Sign in'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400">Loading Login...</div>}>
      <LoginContent />
    </Suspense>
  );
}

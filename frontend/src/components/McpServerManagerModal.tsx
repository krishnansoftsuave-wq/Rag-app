'use client';

import React, { useState, useEffect } from 'react';
import {
  fetchExternalMcpServers,
  testMcpServerConnection,
  addExternalMcpServer,
  toggleMcpServer,
  refreshMcpServer,
  deleteMcpServer,
  callRemoteMcpTool,
} from '@/lib/api';

interface McpServerManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function McpServerManagerModal({ isOpen, onClose }: McpServerManagerModalProps) {
  const [servers, setServers] = useState<any[]>([]);
  const [activeToolsCount, setActiveToolsCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form State
  const [name, setName] = useState<string>('Standalone MCP Server');
  const [url, setUrl] = useState<string>('http://localhost:8005/sse');
  const [transport, setTransport] = useState<string>('sse');
  const [authType, setAuthType] = useState<string>('none');
  const [authToken, setAuthToken] = useState<string>('');
  
  // Test Connection State
  const [testing, setTesting] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<any | null>(null);

  // Expanded Server Tools State
  const [expandedServerId, setExpandedServerId] = useState<string | null>(null);

  // Live Tool Execution Sandbox State
  const [executingTool, setExecutingTool] = useState<string | null>(null);
  const [toolResult, setToolResult] = useState<any | null>(null);

  const loadServers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchExternalMcpServers();
      if (data.servers) {
        setServers(data.servers);
        setActiveToolsCount(data.active_tools_count || 0);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load MCP servers');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadServers();
      setTestResult(null);
      setSuccessMsg(null);
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleTestConnection = async () => {
    if (!url) return;
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      const res = await testMcpServerConnection(url, transport, authType, authToken);
      setTestResult(res);
    } catch (err: any) {
      setError(err.message || 'Test connection failed');
    } finally {
      setTesting(false);
    }
  };

  const handleAddServer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !url) return;
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await addExternalMcpServer(name, url, transport, authType, authToken);
      setSuccessMsg(`Successfully connected to '${res.server.name}' (${res.server.discovered_tools.length} tools found)`);
      setName('Custom MCP Service');
      setUrl('http://localhost:8001/sse');
      setTestResult(null);
      await loadServers();
    } catch (err: any) {
      setError(err.message || 'Failed to add server');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (serverId: string, currentActive: boolean) => {
    try {
      await toggleMcpServer(serverId, !currentActive);
      await loadServers();
    } catch (err: any) {
      setError(err.message || 'Failed to toggle server');
    }
  };

  const handleRefresh = async (serverId: string) => {
    setLoading(true);
    try {
      await refreshMcpServer(serverId);
      await loadServers();
      setSuccessMsg('Refreshed connection & tool schema successfully.');
    } catch (err: any) {
      setError(err.message || 'Refresh failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (serverId: string) => {
    if (!confirm('Are you sure you want to remove this MCP server?')) return;
    try {
      await deleteMcpServer(serverId);
      await loadServers();
    } catch (err: any) {
      setError(err.message || 'Delete failed');
    }
  };

  const handleRunTool = async (serverId: string, toolName: string) => {
    setExecutingTool(toolName);
    setToolResult(null);
    try {
      let sampleArgs: any = {};
      if (toolName === 'generate_artifact') {
        sampleArgs = {
          question: 'What are the uptime and security guarantees?',
          answer: 'DocuBrain guarantees 99.99% monthly uptime with a 15% service credit, AES-256 at rest and TLS 1.3 in transit.',
          sources: [
            {
              filename: 'DocuBrain_Cloud_SLA_2026.txt',
              chunk_index: 0,
              content:
                'DocuBrain guarantees a 99.99% monthly uptime for all Enterprise RAG API endpoints. If monthly uptime drops below 99.99%, customers receive a 15% service credit. All customer document embeddings are encrypted at rest using AES-256. Document text transmitted over network uses TLS 1.3 encryption.',
            },
          ],
          artifact_type: 'auto',
        };
      }

      const res = await callRemoteMcpTool(serverId, toolName, sampleArgs);
      setToolResult(res);
    } catch (err: any) {
      setToolResult({ success: false, error: err.message });
    } finally {
      setExecutingTool(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-700/70 rounded-2xl shadow-2xl w-full max-w-4xl p-6 text-slate-100 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-gradient-to-tr from-purple-600 to-indigo-600 rounded-xl shadow-lg shadow-purple-500/20">
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                External MCP Server Client
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                  Claude Desktop Style
                </span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Connect custom remote MCP Server URLs (SSE/HTTP). App discovers and exposes tools to AI Agent.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-2 rounded-lg hover:bg-slate-800 transition"
          >
            ✕
          </button>
        </div>

        {/* Notifications */}
        {error && (
          <div className="mb-4 p-3 bg-red-950/60 border border-red-800/60 text-red-200 text-xs rounded-xl flex justify-between items-center">
            <span>⚠️ {error}</span>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-white">✕</button>
          </div>
        )}

        {successMsg && (
          <div className="mb-4 p-3 bg-emerald-950/60 border border-emerald-800/60 text-emerald-200 text-xs rounded-xl flex justify-between items-center">
            <span>✅ {successMsg}</span>
            <button onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-white">✕</button>
          </div>
        )}

        <div className="overflow-y-auto flex-1 space-y-6 pr-1">
          {/* Section 1: Add New Custom MCP Server */}
          <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <span>➕ Connect New Standalone MCP Server</span>
            </h3>
            <form onSubmit={handleAddServer} className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Server Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Weather & DB Server"
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Transport</label>
                  <select
                    value={transport}
                    onChange={(e) => setTransport(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
                  >
                    <option value="sse">SSE (Server-Sent Events - FastMCP Standard)</option>
                    <option value="http">HTTP / REST API Endpoint</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">MCP Custom Server URL</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="http://localhost:8001/sse"
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500 font-mono"
                    required
                  />
                  <button
                    type="button"
                    onClick={handleTestConnection}
                    disabled={testing}
                    className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-xs font-medium rounded-lg text-slate-200 transition disabled:opacity-50"
                  >
                    {testing ? 'Testing...' : 'Test Connection'}
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Authentication Type</label>
                  <select
                    value={authType}
                    onChange={(e) => setAuthType(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
                  >
                    <option value="none">No Auth (Public)</option>
                    <option value="bearer">Bearer Token (Authorization Header / Query Param)</option>
                    <option value="api_key">API Key (X-API-Key Header)</option>
                  </select>
                </div>

                {authType !== 'none' && (
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Auth Token / Secret Key</label>
                    <input
                      type="password"
                      value={authToken}
                      onChange={(e) => setAuthToken(e.target.value)}
                      placeholder="e.g. standalone_secret_123"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500 font-mono"
                    />
                  </div>
                )}
              </div>

              {/* Test Result Inspector */}
              {testResult && (
                <div className="p-3 bg-slate-900/90 border border-purple-500/40 rounded-lg text-xs space-y-2">
                  <div className="flex items-center justify-between font-semibold">
                    <span className={testResult.status === 'connected' ? 'text-emerald-400' : 'text-red-400'}>
                      Status: {testResult.status.toUpperCase()} ({testResult.total_tools} tools discovered)
                    </span>
                    <span className="text-slate-500 text-[10px]">{testResult.tested_at}</span>
                  </div>
                  {testResult.error && (
                    <p className="text-red-300 font-mono text-[11px]">{testResult.error}</p>
                  )}
                  {testResult.tools && testResult.tools.length > 0 && (
                    <div className="space-y-1 pt-1 border-t border-slate-800">
                      <p className="text-slate-400 font-medium">Discovered Remote Tools:</p>
                      <div className="flex flex-wrap gap-1.5">
                        {testResult.tools.map((t: any, idx: number) => (
                          <span key={idx} className="px-2 py-0.5 bg-purple-900/40 text-purple-300 border border-purple-700/50 rounded font-mono text-[10px]">
                            ⚙️ {t.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-purple-600/30 transition disabled:opacity-50"
                >
                  {loading ? 'Connecting...' : 'Save & Connect Server'}
                </button>
              </div>
            </form>
          </div>

          {/* Section 2: Configured MCP Servers List */}
          <div>
            <div className="flex justify-between items-center mb-3">
              <h3 className="text-sm font-semibold text-slate-200">
                Connected MCP Servers ({servers.length})
              </h3>
              <span className="text-xs text-purple-400 bg-purple-950/60 border border-purple-800/60 px-2.5 py-1 rounded-lg">
                ⚡ Active Tools Available to Agent: {activeToolsCount}
              </span>
            </div>

            {servers.length === 0 ? (
              <div className="p-8 text-center bg-slate-800/30 border border-slate-800 rounded-xl text-slate-500 text-xs">
                No external MCP servers configured yet. Add one above!
              </div>
            ) : (
              <div className="space-y-3">
                {servers.map((srv) => (
                  <div
                    key={srv.id}
                    className="bg-slate-800/50 border border-slate-700/60 rounded-xl p-4 transition hover:border-slate-600"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <span className="relative flex h-3 w-3">
                          {srv.status === 'connected' && srv.is_active ? (
                            <>
                              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                            </>
                          ) : (
                            <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                          )}
                        </span>

                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="font-semibold text-sm text-slate-100">{srv.name}</h4>
                            <span className="text-[10px] px-2 py-0.5 rounded bg-slate-700 text-slate-300 font-mono">
                              {srv.transport?.toUpperCase()}
                            </span>
                          </div>
                          <p className="text-xs font-mono text-slate-400">{srv.url}</p>
                        </div>
                      </div>

                      <div className="flex items-center space-x-3">
                        {/* Active Toggle */}
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={srv.is_active}
                            onChange={() => handleToggle(srv.id, srv.is_active)}
                            className="sr-only peer"
                          />
                          <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
                        </label>

                        {/* Refresh */}
                        <button
                          onClick={() => handleRefresh(srv.id)}
                          title="Refresh Tool Discovery"
                          className="p-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-slate-300 text-xs transition"
                        >
                          🔄
                        </button>

                        {/* Delete */}
                        <button
                          onClick={() => handleDelete(srv.id)}
                          title="Remove Server"
                          className="p-1.5 bg-red-950/60 hover:bg-red-900 border border-red-800/60 rounded-lg text-red-300 text-xs transition"
                        >
                          🗑️
                        </button>
                      </div>
                    </div>

                    {/* Discovered Tools Summary */}
                    <div className="mt-3 pt-3 border-t border-slate-700/50 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs text-slate-400">Exported Tools:</span>
                        <span className="text-xs font-semibold px-2 py-0.5 bg-purple-950 text-purple-300 rounded border border-purple-800">
                          {srv.discovered_tools?.length || 0} Tools Discovered
                        </span>
                      </div>

                      <button
                        onClick={() => setExpandedServerId(expandedServerId === srv.id ? null : srv.id)}
                        className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-medium"
                      >
                        {expandedServerId === srv.id ? 'Hide Tools ▲' : 'Inspect Tools & Run Live Sandbox ▼'}
                      </button>
                    </div>

                    {/* Expanded Tools Drawer */}
                    {expandedServerId === srv.id && (
                      <div className="mt-3 p-3 bg-slate-900/90 rounded-lg border border-slate-700 space-y-2 text-xs">
                        <h5 className="font-semibold text-slate-300 border-b border-slate-800 pb-1">
                          Discovered Remote MCP Tools:
                        </h5>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
                          {srv.discovered_tools?.map((tool: any, idx: number) => (
                            <div key={idx} className="p-2.5 bg-slate-800/80 rounded-lg border border-slate-700/70 space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-mono font-semibold text-purple-300 text-xs">
                                  ⚙️ {tool.name}
                                </span>
                                <button
                                  onClick={() => handleRunTool(srv.id, tool.name)}
                                  disabled={executingTool === tool.name}
                                  className="px-2 py-1 bg-emerald-700 hover:bg-emerald-600 text-white rounded text-[10px] transition disabled:opacity-50"
                                >
                                  {executingTool === tool.name ? 'Running...' : '▶ Run Tool'}
                                </button>
                              </div>
                              <p className="text-slate-400 text-[11px] leading-tight">{tool.description}</p>
                            </div>
                          ))}
                        </div>

                        {/* Tool Execution Result Box */}
                        {toolResult && (
                          <div className="mt-3 p-3 bg-black/60 border border-emerald-500/40 rounded-lg font-mono text-[11px] space-y-1">
                            <div className="flex justify-between items-center text-emerald-400 font-semibold border-b border-slate-800 pb-1">
                              <span>Output from Standalone MCP Execution:</span>
                              <button onClick={() => setToolResult(null)} className="text-slate-400 hover:text-white">✕</button>
                            </div>
                            <pre className="text-slate-300 overflow-x-auto whitespace-pre-wrap max-h-40 pt-1">
                              {JSON.stringify(toolResult.result || toolResult, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-slate-800 pt-4 mt-4 flex justify-between items-center text-xs text-slate-500">
          <span>Standard MCP Protocol over SSE • Port 8001 Standalone Support</span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium rounded-xl transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

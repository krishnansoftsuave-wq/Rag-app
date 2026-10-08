'use client';

import React, { useState, useEffect } from 'react';
import {
  X,
  Plus,
  RefreshCw,
  Trash2,
  ChevronDown,
  ChevronRight,
  Play,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Lock,
  Wrench,
  Plug,
} from 'lucide-react';
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

// Arguments used when a tool is run from the sandbox; other tools are called without arguments
const SAMPLE_ARGS: Record<string, Record<string, any>> = {
  generate_artifact: {
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
  },
};

const inputClass =
  'w-full rounded-xl border border-zinc-300 bg-white px-3.5 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:border-zinc-500 transition-colors';
const labelClass = 'block text-xs font-medium text-zinc-600 mb-1.5';

const Toggle: React.FC<{ checked: boolean; onChange: () => void; label: string }> = ({ checked, onChange, label }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    aria-label={label}
    title={label}
    onClick={onChange}
    className={`relative w-9 h-5 rounded-full transition-colors shrink-0 ${checked ? 'bg-zinc-900' : 'bg-zinc-300'}`}
  >
    <span
      className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-4' : ''}`}
    />
  </button>
);

/** Where a server stands, as a dot and a short label. */
function serverStatus(srv: any): { dot: string; label: string } {
  const tools = srv.discovered_tools?.length || 0;
  if (!srv.is_active) return { dot: 'bg-zinc-300', label: 'Disabled' };
  if (srv.status === 'connected') return { dot: 'bg-emerald-500', label: `Connected · ${tools} tool${tools === 1 ? '' : 's'}` };
  if (srv.status === 'error') return { dot: 'bg-rose-500', label: "Can't connect" };
  return { dot: 'bg-amber-400', label: 'Not checked yet' };
}

export default function McpServerManagerModal({ isOpen, onClose }: McpServerManagerModalProps) {
  const [servers, setServers] = useState<any[]>([]);
  const [activeToolsCount, setActiveToolsCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Add-server form
  const [showAddForm, setShowAddForm] = useState<boolean>(false);
  const [name, setName] = useState<string>('');
  const [url, setUrl] = useState<string>('');
  const [transport, setTransport] = useState<string>('sse');
  const [authType, setAuthType] = useState<string>('none');
  const [authToken, setAuthToken] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [testing, setTesting] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<any | null>(null);
  const [saving, setSaving] = useState<boolean>(false);

  // Server rows
  const [busyServerId, setBusyServerId] = useState<string | null>(null);
  const [expandedServerId, setExpandedServerId] = useState<string | null>(null);
  const [executingTool, setExecutingTool] = useState<string | null>(null); // "<server id>:<tool name>"
  const [toolResult, setToolResult] = useState<{ key: string; result: any } | null>(null);

  const loadServers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchExternalMcpServers();
      if (data.servers) {
        setServers(data.servers);
        setActiveToolsCount(data.active_tools_count || 0);
        if (data.servers.length === 0) setShowAddForm(true);
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

  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const resetForm = () => {
    setName('');
    setUrl('');
    setTransport('sse');
    setAuthType('none');
    setAuthToken('');
    setDescription('');
    setTestResult(null);
  };

  const handleTestConnection = async () => {
    if (!url) return;
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      setTestResult(await testMcpServerConnection(url, transport, authType, authToken));
    } catch (err: any) {
      setError(err.message || 'Test connection failed');
    } finally {
      setTesting(false);
    }
  };

  const handleAddServer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !url) return;
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await addExternalMcpServer(name, url, transport, authType, authToken, description);
      const srv = res.server;
      if (srv.status === 'connected') {
        setSuccessMsg(`Connected to ${srv.name} · ${srv.discovered_tools.length} tools found`);
      } else {
        setError(`Saved ${srv.name}, but could not connect: ${srv.error_detail || 'unknown error'}`);
      }
      resetForm();
      setShowAddForm(false);
      await loadServers();
    } catch (err: any) {
      setError(err.message || 'Failed to add server');
    } finally {
      setSaving(false);
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
    setBusyServerId(serverId);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await refreshMcpServer(serverId);
      const srv = res.server;
      if (srv.status === 'connected') {
        setSuccessMsg(`${srv.name} refreshed · ${srv.discovered_tools.length} tools`);
      } else {
        setError(`Could not connect to ${srv.name}: ${srv.error_detail || 'unknown error'}`);
      }
      await loadServers();
    } catch (err: any) {
      setError(err.message || 'Refresh failed');
    } finally {
      setBusyServerId(null);
    }
  };

  const handleDelete = async (serverId: string, serverName: string) => {
    if (!confirm(`Remove ${serverName}?`)) return;
    try {
      await deleteMcpServer(serverId);
      await loadServers();
    } catch (err: any) {
      setError(err.message || 'Delete failed');
    }
  };

  const handleRunTool = async (serverId: string, toolName: string) => {
    const key = `${serverId}:${toolName}`;
    setExecutingTool(key);
    setToolResult(null);
    try {
      const res = await callRemoteMcpTool(serverId, toolName, SAMPLE_ARGS[toolName] || {});
      setToolResult({ key, result: res });
    } catch (err: any) {
      setToolResult({ key, result: { success: false, error: err.message } });
    } finally {
      setExecutingTool(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-[2px] p-4" onMouseDown={onClose}>
      <div
        className="w-full max-w-2xl max-h-[88vh] flex flex-col rounded-3xl bg-white border border-zinc-200 shadow-2xl text-zinc-900"
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 px-6 pt-6 pb-4">
          <div>
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <Plug className="w-5 h-5 text-zinc-500" />
              MCP servers
            </h2>
            <p className="text-sm text-zinc-500 mt-1">
              Connect external MCP servers. The assistant uses their tools when a question needs them.
            </p>
          </div>
          <button onClick={onClose} className="p-2 -mr-2 rounded-lg text-zinc-400 hover:text-zinc-800 hover:bg-zinc-100" title="Close">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-4">
          {/* Notifications */}
          {error && (
            <div className="flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0 text-rose-600" />
              <span className="flex-1 break-words">{error}</span>
              <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-700">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
          {successMsg && (
            <div className="flex items-start gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0 text-emerald-600" />
              <span className="flex-1">{successMsg}</span>
              <button onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-emerald-700">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Connected servers */}
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-zinc-700">
              Connected <span className="text-zinc-400">({servers.length})</span>
            </h3>
            <span className="text-xs text-zinc-500">
              {activeToolsCount} tool{activeToolsCount === 1 ? '' : 's'} available to the assistant
            </span>
          </div>

          {loading && servers.length === 0 ? (
            <div className="flex items-center justify-center gap-2 py-8 text-sm text-zinc-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              Checking servers…
            </div>
          ) : servers.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-zinc-300 py-8 text-center text-sm text-zinc-500">
              No MCP servers yet. Add one below.
            </div>
          ) : (
            <div className="rounded-2xl border border-zinc-200 divide-y divide-zinc-200">
              {servers.map((srv) => {
                const status = serverStatus(srv);
                const isExpanded = expandedServerId === srv.id;
                const tools: any[] = srv.discovered_tools || [];
                return (
                  <div key={srv.id} className="px-4 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-zinc-100 text-zinc-600 flex items-center justify-center shrink-0">
                        <Plug className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 min-w-0">
                          <p className="text-sm font-medium text-zinc-900 truncate">{srv.name}</p>
                          <span className="hidden sm:inline text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-500 shrink-0">
                            {srv.transport}
                          </span>
                          {srv.auth_type && srv.auth_type !== 'none' && (
                            <span
                              className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-500 shrink-0"
                              title={srv.auth_type === 'bearer' ? 'Bearer token' : 'API key'}
                            >
                              <Lock className="w-2.5 h-2.5" />
                              {srv.auth_type === 'bearer' ? 'Bearer' : 'API key'}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-zinc-500 font-mono truncate">{srv.url}</p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={() => handleRefresh(srv.id)}
                          disabled={busyServerId === srv.id}
                          className="p-2 rounded-lg text-zinc-400 hover:text-zinc-800 hover:bg-zinc-100 disabled:opacity-50"
                          title="Reconnect and refresh tools"
                        >
                          <RefreshCw className={`w-4 h-4 ${busyServerId === srv.id ? 'animate-spin' : ''}`} />
                        </button>
                        <button
                          onClick={() => handleDelete(srv.id, srv.name)}
                          className="p-2 rounded-lg text-zinc-400 hover:text-rose-600 hover:bg-rose-50"
                          title="Remove server"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                        <span className="ml-1">
                          <Toggle
                            checked={!!srv.is_active}
                            onChange={() => handleToggle(srv.id, srv.is_active)}
                            label={srv.is_active ? 'Disable server' : 'Enable server'}
                          />
                        </span>
                      </div>
                    </div>

                    <div className="mt-2 sm:pl-12 flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span className="inline-flex items-center gap-1.5 text-xs text-zinc-600">
                        <span className={`w-2 h-2 rounded-full ${status.dot}`} />
                        {status.label}
                      </span>
                      {tools.length > 0 && (
                        <button
                          onClick={() => setExpandedServerId(isExpanded ? null : srv.id)}
                          className="inline-flex items-center gap-1 text-xs font-medium text-zinc-600 hover:text-zinc-900"
                        >
                          {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                          {isExpanded ? 'Hide tools' : 'Show tools'}
                        </button>
                      )}
                    </div>
                    {srv.is_active && srv.status === 'error' && srv.error_detail && (
                      <p className="mt-1 sm:pl-12 text-xs text-rose-600 break-words">{srv.error_detail}</p>
                    )}

                    {isExpanded && (
                      <div className="mt-3 sm:ml-12 space-y-2">
                        {tools.map((tool: any) => {
                          const key = `${srv.id}:${tool.name}`;
                          return (
                            <div key={tool.name} className="rounded-xl border border-zinc-200 bg-zinc-50/60 px-3.5 py-3">
                              <div className="flex items-center justify-between gap-2">
                                <span className="min-w-0 truncate inline-flex items-center gap-1.5 text-sm font-medium text-zinc-800 font-mono">
                                  <Wrench className="w-3.5 h-3.5 text-zinc-400" />
                                  {tool.name}
                                </span>
                                <button
                                  onClick={() => handleRunTool(srv.id, tool.name)}
                                  disabled={executingTool === key}
                                  className="shrink-0 whitespace-nowrap inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-lg border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-100 disabled:opacity-50"
                                  title={SAMPLE_ARGS[tool.name] ? 'Run with sample arguments' : 'Run without arguments'}
                                >
                                  {executingTool === key ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                                  {executingTool === key ? 'Running…' : 'Try it'}
                                </button>
                              </div>
                              <p className="mt-1.5 text-xs text-zinc-500 leading-relaxed line-clamp-3">
                                {tool.description}
                              </p>
                              {toolResult?.key === key && (
                                <div className="mt-2.5 rounded-lg border border-zinc-200 bg-white">
                                  <div className="flex items-center justify-between px-3 py-1.5 border-b border-zinc-100 text-xs">
                                    <span className={toolResult.result?.success === false ? 'text-rose-600' : 'text-emerald-700'}>
                                      {toolResult.result?.success === false ? 'Tool returned an error' : 'Output'}
                                    </span>
                                    <button onClick={() => setToolResult(null)} className="text-zinc-400 hover:text-zinc-700">
                                      <X className="w-3.5 h-3.5" />
                                    </button>
                                  </div>
                                  <pre className="px-3 py-2 text-[11px] text-zinc-700 font-mono overflow-x-auto whitespace-pre-wrap max-h-48 overflow-y-auto">
                                    {JSON.stringify(toolResult.result?.result ?? toolResult.result, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Add server */}
          {!showAddForm ? (
            <button
              onClick={() => setShowAddForm(true)}
              className="w-full flex items-center justify-center gap-2 rounded-2xl border border-dashed border-zinc-300 py-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50 hover:border-zinc-400 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add server
            </button>
          ) : (
            <form onSubmit={handleAddServer} className="rounded-2xl border border-zinc-200 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-zinc-900">Add an MCP server</h3>
                {servers.length > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddForm(false);
                      resetForm();
                    }}
                    className="text-xs text-zinc-500 hover:text-zinc-800"
                  >
                    Cancel
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className={labelClass}>Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Weather service"
                    className={inputClass}
                    required
                  />
                </div>
                <div>
                  <label className={labelClass}>Transport</label>
                  <select value={transport} onChange={(e) => setTransport(e.target.value)} className={inputClass}>
                    <option value="sse">SSE (MCP over Server-Sent Events)</option>
                    <option value="http">HTTP / REST endpoint</option>
                  </select>
                </div>
              </div>

              <div>
                <label className={labelClass}>Server URL</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="http://localhost:8005/sse"
                    className={`${inputClass} font-mono`}
                    required
                  />
                  <button
                    type="button"
                    onClick={handleTestConnection}
                    disabled={testing || !url}
                    className="shrink-0 inline-flex items-center gap-1.5 px-4 rounded-xl border border-zinc-300 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
                  >
                    {testing && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    {testing ? 'Testing' : 'Test'}
                  </button>
                </div>
              </div>

              <div>
                <label className={labelClass}>
                  Description <span className="font-normal text-zinc-400">(optional)</span>
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Live weather and forecasts for any city"
                  className={inputClass}
                />
                <p className="mt-1 text-xs text-zinc-400">
                  What the server is for. The chat uses this to decide when a question needs it; leave empty to use the
                  server&apos;s own MCP instructions.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className={labelClass}>Authentication</label>
                  <select value={authType} onChange={(e) => setAuthType(e.target.value)} className={inputClass}>
                    <option value="none">None</option>
                    <option value="bearer">Bearer token</option>
                    <option value="api_key">API key (X-API-Key header)</option>
                  </select>
                </div>
                {authType !== 'none' && (
                  <div>
                    <label className={labelClass}>{authType === 'bearer' ? 'Token' : 'API key'}</label>
                    <input
                      type="password"
                      value={authToken}
                      onChange={(e) => setAuthToken(e.target.value)}
                      placeholder="Stored on the server, never shown again"
                      className={`${inputClass} font-mono`}
                    />
                  </div>
                )}
              </div>

              {testResult && (
                <div
                  className={`rounded-xl border px-4 py-3 text-sm ${
                    testResult.status === 'connected' ? 'border-emerald-200 bg-emerald-50' : 'border-rose-200 bg-rose-50'
                  }`}
                >
                  <p className={`font-medium ${testResult.status === 'connected' ? 'text-emerald-800' : 'text-rose-800'}`}>
                    {testResult.status === 'connected'
                      ? `Connected · ${testResult.total_tools} tool${testResult.total_tools === 1 ? '' : 's'} found`
                      : "Couldn't connect"}
                  </p>
                  {testResult.error && <p className="mt-1 text-xs text-rose-700 font-mono break-words">{testResult.error}</p>}
                  {testResult.tools?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {testResult.tools.map((t: any) => (
                        <span key={t.name} className="px-2 py-0.5 rounded-md bg-white border border-emerald-200 text-emerald-800 font-mono text-[11px]">
                          {t.name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={saving || !name || !url}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-zinc-900 hover:bg-zinc-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                  {saving ? 'Connecting…' : 'Save and connect'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

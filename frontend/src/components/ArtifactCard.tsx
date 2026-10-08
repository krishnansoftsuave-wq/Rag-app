'use client';

import React, { useState } from 'react';
import {
  AlertTriangle,
  BarChart3,
  CalendarClock,
  Check,
  Copy,
  Download,
  ListChecks,
  Loader2,
  Maximize2,
  Network,
  RotateCw,
  Table2,
  X,
} from 'lucide-react';
import { Artifact, ArtifactState, ArtifactType } from '@/types';

interface ArtifactCardProps {
  state: ArtifactState;
  onRegenerate: (type: ArtifactType | 'auto') => void;
}

const TYPE_META: Record<ArtifactType, { label: string; icon: React.ElementType }> = {
  key_points: { label: 'Key Points', icon: ListChecks },
  table: { label: 'Table', icon: Table2 },
  timeline: { label: 'Timeline', icon: CalendarClock },
  chart: { label: 'Chart', icon: BarChart3 },
  mindmap: { label: 'Mind Map', icon: Network },
};

const asArray = (value: any): any[] => (Array.isArray(value) ? value : []);

const SourceTag: React.FC<{ source?: string }> = ({ source }) =>
  source ? (
    <span className="ml-1.5 inline-block text-[9px] font-mono text-indigo-600 bg-indigo-50 border border-indigo-100 px-1.5 py-0.5 rounded">
      {source}
    </span>
  ) : null;

const KeyPointsView: React.FC<{ data: Record<string, any> }> = ({ data }) => (
  <div className="space-y-2">
    {data.summary && <p className="text-slate-700">{data.summary}</p>}
    <ol className="space-y-1.5">
      {asArray(data.points).map((point, i) => (
        <li key={i} className="flex gap-2">
          <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold flex items-center justify-center shrink-0">
            {i + 1}
          </span>
          <span className="text-slate-700">
            {typeof point === 'string' ? point : point?.text}
            {typeof point !== 'string' && <SourceTag source={point?.source} />}
          </span>
        </li>
      ))}
    </ol>
  </div>
);

const TableView: React.FC<{ data: Record<string, any> }> = ({ data }) => {
  const columns = asArray(data.columns);
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full text-left text-[11px]">
        <thead className="bg-slate-100 text-slate-600 uppercase tracking-wide text-[10px]">
          <tr>
            {columns.map((col, i) => (
              <th key={i} className="px-3 py-2 font-bold whitespace-nowrap">
                {String(col)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {asArray(data.rows).map((row, r) => (
            <tr key={r} className="odd:bg-white even:bg-slate-50/60 align-top">
              {columns.map((_, c) => (
                <td key={c} className="px-3 py-2 text-slate-700">
                  {String(asArray(row)[c] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const TimelineView: React.FC<{ data: Record<string, any> }> = ({ data }) => (
  <ol className="relative border-l-2 border-indigo-200 ml-2 space-y-3">
    {asArray(data.events).map((event, i) => (
      <li key={i} className="ml-4">
        <span className="absolute -left-[7px] mt-1 w-3 h-3 rounded-full bg-indigo-500 border-2 border-white" />
        <span className="inline-block text-[10px] font-bold text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded-full">
          {event?.date}
        </span>
        {event?.title && <p className="font-semibold text-slate-800 mt-1">{event.title}</p>}
        {event?.detail && (
          <p className="text-slate-600">
            {event.detail}
            <SourceTag source={event?.source} />
          </p>
        )}
      </li>
    ))}
  </ol>
);

const ChartView: React.FC<{ data: Record<string, any> }> = ({ data }) => {
  const series = asArray(data.series).filter((p) => typeof p?.value === 'number');
  const max = Math.max(...series.map((p) => Math.abs(p.value)), 1);
  const unit = data.unit ? String(data.unit) : '';
  const format = (v: number) => {
    const n = v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    if (!unit) return n;
    return /^[$€£₹]/.test(unit) ? `${unit}${n}` : unit === '%' ? `${n}%` : `${n} ${unit}`;
  };
  return (
    <div className="space-y-2">
      {series.map((point, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-1/3 truncate text-slate-600" title={point.label}>
            {point.label}
          </span>
          <div className="flex-1 h-5 bg-slate-100 rounded-md overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-md"
              style={{ width: `${Math.max((Math.abs(point.value) / max) * 100, 2)}%` }}
            />
          </div>
          <span className="w-20 text-right font-mono font-semibold text-slate-800">{format(point.value)}</span>
        </div>
      ))}
    </div>
  );
};

const BRANCH_COLORS = ['border-indigo-400', 'border-purple-400', 'border-emerald-400', 'border-amber-400', 'border-sky-400', 'border-rose-400'];

const MindMapView: React.FC<{ data: Record<string, any> }> = ({ data }) => (
  <div className="space-y-3">
    <div className="flex justify-center">
      <span className="px-4 py-1.5 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold shadow-sm">
        {data.root || 'Topic'}
      </span>
    </div>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {asArray(data.branches).map((branch, i) => (
        <div key={i} className={`bg-white border border-slate-200 border-l-4 ${BRANCH_COLORS[i % BRANCH_COLORS.length]} rounded-lg p-2.5`}>
          <p className="font-bold text-slate-800 mb-1">{branch?.label}</p>
          <ul className="list-disc ml-4 space-y-0.5 text-slate-600">
            {asArray(branch?.children).map((child, c) => (
              <li key={c}>{String(child)}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  </div>
);

const ArtifactBody: React.FC<{ artifact: Artifact }> = ({ artifact }) => {
  const data = artifact.data || {};
  switch (artifact.type) {
    case 'table':
      return <TableView data={data} />;
    case 'timeline':
      return <TimelineView data={data} />;
    case 'chart':
      return <ChartView data={data} />;
    case 'mindmap':
      return <MindMapView data={data} />;
    default:
      return <KeyPointsView data={data} />;
  }
};

export const ArtifactCard: React.FC<ArtifactCardProps> = ({ state, onRegenerate }) => {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  if (state.status === 'loading') {
    return (
      <div className="mt-3 flex items-center gap-2 text-[11px] text-indigo-700 bg-indigo-50/70 border border-indigo-100 rounded-xl px-3 py-2">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        <span>Standalone MCP server is building an artifact from the retrieved context...</span>
      </div>
    );
  }

  if (state.status === 'error' || !state.artifact) {
    return (
      <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-500 bg-slate-100/70 border border-slate-200 rounded-xl px-3 py-2">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
        <span className="flex-1">Artifact unavailable: {state.error || 'unknown error'}</span>
        <button
          onClick={() => onRegenerate('auto')}
          className="flex items-center gap-1 text-indigo-600 hover:text-indigo-800 font-semibold"
        >
          <RotateCw className="w-3 h-3" />
          Retry
        </button>
      </div>
    );
  }

  const artifact = state.artifact;
  const meta = TYPE_META[artifact.type] || TYPE_META.key_points;
  const Icon = meta.icon;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(artifact.markdown || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleDownload = () => {
    const blob = new Blob([artifact.markdown || ''], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${artifact.title.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').toLowerCase() || 'artifact'}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const header = (
    <div className="flex items-start justify-between gap-2">
      <div className="flex items-start gap-2 min-w-0">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-indigo-600 to-purple-600 text-white flex items-center justify-center shrink-0">
          <Icon className="w-3.5 h-3.5" />
        </div>
        <div className="min-w-0">
          <p className="font-bold text-slate-800 truncate">{artifact.title}</p>
          <p className="text-[10px] text-slate-500 truncate">
            {meta.label} artifact · via {state.serverName || 'MCP server'} · {artifact.generated_by}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <button onClick={handleCopy} title="Copy as Markdown" className="p-1.5 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800">
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
        <button onClick={handleDownload} title="Download .md" className="p-1.5 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800">
          <Download className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => setExpanded(!expanded)}
          title={expanded ? 'Close' : 'Expand'}
          className="p-1.5 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800"
        >
          {expanded ? <X className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
        </button>
      </div>
    </div>
  );

  const typeSwitcher = (
    <div className="flex flex-wrap items-center gap-1.5">
      {(Object.keys(TYPE_META) as ArtifactType[]).map((type) => {
        const TypeIcon = TYPE_META[type].icon;
        const active = type === artifact.type;
        return (
          <button
            key={type}
            disabled={active}
            onClick={() => onRegenerate(type)}
            className={`flex items-center gap-1 text-[10px] px-2 py-1 rounded-full border transition-colors ${
              active
                ? 'bg-indigo-600 text-white border-indigo-600'
                : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:text-indigo-700'
            }`}
          >
            <TypeIcon className="w-3 h-3" />
            {TYPE_META[type].label}
          </button>
        );
      })}
    </div>
  );

  const sourcesLine =
    artifact.source_files?.length > 0 ? (
      <p className="text-[10px] text-slate-400">Sources: {artifact.source_files.join(', ')}</p>
    ) : null;

  return (
    <>
      <div className="mt-3 bg-white border border-indigo-100 rounded-xl p-3 space-y-2.5 shadow-sm">
        {header}
        {artifact.description && <p className="text-[11px] text-slate-500">{artifact.description}</p>}
        <div className="max-h-80 overflow-y-auto pr-1">
          <ArtifactBody artifact={artifact} />
        </div>
        {typeSwitcher}
        {sourcesLine}
      </div>

      {expanded && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={() => setExpanded(false)}
        >
          <div
            className="bg-white text-slate-800 text-xs rounded-2xl shadow-2xl w-full max-w-4xl max-h-[88vh] overflow-y-auto p-5 space-y-3"
            onClick={(e) => e.stopPropagation()}
          >
            {header}
            {artifact.description && <p className="text-slate-500">{artifact.description}</p>}
            <ArtifactBody artifact={artifact} />
            {typeSwitcher}
            {sourcesLine}
          </div>
        </div>
      )}
    </>
  );
};

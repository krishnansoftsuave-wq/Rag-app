'use client';

import React from 'react';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';

// The app has no Tailwind typography plugin, so markdown elements are styled here. Sizes are relative (em) so the
// same markdown reads well in the chat (15px) and in small cards (11px).
const components: Components = {
  p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
  h1: ({ children }) => <h3 className="text-[1.25em] leading-snug font-semibold text-zinc-900 mt-5 mb-2 first:mt-0">{children}</h3>,
  h2: ({ children }) => <h3 className="text-[1.15em] leading-snug font-semibold text-zinc-900 mt-5 mb-2 first:mt-0">{children}</h3>,
  h3: ({ children }) => <h4 className="text-[1.05em] font-semibold text-zinc-900 mt-4 mb-1.5 first:mt-0">{children}</h4>,
  ul: ({ children }) => <ul className="list-disc pl-6 mb-3 space-y-1 last:mb-0 marker:text-zinc-400">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-6 mb-3 space-y-1 last:mb-0 marker:text-zinc-500">{children}</ol>,
  strong: ({ children }) => <strong className="font-semibold text-zinc-900">{children}</strong>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-indigo-600 underline underline-offset-2 hover:text-indigo-800">
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="font-mono text-[0.875em] bg-zinc-100 text-zinc-800 px-1.5 py-0.5 rounded-md">{children}</code>
  ),
  pre: ({ children }) => (
    <pre className="bg-zinc-900 text-zinc-100 rounded-xl p-4 overflow-x-auto mb-3 text-[0.875em] leading-relaxed [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-zinc-100">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => <blockquote className="border-l-2 border-zinc-300 pl-4 text-zinc-600 mb-3">{children}</blockquote>,
  hr: () => <hr className="my-5 border-zinc-200" />,
  table: ({ children }) => (
    <div className="overflow-x-auto mb-3 rounded-xl border border-zinc-200 bg-white">
      <table className="w-full text-left text-[0.9em] border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-zinc-50 text-zinc-700">{children}</thead>,
  th: ({ children }) => <th className="px-3 py-2 font-semibold border-b border-zinc-200 align-bottom">{children}</th>,
  td: ({ children }) => <td className="px-3 py-2 border-t border-zinc-100 align-top">{children}</td>,
};

interface MarkdownMessageProps {
  children: string;
}

/**
 * Renders LLM answers: GitHub-flavored markdown (tables, task lists, strikethrough) plus the
 * small inline HTML models emit (e.g. <br> inside table cells), sanitized so scripts and
 * event handlers never reach the DOM.
 */
export const MarkdownMessage: React.FC<MarkdownMessageProps> = ({ children }) => (
  <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw, rehypeSanitize]} components={components}>
    {children}
  </ReactMarkdown>
);

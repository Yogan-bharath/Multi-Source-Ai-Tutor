'use client';
import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Check } from 'lucide-react';
import { parseProvenanceTags } from './ProvenanceTag';

function renderTextWithTags(text: string): React.ReactNode {
  const parts = parseProvenanceTags(text);
  return <>{parts}</>;
}

interface AnswerCardProps {
  answer: string;
}

function CodeBlock({ children, className }: { children: React.ReactNode; className?: string }) {
  const [copied, setCopied] = useState(false);
  const codeText = String(children).replace(/\n$/, '');
  const match = /language-(\w+)/.exec(className || '');
  const lang = match ? match[1] : '';

  const handleCopy = () => {
    navigator.clipboard.writeText(codeText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className="relative my-3 rounded-lg overflow-hidden font-mono text-[12px]"
      style={{
        background: 'var(--canvas-alt)',
        border: '1px solid var(--border)',
      }}
    >
      <div
        className="flex items-center justify-between px-3.5 py-1.5 text-[11px]"
        style={{
          background: 'var(--surface)',
          borderBottom: '1px solid var(--border)',
          color: 'var(--ink-muted)',
        }}
      >
        <span>{lang || 'code'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 transition-opacity hover:opacity-80"
          style={{ color: 'var(--ink-muted)' }}
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5" style={{ color: 'var(--positive)' }} />
              <span style={{ color: 'var(--positive)' }}>Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto" style={{ color: 'var(--ink)' }}>
        <code>{children}</code>
      </pre>
    </div>
  );
}

export function AnswerCard({ answer }: AnswerCardProps) {
  return (
    <div className="max-w-none text-[13px] leading-relaxed" style={{ color: 'var(--ink)' }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => (
            <p className="mb-3 leading-relaxed" style={{ color: 'var(--ink)' }}>
              {typeof children === 'string' ? renderTextWithTags(children) : children}
            </p>
          ),
          li: ({ children }) => (
            <li className="my-1" style={{ color: 'var(--ink)' }}>
              {typeof children === 'string' ? renderTextWithTags(children) : children}
            </li>
          ),
          ul: ({ children }) => <ul className="list-disc pl-5 my-2 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 my-2 space-y-1">{children}</ol>,
          strong: ({ children }) => (
            <strong className="font-semibold" style={{ color: 'var(--ink)' }}>
              {children}
            </strong>
          ),
          h2: ({ children }) => (
            <h2
              className="text-[15px] font-bold mt-4 mb-2 pb-1"
              style={{ color: 'var(--ink)', borderBottom: '1px solid var(--border)' }}
            >
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-[13px] font-bold mt-3 mb-1" style={{ color: 'var(--ink)' }}>
              {children}
            </h3>
          ),
          table: ({ children }) => (
            <div
              className="overflow-x-auto my-3 rounded-lg"
              style={{ border: '1px solid var(--border)' }}
            >
              <table className="w-full text-left text-[12px] border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead
              style={{
                background: 'var(--canvas-alt)',
                borderBottom: '1px solid var(--border)',
              }}
            >
              {children}
            </thead>
          ),
          th: ({ children }) => (
            <th className="p-2.5 font-semibold" style={{ color: 'var(--ink)' }}>
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td
              className="p-2.5"
              style={{
                borderBottom: '1px solid var(--border-muted)',
                color: 'var(--ink)',
              }}
            >
              {children}
            </td>
          ),
          code: ({ children, className }) => {
            const isBlock = className?.includes('language-');
            return isBlock ? (
              <CodeBlock className={className}>{children}</CodeBlock>
            ) : (
              <code
                className="rounded px-1.5 py-0.5 text-[11px] font-mono"
                style={{
                  background: 'var(--canvas-alt)',
                  color: 'var(--accent)',
                  border: '1px solid var(--border)',
                }}
              >
                {children}
              </code>
            );
          },
          blockquote: ({ children }) => (
            <blockquote
              className="pl-3 italic my-2"
              style={{
                borderLeft: '3px solid var(--accent)',
                color: 'var(--ink-muted)',
              }}
            >
              {children}
            </blockquote>
          ),
        }}
      >
        {answer}
      </ReactMarkdown>
    </div>
  );
}

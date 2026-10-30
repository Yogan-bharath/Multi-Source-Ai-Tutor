'use client';
import React, { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink, AlertTriangle, CheckCircle, GitMerge } from 'lucide-react';
import type { ChatResponse } from '@/types';
import { ProvenanceTag } from './ProvenanceTag';

const CLASSIFICATION_CONFIG = {
  agree: {
    icon: CheckCircle,
    label: 'Sources Agree',
    color: 'var(--positive)',
    bg: 'var(--positive-muted)',
    border: 'var(--positive)',
    badgeBg: 'rgba(45, 157, 120, 0.18)',
    badgeColor: 'var(--positive)',
  },
  partial: {
    icon: GitMerge,
    label: 'Partial Overlap',
    color: 'var(--caution)',
    bg: 'var(--caution-muted)',
    border: 'var(--caution)',
    badgeBg: 'rgba(212, 135, 13, 0.18)',
    badgeColor: 'var(--caution)',
  },
  conflict: {
    icon: AlertTriangle,
    label: 'Sources Conflict',
    color: 'var(--negative)',
    bg: 'var(--negative-muted)',
    border: 'var(--negative)',
    badgeBg: 'rgba(239, 90, 74, 0.18)',
    badgeColor: 'var(--negative)',
  },
} as const;

interface SourcePanelProps {
  chatResponse: ChatResponse;
}

export function SourcePanel({ chatResponse }: SourcePanelProps) {
  const [expandedSource, setExpandedSource] = useState<string | null>(null);
  const { classification, source_summaries, retrieved_chunks } = chatResponse;
  const config = CLASSIFICATION_CONFIG[classification.classification] || CLASSIFICATION_CONFIG.agree;
  const Icon = config.icon;

  return (
    <div className="flex flex-col gap-3 text-xs">
      {/* Classification Badge */}
      <div
        className="rounded-xl p-3.5"
        style={{
          background: config.bg,
          border: `1px solid ${config.border}`,
        }}
      >
        <div className="flex items-center gap-2 mb-1.5">
          <Icon className="w-4 h-4 flex-shrink-0" style={{ color: config.color }} />
          <span className="font-semibold text-[13px]" style={{ color: config.color }}>
            {config.label}
          </span>
          <span
            className="ml-auto text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold"
            style={{
              background: config.badgeBg,
              color: config.badgeColor,
            }}
          >
            {Math.round(classification.confidence * 100)}% confidence
          </span>
        </div>
        <p className="text-[12px] leading-relaxed" style={{ color: 'var(--ink)' }}>
          {classification.reasoning}
        </p>
        {classification.key_differences && classification.key_differences !== 'None' && (
          <div className="mt-2.5 pt-2" style={{ borderTop: '1px solid var(--border-muted)' }}>
            <p className="text-[10px] font-semibold uppercase tracking-wider mb-0.5" style={{ color: 'var(--ink-muted)' }}>
              Key Differences
            </p>
            <p className="text-[12px]" style={{ color: 'var(--ink)' }}>
              {classification.key_differences}
            </p>
          </div>
        )}
      </div>

      {/* Per-Source Perspectives */}
      <div className="space-y-2 mt-1">
        <h4 className="text-[11px] font-bold uppercase tracking-wider px-1" style={{ color: 'var(--ink-muted)' }}>
          Source Perspectives ({source_summaries?.length || 0})
        </h4>
        {source_summaries?.map((s) => (
          <div
            key={s.source_id}
            className="rounded-lg overflow-hidden transition-colors"
            style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
            }}
          >
            <button
              className="w-full flex items-center gap-2.5 p-2.5 text-left transition-colors duration-100 hover:opacity-90"
              style={{ background: 'transparent' }}
              onClick={() => setExpandedSource(expandedSource === s.source_id ? null : s.source_id)}
            >
              <ProvenanceTag sourceId={s.source_id} />
              <span className="flex-1 text-[12px] font-medium truncate" style={{ color: 'var(--ink)' }}>
                {s.title}
              </span>
              {expandedSource === s.source_id ? (
                <ChevronUp className="w-3.5 h-3.5" style={{ color: 'var(--ink-faint)' }} />
              ) : (
                <ChevronDown className="w-3.5 h-3.5" style={{ color: 'var(--ink-faint)' }} />
              )}
            </button>
            {expandedSource === s.source_id && (
              <div
                className="px-3 pb-3 space-y-2.5 pt-2"
                style={{
                  borderTop: '1px solid var(--border-muted)',
                  background: 'var(--canvas-alt)',
                }}
              >
                <p className="text-[12px] leading-relaxed" style={{ color: 'var(--ink)' }}>
                  {s.summary}
                </p>
                {s.url && !s.url.startsWith('file://') && !s.url.startsWith('text://') && (
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[11px] font-medium transition-colors hover:underline"
                    style={{ color: 'var(--accent)' }}
                  >
                    <ExternalLink className="w-3 h-3" />
                    <span>Open Reference</span>
                  </a>
                )}
                {/* Retrieved Vectors */}
                {retrieved_chunks?.[s.source_id]?.length > 0 && (
                  <div className="mt-2.5 pt-2" style={{ borderTop: '1px solid var(--border-muted)' }}>
                    <p className="text-[10px] font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--ink-muted)' }}>
                      Matched Vectors
                    </p>
                    <div className="space-y-1.5">
                      {retrieved_chunks[s.source_id].map((chunk, i) => (
                        <div
                          key={i}
                          className="rounded-md p-2 text-[11px]"
                          style={{
                            background: 'var(--surface)',
                            border: '1px solid var(--border)',
                            color: 'var(--ink-muted)',
                          }}
                        >
                          <span className="font-mono text-[10px] mr-1.5" style={{ color: 'var(--accent)' }}>
                            sim: {chunk.score.toFixed(3)}
                          </span>
                          <span className="line-clamp-2">{chunk.text.slice(0, 160)}…</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

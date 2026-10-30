import React from 'react';

// Scholarly editorial provenance badge colors that work in both light & dark modes
const SOURCE_STYLES: Record<string, { bg: string; color: string; border: string }> = {
  'Source A': { bg: 'rgba(232, 97, 77, 0.12)', color: 'var(--accent)', border: 'rgba(232, 97, 77, 0.35)' },
  'Source B': { bg: 'rgba(45, 157, 120, 0.12)', color: 'var(--positive)', border: 'rgba(45, 157, 120, 0.35)' },
  'Source C': { bg: 'rgba(212, 135, 13, 0.12)', color: 'var(--caution)', border: 'rgba(212, 135, 13, 0.35)' },
  'Source D': { bg: 'rgba(139, 92, 246, 0.12)', color: '#8B5CF6', border: 'rgba(139, 92, 246, 0.35)' },
  'Source E': { bg: 'rgba(236, 72, 153, 0.12)', color: '#EC4899', border: 'rgba(236, 72, 153, 0.35)' },
  'Source F': { bg: 'rgba(6, 182, 212, 0.12)', color: '#06B6D4', border: 'rgba(6, 182, 212, 0.35)' },
  'Source G': { bg: 'rgba(99, 102, 241, 0.12)', color: '#6366F1', border: 'rgba(99, 102, 241, 0.35)' },
  'Source H': { bg: 'rgba(20, 184, 166, 0.12)', color: '#14B8A6', border: 'rgba(20, 184, 166, 0.35)' },
};

const PALETTE = [
  { bg: 'rgba(232, 97, 77, 0.12)', color: 'var(--accent)', border: 'rgba(232, 97, 77, 0.35)' },
  { bg: 'rgba(45, 157, 120, 0.12)', color: 'var(--positive)', border: 'rgba(45, 157, 120, 0.35)' },
  { bg: 'rgba(212, 135, 13, 0.12)', color: 'var(--caution)', border: 'rgba(212, 135, 13, 0.35)' },
  { bg: 'rgba(139, 92, 246, 0.12)', color: '#8B5CF6', border: 'rgba(139, 92, 246, 0.35)' },
  { bg: 'rgba(236, 72, 153, 0.12)', color: '#EC4899', border: 'rgba(236, 72, 153, 0.35)' },
  { bg: 'rgba(6, 182, 212, 0.12)', color: '#06B6D4', border: 'rgba(6, 182, 212, 0.35)' },
  { bg: 'rgba(99, 102, 241, 0.12)', color: '#6366F1', border: 'rgba(99, 102, 241, 0.35)' },
  { bg: 'rgba(20, 184, 166, 0.12)', color: '#14B8A6', border: 'rgba(20, 184, 166, 0.35)' },
];

export function getSourceStyle(sourceId: string) {
  if (SOURCE_STYLES[sourceId]) return SOURCE_STYLES[sourceId];
  let hash = 0;
  for (let i = 0; i < sourceId.length; i++) {
    hash = (hash << 5) - hash + sourceId.charCodeAt(i);
  }
  const idx = Math.abs(hash) % PALETTE.length;
  return PALETTE[idx];
}

export function ProvenanceTag({ sourceId }: { sourceId: string }) {
  const style = getSourceStyle(sourceId);
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-mono font-semibold mx-0.5 transition-colors align-baseline"
      style={{
        background: style.bg,
        color: style.color,
        border: `1px solid ${style.border}`,
      }}
    >
      {sourceId}
    </span>
  );
}

/**
 * Parse markdown text and convert [Source X] and [Source X, Source Y] patterns
 * into colored ProvenanceTag components.
 */
export function parseProvenanceTags(text: string): React.ReactNode[] {
  const pattern = /\[(Source [A-Za-z0-9]+(?:\s*,\s*Source [A-Za-z0-9]+)*)\]/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const sources = match[1].split(',').map((s) => s.trim());
    sources.forEach((src, i) => {
      parts.push(<ProvenanceTag key={`${match!.index}-${i}`} sourceId={src} />);
    });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

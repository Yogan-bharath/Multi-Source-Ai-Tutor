'use client';
import React from 'react';
import {
  Sparkles,
  PanelRightClose,
  PanelRight,
  FileText,
  Layers,
  HelpCircle,
  Network,
  BookOpen,
  Table,
  ChevronRight,
} from 'lucide-react';
import type { StudioToolType } from '@/types';

interface StudioSidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onSelectTool: (tool: StudioToolType) => void;
  sourceCount: number;
}

const STUDIO_TOOLS: Array<{
  id: StudioToolType;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
}> = [
  {
    id: 'summary',
    title: 'Summary',
    description: 'Executive overview and key takeaways.',
    icon: FileText,
  },
  {
    id: 'flashcards',
    title: 'Flashcards',
    description: 'Q&A cards for active recall practice.',
    icon: Layers,
  },
  {
    id: 'quiz',
    title: 'Quiz',
    description: 'Multiple-choice test with explanations.',
    icon: HelpCircle,
  },
  {
    id: 'mindmap',
    title: 'Mind Map',
    description: 'Concept hierarchy across themes.',
    icon: Network,
  },
  {
    id: 'notes',
    title: 'Study Notes',
    description: 'Organized notes, formulas, and key points.',
    icon: BookOpen,
  },
  {
    id: 'datatable',
    title: 'Data Table',
    description: 'Structured comparison across sources.',
    icon: Table,
  },
];

export function StudioSidebar({
  isCollapsed,
  onToggleCollapse,
  onSelectTool,
  sourceCount,
}: StudioSidebarProps) {
  // Collapsed slim rail
  if (isCollapsed) {
    return (
      <div
        className="w-12 flex flex-col items-center py-3 flex-shrink-0 select-none"
        style={{ borderLeft: '1px solid var(--border)', background: 'var(--surface)' }}
      >
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-md transition-colors duration-150 mb-4"
          style={{ color: 'var(--ink-muted)' }}
          title="Expand Learning Studio"
        >
          <PanelRight className="w-4 h-4" />
        </button>

        <div
          onClick={onToggleCollapse}
          className="p-2 rounded-md transition-colors duration-150 cursor-pointer"
          style={{ background: 'var(--canvas-alt)', color: 'var(--accent)' }}
          title="Learning Studio"
        >
          <Sparkles className="w-4 h-4" />
        </div>
      </div>
    );
  }

  // Expanded sidebar
  return (
    <div
      className="w-72 lg:w-[280px] flex flex-col h-full flex-shrink-0"
      style={{ borderLeft: '1px solid var(--border)', background: 'var(--surface)' }}
    >
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4" style={{ color: 'var(--accent)' }} />
          <h2 className="text-[13px] font-semibold" style={{ color: 'var(--ink)' }}>
            Learning Studio
          </h2>
        </div>
        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-md transition-colors duration-150"
          style={{ color: 'var(--ink-faint)' }}
          title="Collapse Studio sidebar"
        >
          <PanelRightClose className="w-4 h-4" />
        </button>
      </div>

      {/* Source count notice */}
      <div
        className="px-4 py-2.5 text-[12px]"
        style={{ borderBottom: '1px solid var(--border-muted)', color: 'var(--ink-muted)' }}
      >
        AI tools grounded in{' '}
        <span className="font-semibold" style={{ color: 'var(--ink)' }}>{sourceCount} source{sourceCount === 1 ? '' : 's'}</span>
      </div>

      {/* Tool List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {STUDIO_TOOLS.map((tool) => {
          const Icon = tool.icon;
          return (
            <button
              key={tool.id}
              onClick={() => onSelectTool(tool.id)}
              className="w-full group p-3 rounded-md cursor-pointer transition-colors duration-100 text-left flex items-start gap-3"
              style={{ border: '1px solid transparent' }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.background = 'var(--canvas-alt)';
                (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = 'transparent';
                (e.currentTarget as HTMLElement).style.borderColor = 'transparent';
              }}
            >
              <div
                className="w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0"
                style={{ background: 'var(--accent-muted)', color: 'var(--accent)' }}
              >
                <Icon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <h3 className="text-[13px] font-medium" style={{ color: 'var(--ink)' }}>
                    {tool.title}
                  </h3>
                  <ChevronRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity duration-150" style={{ color: 'var(--ink-faint)' }} />
                </div>
                <p className="text-[12px] mt-0.5 line-clamp-2 leading-relaxed" style={{ color: 'var(--ink-muted)' }}>
                  {tool.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Footer */}
      <div
        className="p-3 text-[11px] text-center"
        style={{ borderTop: '1px solid var(--border)', color: 'var(--ink-faint)' }}
      >
        Powered by Groq × FAISS
      </div>
    </div>
  );
}

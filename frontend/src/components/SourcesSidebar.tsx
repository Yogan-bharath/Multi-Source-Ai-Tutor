'use client';
import React, { useState } from 'react';
import {
  BookOpen,
  PanelLeftClose,
  PanelLeft,
  Plus,
  Globe,
  FileText,
  File,
  ExternalLink,
  Trash2,
  RotateCcw,
  MoreVertical,
} from 'lucide-react';
import type { SourceInfo } from '@/types';
import { useModal } from '@/context/ModalContext';

interface SourcesSidebarProps {
  sources: SourceInfo[];
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onOpenAddModal: () => void;
  onDeleteSource: (sourceId: string, originalUrl?: string) => Promise<void>;
  onRetrySource: (source: SourceInfo) => Promise<void>;
  loading?: boolean;
}

export function SourcesSidebar({
  sources,
  isCollapsed,
  onToggleCollapse,
  onOpenAddModal,
  onDeleteSource,
  onRetrySource,
  loading = false,
}: SourcesSidebarProps) {
  const { confirmModal } = useModal();
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const getSourceIcon = (source: SourceInfo) => {
    const url = (source.original_url || source.url || '').toLowerCase();
    const type = source.source_type || '';
    if (type === 'pdf' || url.endsWith('.pdf')) {
      return <FileText className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--negative)' }} />;
    }
    if (type === 'text' || url.startsWith('text://')) {
      return <File className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--caution)' }} />;
    }
    return <Globe className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--accent)' }} />;
  };

  const getSourceTypeName = (source: SourceInfo) => {
    const url = (source.original_url || source.url || '').toLowerCase();
    const type = source.source_type || '';
    if (type === 'pdf' || url.endsWith('.pdf')) return 'PDF';
    if (type === 'text' || url.startsWith('text://')) return 'Note';
    return 'Web';
  };

  // Collapsed slim rail
  if (isCollapsed) {
    return (
      <div
        className="w-12 flex flex-col items-center py-3 flex-shrink-0 select-none"
        style={{ borderRight: '1px solid var(--border)', background: 'var(--surface)' }}
      >
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-md transition-colors duration-150 mb-4 hover:opacity-80"
          style={{ color: 'var(--ink-muted)' }}
          title="Expand Sources sidebar"
        >
          <PanelLeft className="w-4 h-4" />
        </button>

        <div className="relative cursor-pointer" onClick={onToggleCollapse}>
          <div
            className="p-2 rounded-md transition-colors duration-150"
            style={{ background: 'var(--canvas-alt)', color: 'var(--accent)' }}
          >
            <BookOpen className="w-4 h-4" />
          </div>
          {sources.length > 0 && (
            <span
              className="absolute -top-1 -right-1 text-[9px] font-bold w-4 h-4 rounded-full flex items-center justify-center text-white"
              style={{ background: 'var(--accent)' }}
            >
              {sources.length}
            </span>
          )}
        </div>

        <div className="mt-auto">
          <button
            onClick={onOpenAddModal}
            className="p-2 rounded-md transition-colors duration-150 hover:opacity-80"
            style={{ color: 'var(--ink-muted)' }}
            title="Add Sources"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  // Expanded sidebar
  return (
    <div
      className="w-72 lg:w-[280px] flex flex-col h-full flex-shrink-0"
      style={{ borderRight: '1px solid var(--border)', background: 'var(--surface)' }}
    >
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4" style={{ color: 'var(--ink-muted)' }} />
          <h2 className="text-[13px] font-semibold" style={{ color: 'var(--ink)' }}>
            Sources
          </h2>
          <span
            className="text-[11px] font-semibold px-1.5 py-0.5 rounded"
            style={{ background: 'var(--canvas-alt)', color: 'var(--ink-muted)' }}
          >
            {sources.length}
          </span>
        </div>
        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-md transition-colors duration-150 hover:opacity-80"
          style={{ color: 'var(--ink-faint)' }}
          title="Collapse Sources sidebar"
        >
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      {/* Add Sources Button */}
      <div className="p-3" style={{ borderBottom: '1px solid var(--border-muted)' }}>
        <button
          onClick={onOpenAddModal}
          className="w-full py-2 px-3 rounded-md text-[13px] font-semibold flex items-center justify-center gap-2 transition-opacity duration-150 hover:opacity-90"
          style={{ background: 'var(--accent)', color: 'var(--accent-ink)' }}
        >
          <Plus className="w-4 h-4" />
          <span>Add Sources</span>
        </button>
      </div>

      {/* Source List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {sources.length === 0 ? (
          <div className="py-12 text-center px-4">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center mx-auto mb-2.5"
              style={{ background: 'var(--canvas-alt)' }}
            >
              <BookOpen className="w-5 h-5" style={{ color: 'var(--ink-faint)' }} />
            </div>
            <p className="text-[13px] font-medium" style={{ color: 'var(--ink)' }}>No sources added</p>
            <p className="text-[12px] mt-1 max-w-[200px] mx-auto" style={{ color: 'var(--ink-faint)' }}>
              Add web links, documents, or notes to ground your tutor's answers.
            </p>
          </div>
        ) : (
          sources.map((source, index) => {
            const sid = source.source_id || (source as any)._id || (source as any).id || source.original_url || `Source-${index}`;
            const isMenuOpen = activeMenuId === sid;
            const isFailed = source.status === 'failed';
            const isRetrying = retryingId === sid;
            const targetId =
              (source as any)._id ||
              (source as any).id ||
              source.source_id ||
              source.original_url ||
              sid;

            return (
              <div
                key={sid}
                className="relative rounded-lg p-2.5 text-[13px] transition-colors duration-100 group"
                style={{
                  background: isFailed ? 'var(--negative-muted)' : 'var(--canvas-alt)',
                  border: `1px solid ${isFailed ? 'var(--negative)' : 'var(--border)'}`,
                }}
              >
                <div className="flex items-start gap-2.5">
                  <div className="mt-0.5">{getSourceIcon(source)}</div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-[13px] truncate leading-snug" style={{ color: 'var(--ink)' }}>
                      {source.title || source.original_url || 'Untitled Source'}
                    </p>
                    <div className="flex items-center gap-2 mt-1 text-[11px]" style={{ color: 'var(--ink-faint)' }}>
                      <span
                        className="px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold"
                        style={{ background: 'var(--surface)', color: 'var(--ink-muted)' }}
                      >
                        {getSourceTypeName(source)}
                      </span>
                      {source.chunk_count ? (
                        <span className="font-mono">{source.chunk_count} chunks</span>
                      ) : null}
                      {isFailed ? (
                        <span className="font-semibold" style={{ color: 'var(--negative)' }}>Failed</span>
                      ) : (
                        <span className="font-semibold" style={{ color: 'var(--positive)' }}>Indexed</span>
                      )}
                    </div>
                  </div>

                  {/* Context menu */}
                  <div className="relative" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => setActiveMenuId(isMenuOpen ? null : sid)}
                      className="p-1 rounded transition-colors duration-150 hover:opacity-80"
                      style={{ color: 'var(--ink-faint)' }}
                    >
                      <MoreVertical className="w-3.5 h-3.5" />
                    </button>

                    {isMenuOpen && (
                      <div
                        className="absolute right-0 top-full mt-1 w-40 rounded-lg shadow-modal py-1 z-30 text-[13px] animate-scaleIn"
                        style={{ background: 'var(--surface-overlay)', border: '1px solid var(--border)' }}
                      >
                        {source.original_url &&
                          !source.original_url.startsWith('file://') &&
                          !source.original_url.startsWith('text://') && (
                            <a
                              href={source.original_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={() => setActiveMenuId(null)}
                              className="flex items-center gap-2 px-3 py-1.5 transition-colors duration-100 hover:opacity-80"
                              style={{ color: 'var(--ink)' }}
                            >
                              <ExternalLink className="w-3.5 h-3.5" />
                              <span>Open Webpage</span>
                            </a>
                          )}
                        {isFailed && (
                          <button
                            onClick={async () => {
                              setActiveMenuId(null);
                              setRetryingId(sid);
                              try {
                                await onRetrySource(source);
                              } finally {
                                setRetryingId(null);
                              }
                            }}
                            disabled={isRetrying}
                            className="w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors duration-100 hover:opacity-80"
                            style={{ color: 'var(--accent)' }}
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                            <span>Retry Indexing</span>
                          </button>
                        )}
                        <button
                          onClick={async () => {
                            setActiveMenuId(null);
                            const ok = await confirmModal({
                              title: 'Remove Source',
                              message: `Are you sure you want to remove "${source.title || source.original_url || 'this source'}" from this project?`,
                              confirmText: 'Remove Source',
                              cancelText: 'Cancel',
                              type: 'danger',
                            });
                            if (ok) {
                              await onDeleteSource(targetId, source.original_url || source.url);
                            }
                          }}
                          className="w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors duration-100 hover:opacity-80"
                          style={{ color: 'var(--negative)' }}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          <span>Remove Source</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Direct quick-action row for failed sources */}
                {isFailed && (
                  <div
                    className="mt-2 pt-2 flex items-center justify-between gap-2"
                    style={{ borderTop: '1px solid var(--border-muted)' }}
                  >
                    <span className="text-[11px] truncate flex-1" style={{ color: 'var(--negative)' }} title={source.error || 'Failed to index'}>
                      {source.error || 'Failed to index URL'}
                    </span>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <button
                        onClick={async (e) => {
                          e.stopPropagation();
                          setRetryingId(sid);
                          try {
                            await onRetrySource(source);
                          } finally {
                            setRetryingId(null);
                          }
                        }}
                        disabled={isRetrying}
                        className="px-2 py-0.5 text-[11px] font-medium rounded flex items-center gap-1 transition-opacity hover:opacity-80"
                        style={{ background: 'var(--accent-muted)', color: 'var(--accent)' }}
                        title="Retry indexing"
                      >
                        <RotateCcw className={`w-3 h-3 ${isRetrying ? 'animate-spin' : ''}`} />
                        <span>Retry</span>
                      </button>
                      <button
                        onClick={async (e) => {
                          e.stopPropagation();
                          const ok = await confirmModal({
                            title: 'Remove Failed Link',
                            message: `Remove "${source.title || source.original_url || 'this failed source'}" from your notebook?`,
                            confirmText: 'Remove',
                            cancelText: 'Cancel',
                            type: 'danger',
                          });
                          if (ok) {
                            await onDeleteSource(targetId, source.original_url || source.url);
                          }
                        }}
                        className="p-1 rounded transition-colors hover:opacity-80"
                        style={{ color: 'var(--negative)', background: 'var(--negative-muted)' }}
                        title="Delete failed link"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div
        className="p-3 text-[11px] flex items-center justify-between"
        style={{ borderTop: '1px solid var(--border)', color: 'var(--ink-faint)' }}
      >
        <span>Knowledge Base</span>
        <span className="font-mono" style={{ color: 'var(--ink-muted)' }}>
          {sources.filter((s) => s.status === 'success').length} verified
        </span>
      </div>
    </div>
  );
}

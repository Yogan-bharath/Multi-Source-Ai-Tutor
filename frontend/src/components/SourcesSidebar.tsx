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
  Youtube,
  Folder,
  Search,
  Edit2,
  Check,
  X,
  Clock,
  MessageSquare,
} from 'lucide-react';
import type { SourceInfo, Project, Conversation } from '@/types';
import { useModal } from '@/context/ModalContext';

interface SourcesSidebarProps {
  sources: SourceInfo[];
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onOpenAddModal: () => void;
  onDeleteSource: (sourceId: string, originalUrl?: string) => Promise<void>;
  onRetrySource: (source: SourceInfo) => Promise<void>;
  loading?: boolean;
  // Recent Notebooks management
  projects?: Project[];
  activeProject?: Project | null;
  onSelectProject?: (project: Project) => void;
  onRenameProject?: (projectId: string, newName: string) => Promise<void>;
  onDeleteProject?: (projectId: string) => Promise<void>;
  onCreateProject?: () => void;
  // Conversations management
  conversations?: Conversation[];
  activeConversation?: Conversation | null;
  onSelectConversation?: (conversation: Conversation) => void;
  onNewChat?: () => void;
  onRenameConversation?: (id: string, newTitle: string) => Promise<void>;
  onDeleteConversation?: (id: string) => Promise<void>;
}

function formatRelativeTime(dateStr?: string): string {
  if (!dateStr) return '';
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (diffSec < 60) return 'Just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

export function SourcesSidebar({
  sources,
  isCollapsed,
  onToggleCollapse,
  onOpenAddModal,
  onDeleteSource,
  onRetrySource,
  loading = false,
  projects = [],
  activeProject = null,
  onSelectProject,
  onRenameProject,
  onDeleteProject,
  onCreateProject,
  conversations = [],
  activeConversation = null,
  onSelectConversation,
  onNewChat,
  onRenameConversation,
  onDeleteConversation,
}: SourcesSidebarProps) {
  const { confirmModal } = useModal();
  const [sidebarTab, setSidebarTab] = useState<'sources' | 'conversations' | 'notebooks'>('sources');
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  // Conversations management states
  const [chatSearch, setChatSearch] = useState('');
  const [chatMenuId, setChatMenuId] = useState<string | null>(null);
  const [renamingChatId, setRenamingChatId] = useState<string | null>(null);
  const [renameChatValue, setRenameChatValue] = useState('');
  const [isRenamingChat, setIsRenamingChat] = useState(false);

  // Notebooks management states
  const [notebookSearch, setNotebookSearch] = useState('');
  const [notebookMenuId, setNotebookMenuId] = useState<string | null>(null);
  const [renamingProjectId, setRenamingProjectId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [isRenaming, setIsRenaming] = useState(false);

  const getSourceIcon = (source: SourceInfo) => {
    const url = (source.original_url || source.url || '').toLowerCase();
    const type = source.source_type || '';
    if (type === 'youtube' || source.video_id) {
      return <Youtube className="w-4 h-4 flex-shrink-0 text-red-500" />;
    }
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
    if (type === 'youtube' || source.video_id) return 'YouTube';
    if (type === 'pdf' || url.endsWith('.pdf')) return 'PDF';
    if (type === 'text' || url.startsWith('text://')) return 'Note';
    return 'Web';
  };

  // Filtered notebooks sorted by updated_at descending
  const sortedNotebooks = [...projects].sort((a, b) => {
    const timeA = new Date(a.updated_at || a.created_at || 0).getTime();
    const timeB = new Date(b.updated_at || b.created_at || 0).getTime();
    return timeB - timeA;
  });

  const filteredNotebooks = sortedNotebooks.filter((p) => {
    if (!notebookSearch.trim()) return true;
    return p.name.toLowerCase().includes(notebookSearch.toLowerCase().trim());
  });

  const handleStartRename = (project: Project) => {
    setNotebookMenuId(null);
    setRenamingProjectId(project.id || project._id!);
    setRenameValue(project.name);
  };

  const handleSaveRename = async (projectId: string) => {
    const clean = renameValue.trim();
    if (!clean || !onRenameProject) {
      setRenamingProjectId(null);
      return;
    }
    setIsRenaming(true);
    try {
      await onRenameProject(projectId, clean);
      setRenamingProjectId(null);
    } finally {
      setIsRenaming(false);
    }
  };

  const handleDeleteNotebook = async (project: Project) => {
    setNotebookMenuId(null);
    const pid = project.id || project._id!;
    const ok = await confirmModal({
      title: 'Delete Entire Notebook',
      message: `Are you sure you want to permanently delete notebook "${project.name}"? This will delete all indexed sources, vector embeddings, GraphRAG entities, conversation messages, and learning artifacts. This action cannot be undone.`,
      confirmText: 'Delete Notebook',
      cancelText: 'Cancel',
      type: 'danger',
    });
    if (ok && onDeleteProject) {
      await onDeleteProject(pid);
    }
  };

  const handleStartRenameChat = (c: Conversation) => {
    setChatMenuId(null);
    setRenamingChatId(c.id || c._id!);
    setRenameChatValue(c.title);
  };

  const handleSaveRenameChat = async (chatId: string) => {
    const clean = renameChatValue.trim();
    if (!clean || !onRenameConversation) {
      setRenamingChatId(null);
      return;
    }
    setIsRenamingChat(true);
    try {
      await onRenameConversation(chatId, clean);
      setRenamingChatId(null);
    } finally {
      setIsRenamingChat(false);
    }
  };

  const handleDeleteChat = async (c: Conversation) => {
    setChatMenuId(null);
    const cid = c.id || c._id!;
    const ok = await confirmModal({
      title: 'Delete Discussion',
      message: `Are you sure you want to permanently delete "${c.title}"? This conversation and its messages will be removed. Your notebook and indexed learning sources will remain untouched.`,
      confirmText: 'Delete Discussion',
      cancelText: 'Cancel',
      type: 'danger',
    });
    if (ok && onDeleteConversation) {
      await onDeleteConversation(cid);
    }
  };

  // Filtered & sorted conversations
  const sortedConversations = [...conversations].sort((a, b) => {
    const timeA = new Date(a.last_message_at || a.updated_at || a.created_at || 0).getTime();
    const timeB = new Date(b.last_message_at || b.updated_at || b.created_at || 0).getTime();
    return timeB - timeA;
  });

  const filteredConversations = sortedConversations.filter((c) => {
    if (!chatSearch.trim()) return true;
    return c.title.toLowerCase().includes(chatSearch.toLowerCase().trim());
  });

  // Collapsed slim rail
  if (isCollapsed) {
    return (
      <div
        className="w-12 flex flex-col items-center py-3 flex-shrink-0 select-none"
        style={{ borderRight: '1px solid var(--border)', background: 'var(--surface)' }}
      >
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-md transition-colors duration-150 mb-3 hover:opacity-80"
          style={{ color: 'var(--ink-muted)' }}
          title="Expand sidebar"
        >
          <PanelLeft className="w-4 h-4" />
        </button>

        {/* Tab 1 Icon: Sources */}
        <div
          className="relative cursor-pointer mb-2"
          onClick={() => {
            setSidebarTab('sources');
            onToggleCollapse();
          }}
          title="Sources"
        >
          <div
            className="p-2 rounded-md transition-colors duration-150"
            style={{
              background: sidebarTab === 'sources' ? 'var(--canvas-alt)' : 'transparent',
              color: 'var(--accent)',
            }}
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

        {/* Tab 2 Icon: Discussions */}
        <div
          className="relative cursor-pointer mb-2"
          onClick={() => {
            setSidebarTab('conversations');
            onToggleCollapse();
          }}
          title="Discussions"
        >
          <div
            className="p-2 rounded-md transition-colors duration-150"
            style={{
              background: sidebarTab === 'conversations' ? 'var(--canvas-alt)' : 'transparent',
              color: sidebarTab === 'conversations' ? 'var(--accent)' : 'var(--ink-muted)',
            }}
          >
            <MessageSquare className="w-4 h-4" />
          </div>
          {conversations.length > 0 && (
            <span
              className="absolute -top-1 -right-1 text-[9px] font-semibold w-4 h-4 rounded-full flex items-center justify-center"
              style={{ background: 'var(--canvas-alt)', color: 'var(--ink-muted)' }}
            >
              {conversations.length}
            </span>
          )}
        </div>

        {/* Tab 3 Icon: Notebooks */}
        <div
          className="relative cursor-pointer"
          onClick={() => {
            setSidebarTab('notebooks');
            onToggleCollapse();
          }}
          title="Recent Notebooks"
        >
          <div
            className="p-2 rounded-md transition-colors duration-150"
            style={{
              background: sidebarTab === 'notebooks' ? 'var(--canvas-alt)' : 'transparent',
              color: 'var(--ink-muted)',
            }}
          >
            <Folder className="w-4 h-4" />
          </div>
          {projects.length > 0 && (
            <span
              className="absolute -top-1 -right-1 text-[9px] font-semibold w-4 h-4 rounded-full flex items-center justify-center"
              style={{ background: 'var(--canvas-alt)', color: 'var(--ink-muted)' }}
            >
              {projects.length}
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
      {/* Tab Switcher Header */}
      <div className="px-2 pt-2 pb-1 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-0.5 sm:gap-1 overflow-x-auto no-scrollbar">
          <button
            onClick={() => setSidebarTab('sources')}
            className="px-2 py-1.5 rounded-md text-[11px] sm:text-[12px] font-semibold flex items-center gap-1 transition-colors whitespace-nowrap"
            style={{
              background: sidebarTab === 'sources' ? 'var(--canvas-alt)' : 'transparent',
              color: sidebarTab === 'sources' ? 'var(--accent)' : 'var(--ink-muted)',
            }}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Sources</span>
            <span className="text-[10px] font-mono opacity-70">({sources.length})</span>
          </button>

          <button
            onClick={() => setSidebarTab('conversations')}
            className="px-2 py-1.5 rounded-md text-[11px] sm:text-[12px] font-semibold flex items-center gap-1 transition-colors whitespace-nowrap"
            style={{
              background: sidebarTab === 'conversations' ? 'var(--canvas-alt)' : 'transparent',
              color: sidebarTab === 'conversations' ? 'var(--accent)' : 'var(--ink-muted)',
            }}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>Chats</span>
            <span className="text-[10px] font-mono opacity-70">({conversations.length})</span>
          </button>

          <button
            onClick={() => setSidebarTab('notebooks')}
            className="px-2 py-1.5 rounded-md text-[11px] sm:text-[12px] font-semibold flex items-center gap-1 transition-colors whitespace-nowrap"
            style={{
              background: sidebarTab === 'notebooks' ? 'var(--canvas-alt)' : 'transparent',
              color: sidebarTab === 'notebooks' ? 'var(--accent)' : 'var(--ink-muted)',
            }}
          >
            <Folder className="w-3.5 h-3.5" />
            <span>Notebooks</span>
            <span className="text-[10px] font-mono opacity-70">({projects.length})</span>
          </button>
        </div>

        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-md transition-colors duration-150 hover:opacity-80 flex-shrink-0"
          style={{ color: 'var(--ink-faint)' }}
          title="Collapse sidebar"
        >
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      {/* ─── TAB 1: SOURCES LIST ─── */}
      {sidebarTab === 'sources' && (
        <>
          {/* Add Sources Action Button */}
          <div className="p-3" style={{ borderBottom: '1px solid var(--border-muted)' }}>
            <button
              onClick={onOpenAddModal}
              className="w-full py-2 px-3 rounded-md text-[13px] font-semibold flex items-center justify-center gap-2 transition-opacity duration-150 hover:opacity-90 shadow-sm"
              style={{ background: 'var(--accent)', color: 'var(--accent-ink)' }}
            >
              <Plus className="w-4 h-4" />
              <span>Add Sources</span>
            </button>
          </div>

          {/* Sources List */}
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
                  Add YouTube transcripts, web articles, PDFs, or notes to ground your tutor.
                </p>
              </div>
            ) : (
              sources.map((source, index) => {
                const sid = source.source_id || (source as any)._id || (source as any).id || source.original_url || `Source-${index}`;
                const isMenuOpen = activeMenuId === sid;
                const isFailed = source.status === 'failed';
                const isProcessing = source.status === 'processing';
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
                        <p className="font-medium text-[13px] truncate leading-snug" style={{ color: 'var(--ink)' }} title={source.title}>
                          {source.title || source.original_url || 'Untitled Source'}
                        </p>
                        <div className="flex items-center gap-2 mt-1 text-[11px] flex-wrap" style={{ color: 'var(--ink-faint)' }}>
                          <span
                            className="px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold"
                            style={{ background: 'var(--surface)', color: 'var(--ink-muted)' }}
                          >
                            {getSourceTypeName(source)}
                          </span>

                          {source.duration_formatted && (
                            <span className="font-mono text-[10px] px-1 py-0.2 rounded" style={{ background: 'var(--surface)' }}>
                              {source.duration_formatted}
                            </span>
                          )}

                          {source.chunk_count ? (
                            <span className="font-mono">{source.chunk_count} chunks</span>
                          ) : null}

                          {isProcessing ? (
                            <span className="font-semibold text-amber-500 animate-pulse">Processing…</span>
                          ) : isFailed ? (
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
                            className="absolute right-0 top-full mt-1 w-44 rounded-lg shadow-modal py-1 z-30 text-[13px] animate-scaleIn"
                            style={{ background: 'var(--surface-overlay)', border: '1px solid var(--border)' }}
                          >
                            {/* Watch Video link */}
                            {(source.source_type === 'youtube' || source.video_id) && (
                              <a
                                href={source.resolved_url || source.original_url || `https://www.youtube.com/watch?v=${source.video_id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={() => setActiveMenuId(null)}
                                className="flex items-center gap-2 px-3 py-1.5 transition-colors duration-100 hover:opacity-80 text-red-500"
                              >
                                <ExternalLink className="w-3.5 h-3.5" />
                                <span>Watch Video</span>
                              </a>
                            )}

                            {source.original_url &&
                              !source.original_url.startsWith('file://') &&
                              !source.original_url.startsWith('text://') &&
                              source.source_type !== 'youtube' && (
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
                                  message: `Are you sure you want to remove "${source.title || source.original_url || 'this source'}" from this notebook?`,
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

                    {/* Direct quick action row for failed sources */}
                    {isFailed && (
                      <div
                        className="mt-2 pt-2 flex items-center justify-between gap-2"
                        style={{ borderTop: '1px solid var(--border-muted)' }}
                      >
                        <span className="text-[11px] truncate flex-1" style={{ color: 'var(--negative)' }} title={source.error || 'Failed to index'}>
                          {source.error || 'Failed to index source'}
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
                                title: 'Remove Failed Source',
                                message: `Remove "${source.title || source.original_url || 'this failed source'}" from notebook?`,
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
                            title="Delete failed source"
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
        </>
      )}

      {/* ─── TAB 2: CONVERSATIONS / CHATS ─── */}
      {sidebarTab === 'conversations' && (
        <>
          {/* Top Actions: Search & New Chat */}
          <div className="p-3 space-y-2" style={{ borderBottom: '1px solid var(--border-muted)' }}>
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5" style={{ color: 'var(--ink-faint)' }} />
              <input
                type="text"
                value={chatSearch}
                onChange={(e) => setChatSearch(e.target.value)}
                placeholder="Search conversations…"
                className="w-full pl-8 pr-7 py-1.5 text-[12px] rounded-md focus:outline-none transition-colors"
                style={{
                  background: 'var(--canvas-alt)',
                  border: '1px solid var(--border)',
                  color: 'var(--ink)',
                }}
              />
              {chatSearch && (
                <button
                  onClick={() => setChatSearch('')}
                  className="absolute right-2 top-2 p-0.5 rounded hover:opacity-80"
                  style={{ color: 'var(--ink-faint)' }}
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            {onNewChat && (
              <button
                onClick={onNewChat}
                className="w-full py-2 px-3 rounded-md text-[13px] font-semibold flex items-center justify-center gap-2 transition-opacity duration-150 hover:opacity-90 shadow-sm"
                style={{ background: 'var(--accent)', color: 'var(--accent-ink)' }}
              >
                <Plus className="w-4 h-4" />
                <span>+ New Chat</span>
              </button>
            )}
          </div>

          {/* Conversations List */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {filteredConversations.length === 0 ? (
              <div className="py-12 text-center px-4">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center mx-auto mb-2.5"
                  style={{ background: 'var(--canvas-alt)' }}
                >
                  <MessageSquare className="w-5 h-5" style={{ color: 'var(--ink-faint)' }} />
                </div>
                <p className="text-[13px] font-medium" style={{ color: 'var(--ink)' }}>
                  {chatSearch ? 'No matching conversations' : 'No conversations yet'}
                </p>
                <p className="text-[12px] mt-1 max-w-[220px] mx-auto" style={{ color: 'var(--ink-faint)' }}>
                  {chatSearch
                    ? 'Try searching with a different keyword.'
                    : 'Click "+ New Chat" to start an independent discussion within this notebook.'}
                </p>
              </div>
            ) : (
              filteredConversations.map((c) => {
                const cid = c.id || c._id!;
                const isActive = activeConversation && (activeConversation.id === cid || (activeConversation as any)._id === cid);
                const isRenaming = renamingChatId === cid;
                const isMenuOpen = chatMenuId === cid;

                return (
                  <div
                    key={cid}
                    className="relative rounded-lg p-2.5 text-[13px] transition-all duration-100 group cursor-pointer"
                    style={{
                      background: isActive ? 'var(--accent-muted)' : 'var(--canvas-alt)',
                      border: `1px solid ${isActive ? 'var(--accent)' : 'var(--border)'}`,
                    }}
                    onClick={() => {
                      if (!isRenaming && onSelectConversation) {
                        onSelectConversation(c);
                      }
                    }}
                  >
                    {isRenaming ? (
                      <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="text"
                          value={renameChatValue}
                          onChange={(e) => setRenameChatValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveRenameChat(cid);
                            if (e.key === 'Escape') setRenamingChatId(null);
                          }}
                          className="flex-1 px-2 py-1 text-[12px] rounded focus:outline-none"
                          style={{
                            background: 'var(--surface)',
                            border: '1px solid var(--accent)',
                            color: 'var(--ink)',
                          }}
                          autoFocus
                          disabled={isRenamingChat}
                        />
                        <button
                          onClick={() => handleSaveRenameChat(cid)}
                          disabled={isRenamingChat}
                          className="p-1 rounded hover:opacity-80 transition-opacity"
                          style={{ color: 'var(--positive)' }}
                          title="Save"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setRenamingChatId(null)}
                          disabled={isRenamingChat}
                          className="p-1 rounded hover:opacity-80 transition-opacity"
                          style={{ color: 'var(--ink-faint)' }}
                          title="Cancel"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <MessageSquare
                              className="w-3.5 h-3.5 flex-shrink-0"
                              style={{ color: isActive ? 'var(--accent)' : 'var(--ink-faint)' }}
                            />
                            <p
                              className="font-medium text-[13px] truncate leading-snug"
                              style={{ color: isActive ? 'var(--accent)' : 'var(--ink)' }}
                              title={c.title}
                            >
                              {c.title || 'Untitled Conversation'}
                            </p>
                          </div>
                          <div
                            className="flex items-center gap-2 mt-1 text-[11px] pl-5"
                            style={{ color: 'var(--ink-faint)' }}
                          >
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3 opacity-60" />
                              <span>{formatRelativeTime(c.last_message_at || c.updated_at || c.created_at)}</span>
                            </span>
                            {c.message_count !== undefined && (
                              <>
                                <span>·</span>
                                <span>{c.message_count} {c.message_count === 1 ? 'msg' : 'msgs'}</span>
                              </>
                            )}
                          </div>
                        </div>

                        {/* Three-dot context menu */}
                        <div className="relative flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => setChatMenuId(isMenuOpen ? null : cid)}
                            className="p-1 rounded opacity-60 hover:opacity-100 transition-opacity"
                            style={{ color: 'var(--ink-faint)' }}
                            title="Conversation options"
                          >
                            <MoreVertical className="w-3.5 h-3.5" />
                          </button>

                          {isMenuOpen && (
                            <div
                              className="absolute right-0 top-full mt-1 w-40 rounded-lg shadow-modal py-1 z-30 text-[12px] animate-scaleIn"
                              style={{ background: 'var(--surface-overlay)', border: '1px solid var(--border)' }}
                            >
                              <button
                                onClick={() => {
                                  setChatMenuId(null);
                                  if (onSelectConversation) onSelectConversation(c);
                                }}
                                className="w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors hover:opacity-80"
                                style={{ color: 'var(--ink)' }}
                              >
                                <MessageSquare className="w-3.5 h-3.5" />
                                <span>Switch to Chat</span>
                              </button>
                              <button
                                onClick={() => handleStartRenameChat(c)}
                                className="w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors hover:opacity-80"
                                style={{ color: 'var(--ink)' }}
                              >
                                <Edit2 className="w-3.5 h-3.5" />
                                <span>Rename</span>
                              </button>
                              <button
                                onClick={() => handleDeleteChat(c)}
                                className="w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors hover:opacity-80 text-red-500"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                                <span>Delete Chat</span>
                              </button>
                            </div>
                          )}
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
            <span>Notebook Chats</span>
            <span className="font-mono" style={{ color: 'var(--ink-muted)' }}>
              {filteredConversations.length} total
            </span>
          </div>
        </>
      )}

      {/* ─── TAB 3: RECENT NOTEBOOKS ─── */}
      {sidebarTab === 'notebooks' && (
        <>
          {/* Top Actions: Search & Create */}
          <div className="p-3 space-y-2" style={{ borderBottom: '1px solid var(--border-muted)' }}>
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5" style={{ color: 'var(--ink-faint)' }} />
              <input
                type="text"
                value={notebookSearch}
                onChange={(e) => setNotebookSearch(e.target.value)}
                placeholder="Search notebooks…"
                className="w-full pl-8 pr-7 py-1.5 text-[12px] rounded-md focus:outline-none transition-colors"
                style={{
                  background: 'var(--canvas-alt)',
                  border: '1px solid var(--border)',
                  color: 'var(--ink)',
                }}
              />
              {notebookSearch && (
                <button
                  onClick={() => setNotebookSearch('')}
                  className="absolute right-2 top-2 p-0.5 rounded hover:opacity-80"
                  style={{ color: 'var(--ink-faint)' }}
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            {onCreateProject && (
              <button
                onClick={onCreateProject}
                className="w-full py-1.5 px-3 rounded-md text-[12px] font-semibold flex items-center justify-center gap-1.5 transition-colors"
                style={{
                  background: 'var(--canvas-alt)',
                  border: '1px solid var(--border)',
                  color: 'var(--accent)',
                }}
              >
                <Plus className="w-3.5 h-3.5" />
                <span>New Notebook</span>
              </button>
            )}
          </div>

          {/* Notebooks List */}
          <div className="flex-1 overflow-y-auto p-2.5 space-y-1.5">
            {filteredNotebooks.length === 0 ? (
              <div className="py-10 text-center px-4">
                <Folder className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-[12px] font-medium" style={{ color: 'var(--ink)' }}>No notebooks found</p>
                {notebookSearch && (
                  <p className="text-[11px] mt-1" style={{ color: 'var(--ink-faint)' }}>
                    Try searching for a different title
                  </p>
                )}
              </div>
            ) : (
              filteredNotebooks.map((p) => {
                const pid = p.id || p._id!;
                const isActive = activeProject && (activeProject.id || activeProject._id) === pid;
                const isMenuOpen = notebookMenuId === pid;
                const isEditing = renamingProjectId === pid;

                return (
                  <div
                    key={pid}
                    onClick={() => {
                      if (!isEditing && onSelectProject) onSelectProject(p);
                    }}
                    className="relative rounded-lg p-2.5 transition-all text-left cursor-pointer group"
                    style={{
                      background: isActive ? 'var(--canvas-alt)' : 'transparent',
                      border: isActive ? '1px solid var(--accent)' : '1px solid transparent',
                    }}
                  >
                    {isEditing ? (
                      <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="text"
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveRename(pid);
                            if (e.key === 'Escape') setRenamingProjectId(null);
                          }}
                          autoFocus
                          disabled={isRenaming}
                          className="flex-1 px-2 py-1 text-[12px] rounded border focus:outline-none"
                          style={{
                            background: 'var(--surface)',
                            borderColor: 'var(--accent)',
                            color: 'var(--ink)',
                          }}
                        />
                        <button
                          onClick={() => handleSaveRename(pid)}
                          disabled={isRenaming}
                          className="p-1 rounded text-emerald-500 hover:bg-emerald-500/10"
                          title="Save"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setRenamingProjectId(null)}
                          disabled={isRenaming}
                          className="p-1 rounded text-slate-400 hover:bg-slate-500/10"
                          title="Cancel"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <Folder
                              className="w-3.5 h-3.5 flex-shrink-0"
                              style={{ color: isActive ? 'var(--accent)' : 'var(--ink-muted)' }}
                            />
                            <h4
                              className="text-[13px] font-semibold truncate leading-tight"
                              style={{ color: isActive ? 'var(--accent)' : 'var(--ink)' }}
                            >
                              {p.name}
                            </h4>
                          </div>

                          <div className="flex items-center gap-2 mt-1 text-[11px]" style={{ color: 'var(--ink-faint)' }}>
                            <span className="flex items-center gap-1">
                              <Clock className="w-2.5 h-2.5 opacity-60" />
                              <span>{formatRelativeTime(p.updated_at || p.created_at)}</span>
                            </span>
                            <span>·</span>
                            <span>{p.source_count || 0} src</span>
                          </div>
                        </div>

                        {/* Three-dot context menu */}
                        <div className="relative" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => setNotebookMenuId(isMenuOpen ? null : pid)}
                            className="p-1 rounded opacity-60 hover:opacity-100 transition-opacity"
                            style={{ color: 'var(--ink-faint)' }}
                          >
                            <MoreVertical className="w-3.5 h-3.5" />
                          </button>

                          {isMenuOpen && (
                            <div
                              className="absolute right-0 top-full mt-1 w-40 rounded-lg shadow-modal py-1 z-30 text-[12px] animate-scaleIn"
                              style={{ background: 'var(--surface-overlay)', border: '1px solid var(--border)' }}
                            >
                              <button
                                onClick={() => {
                                  setNotebookMenuId(null);
                                  if (onSelectProject) onSelectProject(p);
                                }}
                                className="w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors hover:opacity-80"
                                style={{ color: 'var(--ink)' }}
                              >
                                <Folder className="w-3.5 h-3.5" />
                                <span>Open Notebook</span>
                              </button>
                              <button
                                onClick={() => handleStartRename(p)}
                                className="w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors hover:opacity-80"
                                style={{ color: 'var(--ink)' }}
                              >
                                <Edit2 className="w-3.5 h-3.5" />
                                <span>Rename</span>
                              </button>
                              <button
                                onClick={() => handleDeleteNotebook(p)}
                                className="w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors hover:opacity-80 text-red-500"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                                <span>Delete Notebook</span>
                              </button>
                            </div>
                          )}
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
            <span>Recent Notebooks</span>
            <span className="font-mono" style={{ color: 'var(--ink-muted)' }}>
              {filteredNotebooks.length} total
            </span>
          </div>
        </>
      )}
    </div>
  );
}

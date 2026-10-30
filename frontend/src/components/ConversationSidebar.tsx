'use client';
import React, { useState, useMemo } from 'react';
import {
  MessageSquare,
  Plus,
  Search,
  MoreVertical,
  Edit2,
  Archive,
  Trash2,
  FolderKanban,
  Check,
  X,
  ChevronDown,
  Clock,
  ArchiveRestore,
} from 'lucide-react';
import type { Conversation, Project } from '@/types';
import { useModal } from '@/context/ModalContext';

interface ConversationSidebarProps {
  projects: Project[];
  activeProject: Project | null;
  onSelectProject: (project: Project) => void;
  onOpenNewProject: () => void;
  conversations: Conversation[];
  activeConversation: Conversation | null;
  onSelectConversation: (conversation: Conversation) => void;
  onNewChat: () => void;
  onRenameConversation: (id: string, newTitle: string) => Promise<void>;
  onArchiveConversation: (id: string) => Promise<void>;
  onDeleteConversation: (id: string) => Promise<void>;
  isOpenMobile: boolean;
  onCloseMobile: () => void;
}

export function ConversationSidebar({
  projects,
  activeProject,
  onSelectProject,
  onOpenNewProject,
  conversations,
  activeConversation,
  onSelectConversation,
  onNewChat,
  onRenameConversation,
  onArchiveConversation,
  onDeleteConversation,
  isOpenMobile,
  onCloseMobile,
}: ConversationSidebarProps) {
  const { confirmModal } = useModal();
  const [searchQuery, setSearchQuery] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false);

  // Filter conversations by search and archive status
  const filtered = useMemo(() => {
    return conversations.filter((c) => {
      const matchesArchive = showArchived ? c.status === 'archived' : c.status !== 'archived';
      const matchesSearch = !searchQuery.trim() || c.title.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesArchive && matchesSearch;
    });
  }, [conversations, showArchived, searchQuery]);

  // Group by date
  const grouped = useMemo(() => {
    const today: Conversation[] = [];
    const yesterday: Conversation[] = [];
    const last7Days: Conversation[] = [];
    const older: Conversation[] = [];

    const now = new Date();
    const todayMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayMidnight = todayMidnight - 86400000;
    const sevenDaysAgo = todayMidnight - 6 * 86400000;

    for (const c of filtered) {
      const msgDate = new Date(c.last_message_at || c.created_at).getTime();
      if (msgDate >= todayMidnight) {
        today.push(c);
      } else if (msgDate >= yesterdayMidnight) {
        yesterday.push(c);
      } else if (msgDate >= sevenDaysAgo) {
        last7Days.push(c);
      } else {
        older.push(c);
      }
    }

    return { today, yesterday, last7Days, older };
  }, [filtered]);

  const handleStartRename = (c: Conversation) => {
    setEditingId(c.id || c._id!);
    setEditingTitle(c.title);
    setMenuOpenId(null);
  };

  const handleSaveRename = async (id: string) => {
    if (editingTitle.trim()) {
      await onRenameConversation(id, editingTitle.trim());
    }
    setEditingId(null);
  };

  const renderConversationItem = (c: Conversation) => {
    const id = c.id || c._id!;
    const isActive = activeConversation && (activeConversation.id === id || activeConversation._id === id);
    const isEditing = editingId === id;

    if (isEditing) {
      return (
        <div key={id} className="flex items-center gap-1.5 px-3 py-2 bg-blue-50/80 rounded-xl border border-blue-200">
          <input
            type="text"
            value={editingTitle}
            onChange={(e) => setEditingTitle(e.target.value)}
            className="flex-1 bg-white text-xs px-2 py-1 rounded border border-slate-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSaveRename(id);
              if (e.key === 'Escape') setEditingId(null);
            }}
          />
          <button
            onClick={() => handleSaveRename(id)}
            className="p-1 text-emerald-600 hover:bg-emerald-50 rounded"
          >
            <Check className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setEditingId(null)}
            className="p-1 text-slate-400 hover:bg-slate-200 rounded"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      );
    }

    return (
      <div
        key={id}
        className={`group relative flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-medium cursor-pointer transition-all ${
          isActive
            ? 'bg-blue-600 text-white shadow-xs font-semibold'
            : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'
        }`}
        onClick={() => {
          onSelectConversation(c);
          onCloseMobile();
        }}
      >
        <div className="flex items-center gap-2.5 truncate mr-2">
          <MessageSquare className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-white' : 'text-slate-400'}`} />
          <span className="truncate">{c.title}</span>
        </div>

        {/* Options Menu Button */}
        <div className="relative flex-shrink-0" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => setMenuOpenId(menuOpenId === id ? null : id)}
            className={`p-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity ${
              isActive ? 'hover:bg-blue-700 text-white' : 'hover:bg-slate-200 text-slate-500'
            }`}
          >
            <MoreVertical className="w-3.5 h-3.5" />
          </button>

          {/* Menu Dropdown */}
          {menuOpenId === id && (
            <div className="absolute right-0 top-full mt-1 w-36 bg-white rounded-xl shadow-lg border border-slate-200 py-1 z-30 animate-fadeIn text-slate-700 text-xs font-normal">
              <button
                onClick={() => handleStartRename(c)}
                className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-slate-50 text-left"
              >
                <Edit2 className="w-3.5 h-3.5 text-slate-400" />
                <span>Rename</span>
              </button>
              <button
                onClick={async () => {
                  setMenuOpenId(null);
                  await onArchiveConversation(id);
                }}
                className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-slate-50 text-left"
              >
                {c.status === 'archived' ? (
                  <>
                    <ArchiveRestore className="w-3.5 h-3.5 text-slate-400" />
                    <span>Unarchive</span>
                  </>
                ) : (
                  <>
                    <Archive className="w-3.5 h-3.5 text-slate-400" />
                    <span>Archive</span>
                  </>
                )}
              </button>
              <button
                onClick={async () => {
                  setMenuOpenId(null);
                  const ok = await confirmModal({
                    title: 'Delete Conversation',
                    message: 'Are you sure you want to delete this conversation? This cannot be undone.',
                    confirmText: 'Delete Conversation',
                    cancelText: 'Cancel',
                    type: 'danger',
                  });
                  if (ok) {
                    await onDeleteConversation(id);
                  }
                }}
                className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-red-950/40 text-red-400 text-left"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Delete</span>
              </button>
            </div>
          )}
        </div>
      </div>
    );
  };

  const content = (
    <div className="h-full flex flex-col bg-white border-r border-slate-200 w-72 lg:w-80 flex-shrink-0">
      {/* Project Switcher */}
      <div className="p-3 border-b border-slate-200 relative">
        <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1 mb-1 block">
          Learning Workspace
        </label>
        <button
          onClick={() => setProjectDropdownOpen(!projectDropdownOpen)}
          className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 hover:bg-slate-100 rounded-xl border border-slate-200 text-xs font-semibold text-slate-800 transition-colors"
        >
          <div className="flex items-center gap-2 truncate">
            <FolderKanban className="w-4 h-4 text-blue-600 flex-shrink-0" />
            <span className="truncate">{activeProject?.name || 'Select Project'}</span>
          </div>
          <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 ml-1" />
        </button>

        {/* Project Selector Menu */}
        {projectDropdownOpen && (
          <div className="absolute left-3 right-3 top-full mt-1 bg-white rounded-xl shadow-xl border border-slate-200 py-1.5 z-40 max-h-60 overflow-y-auto">
            <div className="px-3 py-1 text-[11px] font-semibold text-slate-400 uppercase">
              Your Projects
            </div>
            {projects.map((p) => {
              const pid = p.id || p._id!;
              const isSelected = activeProject && (activeProject.id === pid || activeProject._id === pid);
              return (
                <button
                  key={pid}
                  onClick={() => {
                    onSelectProject(p);
                    setProjectDropdownOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2 text-xs text-left hover:bg-blue-50 transition-colors ${
                    isSelected ? 'font-semibold text-blue-700 bg-blue-50/60' : 'text-slate-700'
                  }`}
                >
                  <span className="truncate">{p.name}</span>
                  {isSelected && <Check className="w-3.5 h-3.5 text-blue-600 flex-shrink-0" />}
                </button>
              );
            })}
            <div className="border-t border-slate-100 mt-1 pt-1 px-1">
              <button
                onClick={() => {
                  setProjectDropdownOpen(false);
                  onOpenNewProject();
                }}
                className="w-full flex items-center gap-2 px-2.5 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create New Project</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Action: New Chat Button */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full py-2.5 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs flex items-center justify-center gap-2 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>New Discussion</span>
        </button>
      </div>

      {/* Search Input */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search discussions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-2 text-slate-400 hover:text-slate-600"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* Chat List */}
      <div className="flex-1 overflow-y-auto px-3 py-1 space-y-4">
        {filtered.length === 0 ? (
          <div className="py-8 text-center px-4">
            <MessageSquare className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-xs text-slate-500 font-medium">No discussions found</p>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {searchQuery ? 'Try another search term' : 'Click "New Discussion" to start'}
            </p>
          </div>
        ) : (
          <>
            {grouped.today.length > 0 && (
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2 mb-1.5 block">
                  Today
                </span>
                <div className="space-y-1">{grouped.today.map(renderConversationItem)}</div>
              </div>
            )}

            {grouped.yesterday.length > 0 && (
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2 mb-1.5 block">
                  Yesterday
                </span>
                <div className="space-y-1">{grouped.yesterday.map(renderConversationItem)}</div>
              </div>
            )}

            {grouped.last7Days.length > 0 && (
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2 mb-1.5 block">
                  Previous 7 Days
                </span>
                <div className="space-y-1">{grouped.last7Days.map(renderConversationItem)}</div>
              </div>
            )}

            {grouped.older.length > 0 && (
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2 mb-1.5 block">
                  Older
                </span>
                <div className="space-y-1">{grouped.older.map(renderConversationItem)}</div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer: Archive toggle */}
      <div className="p-3 border-t border-slate-200 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500">
        <button
          onClick={() => setShowArchived(!showArchived)}
          className="flex items-center gap-1.5 hover:text-slate-800 transition-colors"
        >
          <Archive className="w-3.5 h-3.5 text-slate-400" />
          <span>{showArchived ? 'Active Discussions' : 'Archived Discussions'}</span>
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <div className="hidden md:block h-full">{content}</div>

      {/* Mobile drawer */}
      {isOpenMobile && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div
            className="fixed inset-0 bg-slate-900/50 backdrop-blur-2xs"
            onClick={onCloseMobile}
          />
          <div className="relative z-10 w-4/5 max-w-xs">{content}</div>
        </div>
      )}
    </>
  );
}

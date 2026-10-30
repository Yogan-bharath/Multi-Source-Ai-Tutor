'use client';
import React, { useState, useEffect, useCallback } from 'react';
import {
  BookOpen,
  FolderKanban,
  LogOut,
  Plus,
  Loader2,
  FolderPlus,
  ChevronDown,
  PanelLeft,
  PanelRight,
  Menu,
  X,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { useModal } from '@/context/ModalContext';
import { SourcesSidebar } from '@/components/SourcesSidebar';
import { StudioSidebar } from '@/components/StudioSidebar';
import { ChatPanel } from '@/components/ChatPanel';
import { AddSourcesModal } from '@/components/AddSourcesModal';
import { StudioToolModal } from '@/components/StudioToolModal';
import { AuthModal } from '@/components/AuthModal';
import { ProjectModal } from '@/components/ProjectModal';
import type {
  Project,
  Conversation,
  SourceInfo,
  StudioToolType,
} from '@/types';

export default function Home() {
  const { user, loading: authLoading, logout } = useAuth();
  const { alertModal } = useModal();

  // Project & Conversation State
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [sources, setSources] = useState<SourceInfo[]>([]);

  // Layout & Sidebar States (collapsible)
  const [leftCollapsed, setLeftCollapsed] = useState<boolean>(false);
  const [rightCollapsed, setRightCollapsed] = useState<boolean>(false);
  const [mobileDrawer, setMobileDrawer] = useState<'sources' | 'studio' | null>(null);

  // Modals
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [addSourcesModalOpen, setAddSourcesModalOpen] = useState(false);
  const [activeStudioTool, setActiveStudioTool] = useState<StudioToolType | null>(null);

  // UI Menus & Loaders
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingSources, setLoadingSources] = useState(false);

  // Load saved sidebar state
  useEffect(() => {
    try {
      const savedLeft = localStorage.getItem('sidebar_sources_collapsed');
      const savedRight = localStorage.getItem('sidebar_studio_collapsed');
      if (savedLeft !== null) setLeftCollapsed(savedLeft === 'true');
      if (savedRight !== null) setRightCollapsed(savedRight === 'true');
    } catch {
      // ignore localstorage errors
    }
  }, []);

  const toggleLeftSidebar = () => {
    setLeftCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem('sidebar_sources_collapsed', String(next));
      return next;
    });
  };

  const toggleRightSidebar = () => {
    setRightCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem('sidebar_studio_collapsed', String(next));
      return next;
    });
  };

  // 1. Load Projects for authenticated user
  const fetchProjects = useCallback(async () => {
    if (!user) return;
    setLoadingProjects(true);
    try {
      const res = await fetch('/api/projects', { credentials: 'include' });
      if (res.ok) {
        const data: Project[] = await res.json();
        setProjects(data);

        // Restore active project from localStorage or default to first
        const savedProjectId = localStorage.getItem('active_project_id');
        const found = data.find((p) => (p.id || p._id) === savedProjectId);
        if (found) {
          setActiveProject(found);
        } else if (data.length > 0) {
          setActiveProject(data[0]);
          localStorage.setItem('active_project_id', data[0].id || data[0]._id!);
        } else {
          setActiveProject(null);
        }
      }
    } catch (err) {
      console.error('Failed to load projects:', err);
    } finally {
      setLoadingProjects(false);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      fetchProjects();
    } else {
      setProjects([]);
      setActiveProject(null);
      setConversations([]);
      setActiveConversation(null);
      setSources([]);
    }
  }, [user, fetchProjects]);

  // 2. Load Sources for active project
  const fetchSources = useCallback(async () => {
    if (!user || !activeProject) {
      setSources([]);
      return;
    }

    const pid = activeProject.id || activeProject._id;
    setLoadingSources(true);
    try {
      const res = await fetch(`/api/projects/${pid}/sources`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setSources(data);
      }
    } catch (err) {
      console.error('Failed to load sources for project:', err);
    } finally {
      setLoadingSources(false);
    }
  }, [user, activeProject]);

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  // 3. Load Conversations for active project
  const fetchConversations = useCallback(async () => {
    if (!user || !activeProject) {
      setConversations([]);
      setActiveConversation(null);
      return;
    }

    const pid = activeProject.id || activeProject._id;
    try {
      const res = await fetch(`/api/projects/${pid}/chats`, { credentials: 'include' });
      if (res.ok) {
        const data: Conversation[] = await res.json();
        setConversations(data);

        // Restore active conversation from localStorage
        const savedChatId = localStorage.getItem(`active_chat_${pid}`);
        const found = data.find((c) => (c.id || c._id) === savedChatId);
        if (found) {
          setActiveConversation(found);
        } else if (data.length > 0) {
          setActiveConversation(data[0]);
          localStorage.setItem(`active_chat_${pid}`, data[0].id || data[0]._id!);
        } else {
          setActiveConversation(null);
        }
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  }, [user, activeProject]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // Handlers
  const handleSelectProject = (project: Project) => {
    setActiveProject(project);
    const pid = project.id || project._id!;
    localStorage.setItem('active_project_id', pid);
    setProjectDropdownOpen(false);
  };

  const handleSelectConversation = (c: Conversation) => {
    setActiveConversation(c);
    if (activeProject) {
      const pid = activeProject.id || activeProject._id!;
      localStorage.setItem(`active_chat_${pid}`, c.id || c._id!);
    }
  };

  const handleNewChat = () => {
    setActiveConversation(null);
    if (activeProject) {
      const pid = activeProject.id || activeProject._id!;
      localStorage.removeItem(`active_chat_${pid}`);
    }
  };

  const handleConversationCreated = (newConv: Conversation) => {
    setConversations((prev) => [newConv, ...prev]);
    setActiveConversation(newConv);
    if (activeProject) {
      const pid = activeProject.id || activeProject._id!;
      localStorage.setItem(`active_chat_${pid}`, newConv.id || newConv._id!);
    }
  };

  const handleDeleteSource = async (sourceId: string, originalUrl?: string) => {
    if (!sourceId && !originalUrl) return;

    // Optimistically remove from state
    const previousSources = [...sources];
    setSources((prev) =>
      prev.filter(
        (s) =>
          s.source_id !== sourceId &&
          (s as any)._id !== sourceId &&
          (s as any).id !== sourceId &&
          s.original_url !== sourceId &&
          (!originalUrl || s.original_url !== originalUrl)
      )
    );

    if (!activeProject) {
      // Guest mode: removed from state, nothing more to delete in DB
      return;
    }

    const pid = activeProject.id || activeProject._id!;
    try {
      // Use POST /api/ingest/sources/remove which handles full JSON body without URL encoding issues
      const res = await fetch('/api/ingest/sources/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          project_id: pid,
          source_id: sourceId,
          original_url: originalUrl,
        }),
      });

      if (res.ok) {
        // Refresh sources and project stats in background
        await fetchSources();
        await fetchProjects();
      } else {
        // Fallback to path DELETE
        const delRes = await fetch(`/api/ingest/sources/${pid}/${encodeURIComponent(sourceId)}`, {
          method: 'DELETE',
          credentials: 'include',
        });
        if (delRes.ok) {
          await fetchSources();
          await fetchProjects();
        } else {
          // Revert optimistic update
          setSources(previousSources);
          const data = await res.json().catch(() => ({}));
          await alertModal({
            title: 'Unable to Remove Source',
            message: data.detail || 'Failed to remove source from the notebook.',
            type: 'error',
          });
        }
      }
    } catch (err: any) {
      setSources(previousSources);
      console.error('Failed to delete source:', err);
      await alertModal({
        title: 'Error',
        message: err?.message || 'Error removing source from notebook.',
        type: 'error',
      });
    }
  };

  const handleRetrySource = async (source: SourceInfo) => {
    if (!activeProject) return;
    const pid = activeProject.id || activeProject._id!;
    const url = source.original_url || source.url;
    if (!url) return;

    try {
      const res = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          urls: [url],
          project_id: pid,
        }),
      });
      if (res.ok) {
        await fetchSources();
        await fetchProjects();
      } else {
        const err = await res.json().catch(() => ({}));
        await alertModal({
          title: 'Retry Indexing Failed',
          message:
            err.detail ||
            'Failed to index this webpage. The site may restrict automated scraping or require authentication.',
          type: 'error',
        });
      }
    } catch (err: any) {
      console.error('Retry failed:', err);
      await alertModal({
        title: 'Network Error',
        message: 'Network error while retrying source indexing.',
        type: 'error',
      });
    }
  };

  const handleProjectCreated = (newProject: Project) => {
    setProjects((prev) => [newProject, ...prev]);
    setActiveProject(newProject);
    const pid = newProject.id || newProject._id!;
    localStorage.setItem('active_project_id', pid);
  };

  // Close menus on outside click
  useEffect(() => {
    const closeMenus = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('#project-dropdown-container')) {
        setProjectDropdownOpen(false);
      }
      if (!target.closest('#user-menu-container')) {
        setUserMenuOpen(false);
      }
    };
    window.addEventListener('click', closeMenus);
    return () => window.removeEventListener('click', closeMenus);
  }, []);

  // Auth loading state
  if (authLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center" style={{ background: 'var(--canvas)' }}>
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--accent)' }}>
            <BookOpen className="w-4 h-4 text-white" />
          </div>
          <p className="text-xs font-medium tracking-wide" style={{ color: 'var(--ink-muted)' }}>
            Loading workspace…
          </p>
        </div>
      </div>
    );
  }

  const activeSuccessfulSources = sources.filter((s) => s.status === 'success');

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden select-none" style={{ background: 'var(--canvas)', color: 'var(--ink)' }}>
      {/* ═══════════════════════════════════════
          Top Navigation — Compact Editorial Bar
          ═══════════════════════════════════════ */}
      <header
        className="h-12 flex-shrink-0 flex items-center justify-between px-4 z-30 select-none"
        style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}
      >
        {/* Left: Brand & Mobile Triggers */}
        <div className="flex items-center gap-3">
          {/* Mobile Source Drawer Toggle */}
          {user && (
            <button
              onClick={() => setMobileDrawer(mobileDrawer === 'sources' ? null : 'sources')}
              className="lg:hidden p-1.5 rounded-md transition-colors duration-150"
              style={{ color: 'var(--ink-muted)' }}
              title="Toggle Sources"
            >
              <PanelLeft className="w-4 h-4" />
            </button>
          )}

          {/* Logo & Title */}
          <div className="flex items-center gap-2.5">
            <div
              className="w-7 h-7 rounded-md flex items-center justify-center"
              style={{ background: 'var(--accent)' }}
            >
              <BookOpen className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-semibold text-[13px] tracking-[-0.01em] hidden sm:inline" style={{ color: 'var(--ink)' }}>
              Multi-Source AI Tutor
            </span>
          </div>

          {/* Breadcrumb Divider */}
          {user && activeProject && (
            <span className="hidden sm:inline text-[13px]" style={{ color: 'var(--border)' }}>/</span>
          )}

          {/* Project Selector */}
          {user && (
            <div id="project-dropdown-container" className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setProjectDropdownOpen(!projectDropdownOpen);
                }}
                className="flex items-center gap-2 px-2.5 py-1.5 rounded-md text-[13px] font-medium transition-colors duration-150 max-w-[200px] sm:max-w-[260px]"
                style={{
                  color: 'var(--ink)',
                  background: projectDropdownOpen ? 'var(--canvas-alt)' : 'transparent',
                }}
                onMouseEnter={(e) => { if (!projectDropdownOpen) (e.target as HTMLElement).style.background = 'var(--canvas-alt)'; }}
                onMouseLeave={(e) => { if (!projectDropdownOpen) (e.target as HTMLElement).style.background = 'transparent'; }}
              >
                <FolderKanban className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--ink-muted)' }} />
                <span className="truncate">
                  {activeProject ? activeProject.name : 'Select Notebook'}
                </span>
                <ChevronDown className="w-3 h-3 flex-shrink-0 ml-auto" style={{ color: 'var(--ink-faint)' }} />
              </button>

              {projectDropdownOpen && (
                <div
                  className="absolute left-0 top-full mt-1 w-64 rounded-lg shadow-modal py-1 z-50 animate-scaleIn"
                  style={{ background: 'var(--surface-overlay)', border: '1px solid var(--border)' }}
                >
                  <div className="px-3 py-2 text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--ink-faint)' }}>
                    Your Notebooks
                  </div>
                  <div className="max-h-60 overflow-y-auto">
                    {projects.map((p) => {
                      const pid = p.id || p._id!;
                      const isActive = activeProject && (activeProject.id === pid || activeProject._id === pid);
                      return (
                        <button
                          key={pid}
                          onClick={() => handleSelectProject(p)}
                          className="w-full text-left px-3 py-2 flex items-center justify-between text-[13px] transition-colors duration-100"
                          style={{
                            background: isActive ? 'var(--accent-muted)' : 'transparent',
                            color: isActive ? 'var(--accent)' : 'var(--ink)',
                            fontWeight: isActive ? 600 : 400,
                          }}
                          onMouseEnter={(e) => { if (!isActive) (e.target as HTMLElement).style.background = 'var(--canvas-alt)'; }}
                          onMouseLeave={(e) => { if (!isActive) (e.target as HTMLElement).style.background = 'transparent'; }}
                        >
                          <span className="truncate pr-2">{p.name}</span>
                          <span className="text-[11px] flex-shrink-0" style={{ color: 'var(--ink-faint)' }}>
                            {p.source_count || 0} src
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  <div style={{ borderTop: '1px solid var(--border)' }} className="mt-1 pt-1">
                    <button
                      onClick={() => {
                        setProjectDropdownOpen(false);
                        setProjectModalOpen(true);
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-[13px] font-medium text-left transition-colors duration-100"
                      style={{ color: 'var(--accent)' }}
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>New Notebook</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Center: Active Sources Badge */}
        {user && activeProject && (
          <div
            className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded-md text-[11px]"
            style={{ background: 'var(--canvas-alt)', color: 'var(--ink-muted)' }}
          >
            <div className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--positive)' }} />
            <span>
              <strong style={{ color: 'var(--ink)' }}>{activeSuccessfulSources.length}</strong>{' '}
              active {activeSuccessfulSources.length === 1 ? 'source' : 'sources'}
            </span>
          </div>
        )}

        {/* Right: Mobile Studio Toggle & User */}
        <div className="flex items-center gap-2">
          {/* Mobile Studio Drawer Toggle */}
          {user && (
            <button
              onClick={() => setMobileDrawer(mobileDrawer === 'studio' ? null : 'studio')}
              className="lg:hidden p-1.5 rounded-md transition-colors duration-150"
              style={{ color: 'var(--ink-muted)' }}
              title="Toggle Learning Studio"
            >
              <PanelRight className="w-4 h-4" />
            </button>
          )}

          {user ? (
            <div id="user-menu-container" className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setUserMenuOpen(!userMenuOpen);
                }}
                className="flex items-center gap-2 p-1 rounded-md transition-colors duration-150"
              >
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center font-semibold text-xs text-white"
                  style={{ background: 'var(--accent)' }}
                >
                  {user.name ? user.name[0].toUpperCase() : 'U'}
                </div>
                <span className="hidden sm:inline text-[13px] font-medium" style={{ color: 'var(--ink)' }}>
                  {user.name}
                </span>
                <ChevronDown className="w-3 h-3 hidden sm:inline" style={{ color: 'var(--ink-faint)' }} />
              </button>

              {userMenuOpen && (
                <div
                  className="absolute right-0 top-full mt-1 w-52 rounded-lg shadow-modal py-1 z-50 animate-scaleIn"
                  style={{ background: 'var(--surface-overlay)', border: '1px solid var(--border)' }}
                >
                  <div className="px-3 py-2.5" style={{ borderBottom: '1px solid var(--border)' }}>
                    <p className="font-semibold text-[13px] truncate" style={{ color: 'var(--ink)' }}>{user.name}</p>
                    <p className="text-[11px] truncate" style={{ color: 'var(--ink-faint)' }}>{user.email}</p>
                  </div>
                  <button
                    onClick={() => {
                      setUserMenuOpen(false);
                      setProjectModalOpen(true);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-[13px] transition-colors duration-100 text-left"
                    style={{ color: 'var(--ink-muted)' }}
                  >
                    <FolderPlus className="w-4 h-4" />
                    <span>Create Notebook</span>
                  </button>
                  <button
                    onClick={() => {
                      setUserMenuOpen(false);
                      logout();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-[13px] transition-colors duration-100 text-left"
                    style={{ color: 'var(--negative)', borderTop: '1px solid var(--border)' }}
                  >
                    <LogOut className="w-4 h-4" />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={() => setAuthModalOpen(true)}
              className="px-3.5 py-1.5 text-[13px] font-medium rounded-md transition-colors duration-150 flex items-center gap-1.5"
              style={{ background: 'var(--accent)', color: 'var(--accent-ink)' }}
            >
              <span>Sign In</span>
            </button>
          )}
        </div>
      </header>

      {/* ═══════════════════════════════════════
          Main Content Area
          ═══════════════════════════════════════ */}
      {!user ? (
        /* ─── Guest Entry Experience ─── */
        <div className="flex-1 flex flex-col items-center justify-center p-6 select-text" style={{ background: 'var(--canvas)' }}>
          <div className="max-w-lg text-center">
            {/* Compact product intro — not a marketing hero */}
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-5"
              style={{ background: 'var(--accent-muted)' }}
            >
              <BookOpen className="w-6 h-6" style={{ color: 'var(--accent)' }} />
            </div>
            <h1 className="text-2xl font-bold tracking-[-0.02em]" style={{ color: 'var(--ink)' }}>
              Research. Learn. Synthesize.
            </h1>
            <p className="text-sm mt-3 leading-relaxed max-w-md mx-auto" style={{ color: 'var(--ink-muted)' }}>
              Add websites, documents, and notes into research notebooks.
              Ask questions across your sources and explore interactive study tools.
            </p>

            {/* Three concise capability labels */}
            <div className="flex flex-wrap justify-center gap-3 mt-6">
              {[
                'Multi-source ingestion',
                'AI-grounded answers',
                'Interactive study tools',
              ].map((label) => (
                <span
                  key={label}
                  className="inline-flex items-center px-3 py-1.5 rounded-md text-[12px] font-medium"
                  style={{ background: 'var(--canvas-alt)', color: 'var(--ink-muted)', border: '1px solid var(--border-muted)' }}
                >
                  {label}
                </span>
              ))}
            </div>

            <button
              onClick={() => setAuthModalOpen(true)}
              className="mt-8 px-6 py-2.5 text-sm font-semibold rounded-md transition-colors duration-150 inline-flex items-center gap-2"
              style={{ background: 'var(--accent)', color: 'var(--accent-ink)' }}
            >
              Get Started
            </button>
            <p className="text-[11px] mt-3" style={{ color: 'var(--ink-faint)' }}>
              Free to use · No credit card required
            </p>
          </div>
        </div>
      ) : projects.length === 0 && !loadingProjects ? (
        /* ─── Empty State: First Notebook ─── */
        <div className="flex-1 flex flex-col items-center justify-center p-6 select-text" style={{ background: 'var(--canvas)' }}>
          <div className="max-w-sm text-center">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4"
              style={{ background: 'var(--accent-muted)' }}
            >
              <FolderPlus className="w-6 h-6" style={{ color: 'var(--accent)' }} />
            </div>
            <h2 className="text-lg font-semibold" style={{ color: 'var(--ink)' }}>Create your first notebook</h2>
            <p className="text-sm mt-2 leading-relaxed" style={{ color: 'var(--ink-muted)' }}>
              Notebooks organize your research sources, embeddings, and conversations into focused workspaces.
            </p>
            <button
              onClick={() => setProjectModalOpen(true)}
              className="mt-5 px-5 py-2 text-sm font-semibold rounded-md transition-colors duration-150 inline-flex items-center gap-2"
              style={{ background: 'var(--accent)', color: 'var(--accent-ink)' }}
            >
              <Plus className="w-4 h-4" />
              <span>Create Notebook</span>
            </button>
          </div>
        </div>
      ) : (
        /* ─── Three-Panel Workspace ─── */
        <div className="flex-1 flex flex-row min-h-0 overflow-hidden relative">
          {/* 1. Left Sidebar: Sources (Desktop) */}
          <div className="hidden lg:block h-full flex-shrink-0 transition-all duration-200">
            <SourcesSidebar
              sources={sources}
              isCollapsed={leftCollapsed}
              onToggleCollapse={toggleLeftSidebar}
              onOpenAddModal={() => setAddSourcesModalOpen(true)}
              onDeleteSource={handleDeleteSource}
              onRetrySource={handleRetrySource}
              loading={loadingSources}
            />
          </div>

          {/* Mobile Overlay Drawer: Sources */}
          {mobileDrawer === 'sources' && (
            <div className="lg:hidden fixed inset-0 z-40 flex">
              <div
                className="fixed inset-0 animate-fadeIn"
                style={{ background: 'rgba(0,0,0,0.5)' }}
                onClick={() => setMobileDrawer(null)}
              />
              <div
                className="relative w-80 max-w-[85vw] h-full shadow-modal z-50 animate-slideInLeft"
                style={{ background: 'var(--surface)' }}
              >
                <SourcesSidebar
                  sources={sources}
                  isCollapsed={false}
                  onToggleCollapse={() => setMobileDrawer(null)}
                  onOpenAddModal={() => {
                    setMobileDrawer(null);
                    setAddSourcesModalOpen(true);
                  }}
                  onDeleteSource={handleDeleteSource}
                  onRetrySource={handleRetrySource}
                  loading={loadingSources}
                />
              </div>
            </div>
          )}

          {/* 2. Center Panel: AI Conversation */}
          <main className="flex-1 min-w-0 h-full flex flex-col overflow-hidden relative" style={{ background: 'var(--canvas)' }}>
            <ChatPanel
              activeProject={activeProject}
              activeConversation={activeConversation}
              conversations={conversations}
              onSelectConversation={handleSelectConversation}
              onNewChat={handleNewChat}
              onConversationCreated={handleConversationCreated}
              onConversationUpdated={fetchConversations}
              sourceCount={activeSuccessfulSources.length}
            />
          </main>

          {/* 3. Right Sidebar: Learning Studio (Desktop) */}
          <div className="hidden lg:block h-full flex-shrink-0 transition-all duration-200">
            <StudioSidebar
              isCollapsed={rightCollapsed}
              onToggleCollapse={toggleRightSidebar}
              onSelectTool={(tool) => setActiveStudioTool(tool)}
              sourceCount={activeSuccessfulSources.length}
            />
          </div>

          {/* Mobile Overlay Drawer: Learning Studio */}
          {mobileDrawer === 'studio' && (
            <div className="lg:hidden fixed inset-0 z-40 flex justify-end">
              <div
                className="fixed inset-0 animate-fadeIn"
                style={{ background: 'rgba(0,0,0,0.5)' }}
                onClick={() => setMobileDrawer(null)}
              />
              <div
                className="relative w-80 max-w-[85vw] h-full shadow-modal z-50 animate-slideInRight"
                style={{ background: 'var(--surface)' }}
              >
                <StudioSidebar
                  isCollapsed={false}
                  onToggleCollapse={() => setMobileDrawer(null)}
                  onSelectTool={(tool) => {
                    setMobileDrawer(null);
                    setActiveStudioTool(tool);
                  }}
                  sourceCount={activeSuccessfulSources.length}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════
          Modals
          ═══════════════════════════════════════ */}
      {activeProject && (
        <AddSourcesModal
          isOpen={addSourcesModalOpen}
          onClose={() => setAddSourcesModalOpen(false)}
          projectId={activeProject.id || activeProject._id!}
          projectName={activeProject.name}
          onSourcesAdded={() => {
            fetchSources();
            fetchProjects();
          }}
        />
      )}

      {activeProject && (
        <StudioToolModal
          isOpen={Boolean(activeStudioTool)}
          onClose={() => setActiveStudioTool(null)}
          toolType={activeStudioTool}
          projectId={activeProject.id || activeProject._id!}
          projectName={activeProject.name}
        />
      )}

      <ProjectModal
        isOpen={projectModalOpen}
        onClose={() => setProjectModalOpen(false)}
        onProjectCreated={handleProjectCreated}
      />

      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        canClose={true}
      />
    </div>
  );
}

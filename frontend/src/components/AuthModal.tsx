'use client';
import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { BookOpen, Lock, Mail, User, AlertCircle, Loader2, X } from 'lucide-react';

interface AuthModalProps {
  isOpen: boolean;
  onClose?: () => void;
  canClose?: boolean;
}

export function AuthModal({ isOpen, onClose, canClose = false }: AuthModalProps) {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanEmail = email.trim();
    if (!cleanEmail || !cleanEmail.includes('@')) {
      setError('Please provide a valid email address.');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    if (isRegister && !name.trim()) {
      setError('Please provide your name.');
      return;
    }

    setLoading(true);
    try {
      if (isRegister) {
        await register(name.trim(), cleanEmail, password);
      } else {
        await login(cleanEmail, password);
      }
      onClose?.();
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fadeIn"
      style={{ background: 'rgba(0, 0, 0, 0.65)', backdropFilter: 'blur(4px)' }}
    >
      <div
        className="rounded-2xl shadow-modal w-full max-w-md overflow-hidden relative animate-scaleIn"
        style={{
          background: 'var(--surface-overlay)',
          border: '1px solid var(--border)',
          color: 'var(--ink)',
        }}
      >
        {canClose && onClose && (
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-lg transition-colors hover:opacity-80"
            style={{ color: 'var(--ink-faint)' }}
            title="Close dialog"
          >
            <X className="w-5 h-5" />
          </button>
        )}

        {/* Modal Header */}
        <div className="px-6 pt-8 pb-4 text-center">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-3"
            style={{
              background: 'var(--accent-muted)',
              color: 'var(--accent)',
              border: '1px solid var(--accent)',
            }}
          >
            <BookOpen className="w-6 h-6" />
          </div>
          <h2 className="text-[18px] font-bold tracking-tight" style={{ color: 'var(--ink)' }}>
            {isRegister ? 'Create Your Account' : 'Welcome Back'}
          </h2>
          <p className="text-[12px] mt-1" style={{ color: 'var(--ink-muted)' }}>
            {isRegister
              ? 'Organize research notebooks and save your cross-source insights'
              : 'Sign in to access your research notebooks and learning tools'}
          </p>
        </div>

        {/* Tab Toggle */}
        <div className="px-6 pb-2">
          <div
            className="flex p-1 rounded-lg"
            style={{ background: 'var(--canvas-alt)', border: '1px solid var(--border)' }}
          >
            <button
              type="button"
              onClick={() => {
                setIsRegister(false);
                setError(null);
              }}
              className="flex-1 py-1.5 text-[12px] font-semibold rounded-md transition-colors"
              style={{
                background: !isRegister ? 'var(--surface)' : 'transparent',
                color: !isRegister ? 'var(--ink)' : 'var(--ink-muted)',
                boxShadow: !isRegister ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
              }}
            >
              Log In
            </button>
            <button
              type="button"
              onClick={() => {
                setIsRegister(true);
                setError(null);
              }}
              className="flex-1 py-1.5 text-[12px] font-semibold rounded-md transition-colors"
              style={{
                background: isRegister ? 'var(--surface)' : 'transparent',
                color: isRegister ? 'var(--ink)' : 'var(--ink-muted)',
                boxShadow: isRegister ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
              }}
            >
              Create Account
            </button>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div
              className="p-3 rounded-lg flex items-start gap-2 text-[12px]"
              style={{
                background: 'var(--negative-muted)',
                border: '1px solid var(--negative)',
                color: 'var(--negative)',
              }}
            >
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {isRegister && (
            <div>
              <label className="block text-[12px] font-semibold mb-1.5" style={{ color: 'var(--ink)' }}>
                Full Name
              </label>
              <div className="relative">
                <User className="w-4 h-4 absolute left-3.5 top-3" style={{ color: 'var(--ink-faint)' }} />
                <input
                  type="text"
                  required={isRegister}
                  placeholder="e.g. Marie Curie"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full pl-10 pr-3.5 py-2.5 text-[13px] rounded-lg focus:outline-none transition-colors"
                  style={{
                    background: 'var(--canvas-alt)',
                    border: '1px solid var(--border)',
                    color: 'var(--ink)',
                  }}
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-[12px] font-semibold mb-1.5" style={{ color: 'var(--ink)' }}>
              Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 absolute left-3.5 top-3" style={{ color: 'var(--ink-faint)' }} />
              <input
                type="email"
                required
                placeholder="you@domain.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-10 pr-3.5 py-2.5 text-[13px] rounded-lg focus:outline-none transition-colors"
                style={{
                  background: 'var(--canvas-alt)',
                  border: '1px solid var(--border)',
                  color: 'var(--ink)',
                }}
              />
            </div>
          </div>

          <div>
            <label className="block text-[12px] font-semibold mb-1.5" style={{ color: 'var(--ink)' }}>
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3.5 top-3" style={{ color: 'var(--ink-faint)' }} />
              <input
                type="password"
                required
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-3.5 py-2.5 text-[13px] rounded-lg focus:outline-none transition-colors"
                style={{
                  background: 'var(--canvas-alt)',
                  border: '1px solid var(--border)',
                  color: 'var(--ink)',
                }}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 font-semibold text-[13px] rounded-lg shadow-sm transition-opacity hover:opacity-90 flex items-center justify-center gap-2 mt-2"
            style={{
              background: 'var(--accent)',
              color: 'var(--accent-ink)',
            }}
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>{isRegister ? 'Register & Continue' : 'Sign In'}</span>
          </button>
        </form>

        <div
          className="px-6 py-3.5 text-center text-[11px]"
          style={{
            background: 'var(--canvas-alt)',
            borderTop: '1px solid var(--border)',
            color: 'var(--ink-faint)',
          }}
        >
          Secured with Argon2id password hashing & HttpOnly authentication
        </div>
      </div>
    </div>
  );
}

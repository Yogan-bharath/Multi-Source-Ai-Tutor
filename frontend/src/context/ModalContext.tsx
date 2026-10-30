'use client';
import React, { createContext, useContext, useState, useRef, useEffect, ReactNode } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, Info, Trash2, X } from 'lucide-react';

export interface ConfirmOptions {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  type?: 'danger' | 'warning' | 'info';
}

export interface AlertOptions {
  title: string;
  message: string;
  buttonText?: string;
  type?: 'error' | 'warning' | 'info' | 'success';
}

interface ModalContextType {
  confirmModal: (options: ConfirmOptions) => Promise<boolean>;
  alertModal: (options: AlertOptions) => Promise<void>;
}

const ModalContext = createContext<ModalContextType | undefined>(undefined);

export function ModalProvider({ children }: { children: ReactNode }) {
  // Confirm state
  const [confirmConfig, setConfirmConfig] = useState<ConfirmOptions | null>(null);
  const confirmResolverRef = useRef<((value: boolean) => void) | null>(null);

  // Alert state
  const [alertConfig, setAlertConfig] = useState<AlertOptions | null>(null);
  const alertResolverRef = useRef<(() => void) | null>(null);

  const confirmModal = (options: ConfirmOptions): Promise<boolean> => {
    return new Promise<boolean>((resolve) => {
      confirmResolverRef.current = resolve;
      setConfirmConfig(options);
    });
  };

  const alertModal = (options: AlertOptions): Promise<void> => {
    return new Promise<void>((resolve) => {
      alertResolverRef.current = resolve;
      setAlertConfig(options);
    });
  };

  const handleConfirmClose = (result: boolean) => {
    if (confirmResolverRef.current) {
      confirmResolverRef.current(result);
      confirmResolverRef.current = null;
    }
    setConfirmConfig(null);
  };

  const handleAlertClose = () => {
    if (alertResolverRef.current) {
      alertResolverRef.current();
      alertResolverRef.current = null;
    }
    setAlertConfig(null);
  };

  // Keyboard shortcut listener (Escape & Enter)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (confirmConfig) {
        if (e.key === 'Escape') {
          handleConfirmClose(false);
        } else if (e.key === 'Enter') {
          handleConfirmClose(true);
        }
      } else if (alertConfig) {
        if (e.key === 'Escape' || e.key === 'Enter') {
          handleAlertClose();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [confirmConfig, alertConfig]);

  return (
    <ModalContext.Provider value={{ confirmModal, alertModal }}>
      {children}

      {/* Themed Confirmation Pop-up Window */}
      {confirmConfig && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 animate-fadeIn"
          style={{ background: 'rgba(0, 0, 0, 0.65)', backdropFilter: 'blur(4px)' }}
          onClick={() => handleConfirmClose(false)}
        >
          <div
            className="rounded-2xl shadow-modal max-w-md w-full overflow-hidden animate-scaleIn relative"
            style={{
              background: 'var(--surface-overlay)',
              border: '1px solid var(--border)',
              color: 'var(--ink)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <button
              onClick={() => handleConfirmClose(false)}
              className="absolute top-4 right-4 p-1.5 rounded-lg transition-colors hover:opacity-80"
              style={{ color: 'var(--ink-faint)' }}
              title="Close dialog"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="p-6">
              <div className="flex items-start gap-4">
                <div
                  className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{
                    background:
                      confirmConfig.type === 'danger'
                        ? 'var(--negative-muted)'
                        : confirmConfig.type === 'warning'
                        ? 'var(--caution-muted)'
                        : 'var(--accent-muted)',
                    color:
                      confirmConfig.type === 'danger'
                        ? 'var(--negative)'
                        : confirmConfig.type === 'warning'
                        ? 'var(--caution)'
                        : 'var(--accent)',
                    border: `1px solid ${
                      confirmConfig.type === 'danger'
                        ? 'var(--negative)'
                        : confirmConfig.type === 'warning'
                        ? 'var(--caution)'
                        : 'var(--accent)'
                    }`,
                  }}
                >
                  {confirmConfig.type === 'danger' ? (
                    <Trash2 className="w-5 h-5" />
                  ) : confirmConfig.type === 'warning' ? (
                    <AlertTriangle className="w-5 h-5" />
                  ) : (
                    <Info className="w-5 h-5" />
                  )}
                </div>

                <div className="flex-1 pr-4">
                  <h3 className="text-[15px] font-bold leading-snug" style={{ color: 'var(--ink)' }}>
                    {confirmConfig.title}
                  </h3>
                  <p className="text-[13px] mt-1.5 leading-relaxed break-words" style={{ color: 'var(--ink-muted)' }}>
                    {confirmConfig.message}
                  </p>
                </div>
              </div>

              {/* Actions */}
              <div
                className="flex items-center justify-end gap-2.5 mt-6 pt-4"
                style={{ borderTop: '1px solid var(--border-muted)' }}
              >
                <button
                  type="button"
                  onClick={() => handleConfirmClose(false)}
                  className="px-4 py-2 text-[13px] font-medium rounded-lg transition-colors duration-150 hover:opacity-85"
                  style={{
                    background: 'var(--canvas-alt)',
                    color: 'var(--ink-muted)',
                    border: '1px solid var(--border)',
                  }}
                >
                  {confirmConfig.cancelText || 'Cancel'}
                </button>
                <button
                  type="button"
                  onClick={() => handleConfirmClose(true)}
                  className="px-4 py-2 text-[13px] font-semibold rounded-lg text-white transition-opacity duration-150 hover:opacity-90 shadow-sm"
                  style={{
                    background:
                      confirmConfig.type === 'danger'
                        ? 'var(--negative)'
                        : confirmConfig.type === 'warning'
                        ? 'var(--caution)'
                        : 'var(--accent)',
                    color: '#FFFFFF',
                  }}
                >
                  {confirmConfig.confirmText || 'Confirm'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Themed Notification / Alert Pop-up Window */}
      {alertConfig && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 animate-fadeIn"
          style={{ background: 'rgba(0, 0, 0, 0.65)', backdropFilter: 'blur(4px)' }}
          onClick={handleAlertClose}
        >
          <div
            className="rounded-2xl shadow-modal max-w-md w-full overflow-hidden animate-scaleIn relative"
            style={{
              background: 'var(--surface-overlay)',
              border: '1px solid var(--border)',
              color: 'var(--ink)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <button
              onClick={handleAlertClose}
              className="absolute top-4 right-4 p-1.5 rounded-lg transition-colors hover:opacity-80"
              style={{ color: 'var(--ink-faint)' }}
              title="Close alert"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="p-6">
              <div className="flex items-start gap-4">
                <div
                  className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{
                    background:
                      alertConfig.type === 'error'
                        ? 'var(--negative-muted)'
                        : alertConfig.type === 'warning'
                        ? 'var(--caution-muted)'
                        : alertConfig.type === 'success'
                        ? 'var(--positive-muted)'
                        : 'var(--accent-muted)',
                    color:
                      alertConfig.type === 'error'
                        ? 'var(--negative)'
                        : alertConfig.type === 'warning'
                        ? 'var(--caution)'
                        : alertConfig.type === 'success'
                        ? 'var(--positive)'
                        : 'var(--accent)',
                    border: `1px solid ${
                      alertConfig.type === 'error'
                        ? 'var(--negative)'
                        : alertConfig.type === 'warning'
                        ? 'var(--caution)'
                        : alertConfig.type === 'success'
                        ? 'var(--positive)'
                        : 'var(--accent)'
                    }`,
                  }}
                >
                  {alertConfig.type === 'error' ? (
                    <AlertCircle className="w-5 h-5" />
                  ) : alertConfig.type === 'warning' ? (
                    <AlertTriangle className="w-5 h-5" />
                  ) : alertConfig.type === 'success' ? (
                    <CheckCircle2 className="w-5 h-5" />
                  ) : (
                    <Info className="w-5 h-5" />
                  )}
                </div>

                <div className="flex-1 pr-4">
                  <h3 className="text-[15px] font-bold leading-snug" style={{ color: 'var(--ink)' }}>
                    {alertConfig.title}
                  </h3>
                  <p
                    className="text-[13px] mt-1.5 leading-relaxed break-words whitespace-pre-wrap"
                    style={{ color: 'var(--ink-muted)' }}
                  >
                    {alertConfig.message}
                  </p>
                </div>
              </div>

              {/* Actions */}
              <div
                className="flex items-center justify-end mt-6 pt-4"
                style={{ borderTop: '1px solid var(--border-muted)' }}
              >
                <button
                  type="button"
                  onClick={handleAlertClose}
                  className="px-5 py-2 text-[13px] font-semibold rounded-lg text-white transition-opacity duration-150 hover:opacity-90 shadow-sm"
                  style={{ background: 'var(--accent)', color: 'var(--accent-ink)' }}
                >
                  {alertConfig.buttonText || 'Understood'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </ModalContext.Provider>
  );
}

export function useModal() {
  const context = useContext(ModalContext);
  if (!context) {
    throw new Error('useModal must be used within a ModalProvider');
  }
  return context;
}

'use client';

import React, { useState } from 'react';
import { loginUser, registerUser } from '@/lib/api';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: any) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isLogin) {
        const res = await loginUser(username || email, password);
        onSuccess(res.user);
      } else {
        const res = await registerUser(username, email, password);
        onSuccess(res.user);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-[2px] p-4">
      <div className="relative w-full max-w-md rounded-3xl bg-white border border-zinc-200 p-7 shadow-2xl text-zinc-900">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-zinc-400 hover:text-zinc-800 text-xl font-bold"
        >
          &times;
        </button>

        <div className="mb-6 text-center">
          <h2 className="text-2xl font-semibold text-zinc-900">
            {isLogin ? 'Welcome Back to DocuBrain' : 'Create DocuBrain Account'}
          </h2>
          <p className="text-sm text-zinc-500 mt-1">
            {isLogin ? 'Log in to access your secure RAG documents & MCP tools' : 'Sign up to upload and isolate your personal document database'}
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs text-center">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">Email Address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@docubrain.ai"
                className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-zinc-300 text-zinc-900 placeholder-zinc-400 focus:outline-none focus:border-zinc-500 text-sm"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-zinc-600 mb-1">
              {isLogin ? 'Username or Email' : 'Username'}
            </label>
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={isLogin ? 'username or email' : 'johndoe'}
              className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-zinc-300 text-zinc-900 placeholder-zinc-400 focus:outline-none focus:border-zinc-500 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-600 mb-1">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-zinc-300 text-zinc-900 placeholder-zinc-400 focus:outline-none focus:border-zinc-500 text-sm"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-full bg-zinc-900 hover:bg-zinc-700 text-white font-medium text-sm transition-colors disabled:opacity-50"
          >
            {loading ? 'Processing...' : isLogin ? 'Log In' : 'Sign Up'}
          </button>
        </form>

        <div className="mt-5 text-center text-sm text-zinc-500">
          {isLogin ? "Don't have an account?" : 'Already registered?'}{' '}
          <button
            onClick={() => {
              setIsLogin(!isLogin);
              setError(null);
            }}
            className="text-zinc-900 hover:underline font-medium"
          >
            {isLogin ? 'Create Account' : 'Log In Here'}
          </button>
        </div>
      </div>
    </div>
  );
};

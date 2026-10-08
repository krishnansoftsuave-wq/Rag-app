'use client';

import React from 'react';
import { PanelLeftClose, SquarePen, Library, Plug, Trash2, LogOut, LogIn, Sparkles, Loader2 } from 'lucide-react';
import { ChatSession } from '@/types';

interface SidebarProps {
  chats: ChatSession[];
  activeChatId: string | null;
  pendingChatIds: Set<string>;
  documentsCount: number;
  isBackendConnected: boolean;
  currentUser?: any;
  onNewChat: () => void;
  onSelectChat: (chatId: string) => void;
  onDeleteChat: (chatId: string) => void;
  onOpenLibrary: () => void;
  onOpenMcp: () => void;
  onLogin: () => void;
  onLogout: () => void;
  onClose: () => void;
}

const DAY_MS = 24 * 60 * 60 * 1000;

/** Chats grouped the way ChatGPT does: Today, Yesterday, Previous 7 days, Older. */
function groupChats(chats: ChatSession[]): { label: string; chats: ChatSession[] }[] {
  const startOfToday = new Date().setHours(0, 0, 0, 0);
  const groups: Record<string, ChatSession[]> = { Today: [], Yesterday: [], 'Previous 7 days': [], Older: [] };
  for (const chat of chats) {
    if (chat.updatedAt >= startOfToday) groups.Today.push(chat);
    else if (chat.updatedAt >= startOfToday - DAY_MS) groups.Yesterday.push(chat);
    else if (chat.updatedAt >= startOfToday - 7 * DAY_MS) groups['Previous 7 days'].push(chat);
    else groups.Older.push(chat);
  }
  return Object.entries(groups)
    .filter(([, list]) => list.length > 0)
    .map(([label, list]) => ({ label, chats: list }));
}

const NavItem: React.FC<{ icon: React.ReactNode; label: string; badge?: React.ReactNode; onClick: () => void }> = ({
  icon,
  label,
  badge,
  onClick,
}) => (
  <button
    onClick={onClick}
    className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-zinc-700 hover:bg-zinc-200/60 transition-colors"
  >
    <span className="text-zinc-500">{icon}</span>
    <span className="flex-1 text-left">{label}</span>
    {badge}
  </button>
);

export const Sidebar: React.FC<SidebarProps> = ({
  chats,
  activeChatId,
  pendingChatIds,
  documentsCount,
  isBackendConnected,
  currentUser,
  onNewChat,
  onSelectChat,
  onDeleteChat,
  onOpenLibrary,
  onOpenMcp,
  onLogin,
  onLogout,
  onClose,
}) => (
  <div className="h-full w-[260px] flex flex-col bg-zinc-50 border-r border-zinc-200">
    {/* Brand */}
    <div className="h-14 shrink-0 flex items-center justify-between px-3">
      <div className="flex items-center gap-2 px-1">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 flex items-center justify-center text-white">
          <Sparkles className="w-4 h-4" />
        </div>
        <span className="font-semibold text-zinc-900">DocuBrain</span>
      </div>
      <button
        onClick={onClose}
        className="p-2 rounded-lg text-zinc-500 hover:text-zinc-800 hover:bg-zinc-200/60"
        title="Close sidebar"
      >
        <PanelLeftClose className="w-[18px] h-[18px]" />
      </button>
    </div>

    {/* Actions */}
    <nav className="px-2 space-y-0.5">
      <NavItem icon={<SquarePen className="w-4 h-4" />} label="New chat" onClick={onNewChat} />
      <NavItem
        icon={<Library className="w-4 h-4" />}
        label="Documents"
        onClick={onOpenLibrary}
        badge={<span className="text-xs text-zinc-500 tabular-nums">{documentsCount}</span>}
      />
      <NavItem icon={<Plug className="w-4 h-4" />} label="MCP servers" onClick={onOpenMcp} />
    </nav>

    {/* History */}
    <div className="flex-1 overflow-y-auto px-2 mt-4 pb-2">
      {chats.length === 0 ? (
        <p className="px-2.5 text-xs text-zinc-400">Your chats will appear here.</p>
      ) : (
        groupChats(chats).map((group) => (
          <div key={group.label} className="mb-4">
            <p className="px-2.5 pb-1 text-xs font-medium text-zinc-500">{group.label}</p>
            {group.chats.map((chat) => {
              const isActive = chat.id === activeChatId;
              return (
                <div
                  key={chat.id}
                  onClick={() => onSelectChat(chat.id)}
                  className={`group flex items-center gap-1 pl-2.5 pr-1 py-1.5 rounded-lg cursor-pointer text-sm ${
                    isActive ? 'bg-zinc-200/80 text-zinc-900' : 'text-zinc-700 hover:bg-zinc-200/50'
                  }`}
                >
                  <span className="flex-1 truncate" title={chat.title}>
                    {chat.title}
                  </span>
                  {pendingChatIds.has(chat.id) && <Loader2 className="w-3.5 h-3.5 text-zinc-400 animate-spin shrink-0" />}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(`Delete "${chat.title}"?`)) onDeleteChat(chat.id);
                    }}
                    className={`p-1 rounded-md text-zinc-400 hover:text-rose-600 hover:bg-white shrink-0 ${
                      isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 focus:opacity-100'
                    }`}
                    title="Delete chat"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        ))
      )}
    </div>

    {/* Status & account */}
    <div className="shrink-0 border-t border-zinc-200 p-2 space-y-1">
      <div className="flex items-center gap-2 px-2.5 py-1 text-xs text-zinc-500">
        <span className={`w-2 h-2 rounded-full ${isBackendConnected ? 'bg-emerald-500' : 'bg-rose-500'}`} />
        {isBackendConnected ? 'Backend online' : 'Backend offline'}
      </div>
      {currentUser ? (
        <div className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg hover:bg-zinc-200/50">
          <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm font-semibold uppercase shrink-0">
            {(currentUser.username || '?').charAt(0)}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-zinc-800 truncate">{currentUser.username}</p>
            {currentUser.email && <p className="text-xs text-zinc-500 truncate">{currentUser.email}</p>}
          </div>
          <button
            onClick={onLogout}
            className="p-1.5 rounded-md text-zinc-400 hover:text-rose-600 hover:bg-white"
            title="Log out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <button
          onClick={onLogin}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-white text-sm font-medium"
        >
          <LogIn className="w-4 h-4" />
          Log in
        </button>
      )}
    </div>
  </div>
);

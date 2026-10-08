'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChatMessage, ChatSession } from '@/types';

const STORAGE_PREFIX = 'docubrain_chats:';
const MAX_CHATS = 50;

export const newId = (prefix: string) => `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;

// The agent's per-step traces are large and not shown in the chat, so they are not stored
const forStorage = (m: ChatMessage): ChatMessage => ({
  ...m,
  agent_result: m.agent_result && { ...m.agent_result, trace: [] },
  workflow_result: m.workflow_result && { ...m.workflow_result, trace: [] },
});

function readChats(key: string): ChatSession[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeChats(key: string, chats: ChatSession[]) {
  let keep = chats.slice(0, MAX_CHATS).map((c) => ({ ...c, messages: c.messages.map(forStorage) }));
  for (;;) {
    try {
      localStorage.setItem(key, JSON.stringify(keep));
      return;
    } catch {
      // Storage full (or unavailable): keep the newest half and try again
      if (keep.length <= 1) return;
      keep = keep.slice(0, Math.ceil(keep.length / 2));
    }
  }
}

/**
 * The sidebar's conversations, saved in this browser for one owner (a user id, or "guest").
 * Loaded after mount, so the server render and the first client render agree.
 */
export function useChatSessions(owner: string) {
  const key = STORAGE_PREFIX + owner;
  const [store, setStore] = useState<{ key: string | null; chats: ChatSession[] }>({ key: null, chats: [] });

  useEffect(() => {
    setStore({ key, chats: readChats(key) });
  }, [key]);

  useEffect(() => {
    if (store.key) writeChats(store.key, store.chats);
  }, [store]);

  const update = useCallback((fn: (chats: ChatSession[]) => ChatSession[]) => {
    setStore((s) => (s.key ? { ...s, chats: fn(s.chats) } : s));
  }, []);

  const createChat = useCallback(
    (title: string): string => {
      const id = newId('chat');
      const now = Date.now();
      update((chats) => [{ id, title, createdAt: now, updatedAt: now, messages: [] }, ...chats]);
      return id;
    },
    [update]
  );

  const appendMessage = useCallback(
    (chatId: string, message: ChatMessage) =>
      update((chats) =>
        chats.map((c) => (c.id === chatId ? { ...c, updatedAt: Date.now(), messages: [...c.messages, message] } : c))
      ),
    [update]
  );

  const removeMessage = useCallback(
    (chatId: string, messageId: string) =>
      update((chats) =>
        chats.map((c) => (c.id === chatId ? { ...c, messages: c.messages.filter((m) => m.id !== messageId) } : c))
      ),
    [update]
  );

  const deleteChat = useCallback((chatId: string) => update((chats) => chats.filter((c) => c.id !== chatId)), [update]);

  const chats = useMemo(
    () => (store.key === key ? [...store.chats].sort((a, b) => b.updatedAt - a.updatedAt) : []),
    [store, key]
  );

  return { chats, createChat, appendMessage, removeMessage, deleteChat };
}

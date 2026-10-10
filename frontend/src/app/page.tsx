'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Menu, PanelLeftOpen, SquarePen } from 'lucide-react';
import { Sidebar } from '@/components/Sidebar';
import { ChatInterface } from '@/components/ChatInterface';
import { AuthModal } from '@/components/AuthModal';
import McpServerManagerModal from '@/components/McpServerManagerModal';
import { fetchHealth, fetchDocuments, deleteDocument, fetchCurrentUser, removeAuthToken, sendChatMessage } from '@/lib/api';
import { useChatSessions, newId } from '@/lib/chatSessions';
import { AnswerMode, ChatAttachment, DocumentMetadata } from '@/types';

const ANSWER_MODE_KEY = 'docubrain_answer_mode';

const timeNow = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const chatTitle = (question: string) => (question.length > 48 ? `${question.slice(0, 47).trimEnd()}…` : question);

export default function Home() {
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null); // null: search all documents
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);
  const [isMcpModalOpen, setIsMcpModalOpen] = useState<boolean>(false);
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true); // desktop
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);
  const [isLibraryOpen, setIsLibraryOpen] = useState<boolean>(false);
  const [activeChatId, setActiveChatId] = useState<string | null>(null); // null: a new, empty chat
  const [pendingChatIds, setPendingChatIds] = useState<Set<string>>(new Set());
  const [answerMode, setAnswerMode] = useState<AnswerMode>('agent'); // who answers: the single agent or the team

  const { chats, createChat, appendMessage, removeMessage, deleteChat } = useChatSessions(
    currentUser?.id || currentUser?.user_id || 'guest'
  );
  const activeChat = chats.find((c) => c.id === activeChatId) || null;

  // Keep the Single / Team choice across visits
  useEffect(() => {
    try {
      const saved = localStorage.getItem(ANSWER_MODE_KEY);
      if (saved === 'agent' || saved === 'team') setAnswerMode(saved);
    } catch (e) {}
  }, []);

  const changeAnswerMode = (mode: AnswerMode) => {
    setAnswerMode(mode);
    try {
      localStorage.setItem(ANSWER_MODE_KEY, mode);
    } catch (e) {}
  };

  // Load Current User session on mount
  useEffect(() => {
    const savedUser = localStorage.getItem('docubrain_user');
    if (savedUser) {
      try {
        setCurrentUser(JSON.parse(savedUser));
      } catch (e) {}
    }

    fetchCurrentUser().then((user) => {
      if (user && user.user_id !== 'default_user') {
        setCurrentUser(user);
        localStorage.setItem('docubrain_user', JSON.stringify(user));
      }
    });
  }, []);

  // Poll backend health & fetch documents
  const loadData = async () => {
    try {
      const health = await fetchHealth();
      setIsBackendConnected(health.status === 'healthy');

      const docsRes = await fetchDocuments();
      setDocuments(docsRes.documents);
      // Drop the selection if that document was removed (e.g. from another tab)
      setSelectedDocId((id) => (id && docsRes.documents.some((d) => d.doc_id === id) ? id : null));
    } catch (err) {
      setIsBackendConnected(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  // The open chat was deleted, or belongs to the user who just logged out: start a new one
  useEffect(() => {
    if (activeChatId && !activeChat) setActiveChatId(null);
  }, [activeChatId, activeChat]);

  const handleUploadSuccess = (newDoc: DocumentMetadata) => {
    setDocuments((prev) => [newDoc, ...prev.filter((d) => d.doc_id !== newDoc.doc_id)]);
    loadData();
  };

  const handleDeleteDoc = async (docId: string) => {
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docId));
      setSelectedDocId((id) => (id === docId ? null : id));
      loadData();
    } catch (err) {
      alert('Failed to delete document');
    }
  };

  const handleLogout = () => {
    removeAuthToken();
    setCurrentUser(null);
    loadData();
  };

  // Ask the single agent or the team and add its answer (or the error) to the chat the question was asked in
  const runQuestion = async (chatId: string, question: string, mode: AnswerMode, attachment?: ChatAttachment) => {
    setPendingChatIds((prev) => new Set(prev).add(chatId));
    try {
      const response = await sendChatMessage(question, attachment ? [attachment.doc_id] : undefined, mode);
      // A backend from before the team mode existed answers an unknown mode with its default comparison
      if (response.mode !== mode) {
        throw new Error(
          `Asked the ${mode === 'team' ? 'team' : 'single agent'}, but the backend answered in "${response.mode}" mode. ` +
            'Restart the backend so it loads the latest code, then try again.'
        );
      }
      appendMessage(chatId, {
        id: newId('msg'),
        sender: 'assistant',
        text: response.answer,
        timestamp: timeNow(),
        sources: response.sources,
        used_fallback: response.used_fallback,
        mode: response.mode,
        agent_result: response.agent_result,
        team_result: response.team_result,
        workflow_result: response.workflow_result,
        comparison: response.comparison,
        mcp_results: response.mcp_results,
      });
    } catch (err: any) {
      appendMessage(chatId, {
        id: newId('msg'),
        sender: 'assistant',
        text: err.message || 'Unable to connect to the backend server.',
        timestamp: timeNow(),
        error: true,
      });
    } finally {
      setPendingChatIds((prev) => {
        const next = new Set(prev);
        next.delete(chatId);
        return next;
      });
    }
  };

  const handleSend = (question: string) => {
    const doc = documents.find((d) => d.doc_id === selectedDocId);
    const attachment = doc ? { doc_id: doc.doc_id, filename: doc.filename } : undefined;
    let chatId = activeChat?.id;
    if (!chatId) {
      chatId = createChat(chatTitle(question));
      setActiveChatId(chatId);
    }
    appendMessage(chatId, { id: newId('msg'), sender: 'user', text: question, timestamp: timeNow(), attachment, mode: answerMode });
    runQuestion(chatId, question, answerMode, attachment);
  };

  // Replace a failed answer with a new attempt at the question before it
  const handleRetry = (messageId: string) => {
    if (!activeChat || pendingChatIds.has(activeChat.id)) return;
    const index = activeChat.messages.findIndex((m) => m.id === messageId);
    const question = activeChat.messages.slice(0, index).reverse().find((m) => m.sender === 'user');
    if (!question) return;
    removeMessage(activeChat.id, messageId);
    // Ask again the way it was asked (questions from before the switch existed went to the single agent)
    runQuestion(activeChat.id, question.text, question.mode === 'team' ? 'team' : 'agent', question.attachment);
  };

  const openChat = useCallback((chatId: string | null) => {
    setActiveChatId(chatId);
    setIsMobileSidebarOpen(false);
    setIsLibraryOpen(false);
  }, []);

  const sidebar = (onClose: () => void) => (
    <Sidebar
      chats={chats}
      activeChatId={activeChat?.id || null}
      pendingChatIds={pendingChatIds}
      documentsCount={documents.length}
      isBackendConnected={isBackendConnected}
      currentUser={currentUser}
      onNewChat={() => openChat(null)}
      onSelectChat={(id) => openChat(id)}
      onDeleteChat={deleteChat}
      onOpenLibrary={() => {
        setIsMobileSidebarOpen(false);
        setIsLibraryOpen(true);
      }}
      onOpenMcp={() => setIsMcpModalOpen(true)}
      onLogin={() => setIsAuthModalOpen(true)}
      onLogout={handleLogout}
      onClose={onClose}
    />
  );

  return (
    <div className="h-dvh flex overflow-hidden bg-white text-zinc-900">
      {/* Desktop sidebar */}
      <aside
        className={`hidden md:block shrink-0 overflow-hidden transition-[width] duration-200 ${isSidebarOpen ? 'w-[260px]' : 'w-0'}`}
      >
        {sidebar(() => setIsSidebarOpen(false))}
      </aside>

      {/* Mobile sidebar drawer */}
      {isMobileSidebarOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/40" onClick={() => setIsMobileSidebarOpen(false)} />
          <aside className="absolute inset-y-0 left-0 shadow-2xl">{sidebar(() => setIsMobileSidebarOpen(false))}</aside>
        </div>
      )}

      <main className="flex-1 min-w-0 flex flex-col">
        <header className="h-14 shrink-0 flex items-center gap-1 px-3">
          <button
            onClick={() => setIsMobileSidebarOpen(true)}
            className="md:hidden p-2 rounded-lg text-zinc-600 hover:bg-zinc-100"
            title="Open sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>
          {!isSidebarOpen && (
            <>
              <button
                onClick={() => setIsSidebarOpen(true)}
                className="hidden md:flex p-2 rounded-lg text-zinc-500 hover:text-zinc-800 hover:bg-zinc-100"
                title="Open sidebar"
              >
                <PanelLeftOpen className="w-5 h-5" />
              </button>
              <button
                onClick={() => openChat(null)}
                className="hidden md:flex p-2 rounded-lg text-zinc-500 hover:text-zinc-800 hover:bg-zinc-100"
                title="New chat"
              >
                <SquarePen className="w-5 h-5" />
              </button>
            </>
          )}
          <div className="px-2 min-w-0 flex items-baseline gap-2">
            <span className="text-lg font-semibold text-zinc-800">DocuBrain</span>
            <span className="text-sm text-zinc-400 truncate hidden sm:inline">RAG Agent</span>
          </div>
          <button
            onClick={() => openChat(null)}
            className="md:hidden ml-auto p-2 rounded-lg text-zinc-600 hover:bg-zinc-100"
            title="New chat"
          >
            <SquarePen className="w-5 h-5" />
          </button>
        </header>

        <ChatInterface
          chatKey={activeChat?.id || 'new'}
          messages={activeChat?.messages || []}
          isPending={!!activeChat && pendingChatIds.has(activeChat.id)}
          userName={currentUser?.username}
          documents={documents}
          selectedDocId={selectedDocId}
          onSelectDoc={setSelectedDocId}
          onUploadSuccess={handleUploadSuccess}
          onDeleteDoc={handleDeleteDoc}
          isLibraryOpen={isLibraryOpen}
          onLibraryOpenChange={setIsLibraryOpen}
          onSend={handleSend}
          onRetry={handleRetry}
          answerMode={answerMode}
          onAnswerModeChange={changeAnswerMode}
        />
      </main>

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onSuccess={(user) => {
          setCurrentUser(user);
          loadData();
        }}
      />

      <McpServerManagerModal
        isOpen={isMcpModalOpen}
        onClose={() => setIsMcpModalOpen(false)}
      />
    </div>
  );
}

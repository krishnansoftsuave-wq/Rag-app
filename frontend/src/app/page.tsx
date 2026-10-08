'use client';

import React, { useState, useEffect } from 'react';
import { Header } from '@/components/Header';
import { DocumentUpload } from '@/components/DocumentUpload';
import { DocumentList } from '@/components/DocumentList';
import { ChatInterface } from '@/components/ChatInterface';
import { ApiKeyModal } from '@/components/ApiKeyModal';
import { AuthModal } from '@/components/AuthModal';
import { McpDocSelector } from '@/components/McpDocSelector';
import McpServerManagerModal from '@/components/McpServerManagerModal';
import { fetchHealth, fetchDocuments, deleteDocument, fetchCurrentUser, removeAuthToken } from '@/lib/api';
import { DocumentMetadata } from '@/types';

export default function Home() {
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [totalChunks, setTotalChunks] = useState<number>(0);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [apiKey, setApiKey] = useState<string>('');
  const [isApiKeyModalOpen, setIsApiKeyModalOpen] = useState<boolean>(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);
  const [isMcpModalOpen, setIsMcpModalOpen] = useState<boolean>(false);
  const [currentUser, setCurrentUser] = useState<any>(null);

  // Load API Key & Current User session on mount
  useEffect(() => {
    const savedKey = localStorage.getItem('rag_gemini_api_key');
    if (savedKey) setApiKey(savedKey);

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
      setTotalChunks(health.total_chunks);

      const docsRes = await fetchDocuments();
      setDocuments(docsRes.documents);
    } catch (err) {
      setIsBackendConnected(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleUploadSuccess = (newDoc: DocumentMetadata) => {
    setDocuments((prev) => [newDoc, ...prev]);
    loadData();
  };

  const handleToggleSelectDoc = (docId: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const handleDeleteDoc = async (docId: string) => {
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docId));
      setSelectedDocIds((prev) => prev.filter((id) => id !== docId));
      loadData();
    } catch (err) {
      alert('Failed to delete document');
    }
  };

  const handleSaveApiKey = (key: string) => {
    setApiKey(key);
    if (key) {
      localStorage.setItem('rag_gemini_api_key', key);
    } else {
      localStorage.removeItem('rag_gemini_api_key');
    }
  };

  const handleLogout = () => {
    removeAuthToken();
    setCurrentUser(null);
    loadData();
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <Header
        isBackendConnected={isBackendConnected}
        totalDocuments={documents.length}
        totalChunks={totalChunks}
        hasApiKey={Boolean(apiKey)}
        onOpenApiKeyModal={() => setIsApiKeyModalOpen(true)}
        onOpenMcpModal={() => setIsMcpModalOpen(true)}
        currentUser={currentUser}
        onOpenAuthModal={() => setIsAuthModalOpen(true)}
        onLogout={handleLogout}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Top MCP Document Targeted Selection Bar */}
        <McpDocSelector
          documents={documents}
          selectedDocId={selectedDocIds.length > 0 ? selectedDocIds[0] : null}
          onSelectDoc={(docId) => setSelectedDocIds(docId ? [docId] : [])}
          onRefreshDocs={loadData}
        />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Sidebar: Document Management */}
          <div className="lg:col-span-4 space-y-6 flex flex-col">
            <DocumentUpload onUploadSuccess={handleUploadSuccess} />
            <div className="flex-1 min-h-[350px]">
              <DocumentList
                documents={documents}
                selectedDocIds={selectedDocIds}
                onToggleSelectDoc={handleToggleSelectDoc}
                onDeleteDoc={handleDeleteDoc}
              />
            </div>
          </div>

          {/* Right Main Panel: Interactive Chat & Citations */}
          <div className="lg:col-span-8">
            <ChatInterface
              selectedDocIds={selectedDocIds}
              apiKey={apiKey}
              hasDocuments={documents.length > 0}
            />
          </div>
        </div>
      </main>

      <ApiKeyModal
        isOpen={isApiKeyModalOpen}
        onClose={() => setIsApiKeyModalOpen(false)}
        currentApiKey={apiKey}
        onSaveApiKey={handleSaveApiKey}
      />

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

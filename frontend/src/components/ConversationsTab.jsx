import { useState, useEffect } from "react";
import { apiClient } from "@/api/client";
import { ArrowLeft, MessageSquare } from "lucide-react";
import { toast } from "sonner";

import { Card, Badge, Button, Spinner } from "@/components/ui/Primitives";
import { EmptyState } from "@/components/ui/Stats";

/* ============================================================
   CONVERSATIONS TAB
   Browse / debug conversation history for an application.
   Rebuilt on the shared card, badge and button primitives.
   ============================================================ */

export default function ConversationsTab({ applicationId }) {
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [conversationMessages, setConversationMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDetailLoading, setIsDetailLoading] = useState(false);

  const loadConversations = async () => {
    setIsLoading(true);
    try {
      const res = await apiClient.get(`/admin/conversations/application/${applicationId}`);
      setConversations(res.data);
    } catch (e) {
      console.error(e);
      toast.error("Failed to load conversations.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;

    const fetchConversations = async () => {
      try {
        const res = await apiClient.get(`/admin/conversations/application/${applicationId}`);
        if (isMounted) setConversations(res.data);
      } catch (e) {
        console.error(e);
        if (isMounted) toast.error("Failed to load conversations.");
      }
    };

    fetchConversations();

    return () => {
      isMounted = false;
    };
  }, [applicationId]);

  const openConversation = async (convId) => {
    setIsDetailLoading(true);
    try {
      const res = await apiClient.get(`/admin/conversations/${convId}`);
      setSelectedConversation(res.data.conversation);
      setConversationMessages(res.data.messages || []);
    } catch (e) {
      console.error(e);
      toast.error("Failed to load conversation detail.");
    } finally {
      setIsDetailLoading(false);
    }
  };

  const closeConversation = async (convId) => {
    try {
      await apiClient.delete(`/admin/conversations/${convId}`);
      toast.success("Conversation closed.");
      setSelectedConversation(null);
      setConversationMessages([]);
      loadConversations();
    } catch (e) {
      console.error(e);
      toast.error("Failed to close conversation.");
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="view-conversations">
      <Card className="p-6">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <h3 className="text-card-title text-white flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-[#00D4FF]" aria-hidden="true" />
              <span>Conversation History</span>
            </h3>
            <p className="text-meta text-slate-500 mt-1">
              Browse and debug conversations for this application.
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={loadConversations}>
            Refresh
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Spinner className="h-6 w-6" />
          </div>
        ) : selectedConversation ? (
          <div>
            <button
              onClick={() => {
                setSelectedConversation(null);
                setConversationMessages([]);
              }}
              className="flex items-center gap-1.5 text-[11px] font-semibold text-[#00D4FF] hover:text-white transition mb-4 focus-visible:outline-none"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back to list</span>
            </button>

            <div className="flex items-start justify-between gap-4 mb-4">
              <div className="min-w-0">
                <h4 className="text-card-title text-white truncate">
                  {selectedConversation.title || "Untitled Conversation"}
                </h4>
                <p className="text-[10px] text-slate-500 font-mono mt-1 truncate">
                  ID: {selectedConversation.id} • {selectedConversation.conversation_identity}
                </p>
              </div>
              <Button
                variant="danger"
                size="sm"
                onClick={() => closeConversation(selectedConversation.id)}
              >
                Close Conversation
              </Button>
            </div>

            {isDetailLoading ? (
              <div className="flex items-center justify-center py-12">
                <Spinner className="h-6 w-6" />
              </div>
            ) : (
              <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
                {conversationMessages.length === 0 ? (
                  <p className="text-center text-slate-500 text-xs py-8">
                    No messages in this conversation.
                  </p>
                ) : (
                  conversationMessages.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
                    >
                      <div className="flex items-center gap-2 mb-1 text-[10px] text-slate-500 px-1">
                        <span>{msg.role === "user" ? "User" : "Assistant"}</span>
                        <span>•</span>
                        <span>
                          {new Date(msg.created_at || msg.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <div
                        className={`rounded-card px-4 py-2.5 text-[12px] leading-relaxed max-w-[85%] ${
                          msg.role === "user"
                            ? "bg-[#2563EB] text-white rounded-tr-none border border-white/[0.06]"
                            : "bg-white/[0.04] border border-white/[0.08] rounded-tl-none text-slate-200"
                        }`}
                      >
                        {msg.content}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        ) : conversations.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="No conversations found"
            message="Conversations started through the embedded widget will appear here."
          />
        ) : (
          <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="sticky top-0 z-10 bg-[#0D1526] border-b border-white/[0.08] text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                  <th className="py-3 px-4">Title</th>
                  <th className="py-3 px-4">Identity</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Created</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {conversations.map((conv) => (
                  <tr
                    key={conv.id}
                    className="border-b border-white/[0.05] hover:bg-white/[0.03] transition duration-200"
                  >
                    <td className="py-3 px-4 font-semibold text-slate-200">
                      {conv.title || "Untitled"}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-400">
                      {conv.conversation_identity}
                    </td>
                    <td className="py-3 px-4">
                      {conv.is_active ? (
                        <Badge variant="success">active</Badge>
                      ) : (
                        <Badge variant="neutral">closed</Badge>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-400 font-mono">
                      {new Date(conv.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openConversation(conv.id)}
                        data-testid={`view-conv-${conv.id}`}
                      >
                        View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
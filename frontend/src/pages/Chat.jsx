import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Copy, KeyRound, MessageSquare, Send, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "@/api/client";
import { Badge, Button, Card } from "@/components/ui/Primitives";
import { Input } from "@/components/ui/Form";

const API_KEY_STORAGE = "oceanrag_chat_api_key";

function stripCitationMarkers(text) {
  return String(text || "").replace(/\s*\[\d+\]/g, "");
}

export default function Chat() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [apiKey, setApiKey] = useState(
    () => localStorage.getItem(API_KEY_STORAGE) || ""
  );
  const [showKeyInput, setShowKeyInput] = useState(false);
  const [resolvedApplicationId, setResolvedApplicationId] = useState("");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    Object.keys(localStorage)
      .filter((key) => key.startsWith("oceanrag_chat_history:"))
      .forEach((key) => localStorage.removeItem(key));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const saveApiKey = (value) => {
    setApiKey(value);
    if (value) {
      localStorage.setItem(API_KEY_STORAGE, value);
      setResolvedApplicationId("");
      setMessages([]);
    } else {
      localStorage.removeItem(API_KEY_STORAGE);
      setResolvedApplicationId("");
      setMessages([]);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!question.trim() || isLoading) return;

    const userMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: question,
      timestamp: new Date().toISOString(),
    };
    setMessages((current) => [...current, userMessage]);
    const currentQuestion = question;
    setQuestion("");
    setIsLoading(true);

    try {
      const response = await apiClient.post(
        "/client/chat/preview/messages",
        {
          conversation_identity: "customer-preview",
          message: currentQuestion,
          conversation_title: "Customer Preview",
          conversation_messages: messages
            .filter((message) => message.role === "user" || message.role === "bot")
            .map((message) => ({
              role: message.role === "user" ? "user" : "assistant",
              content: message.content,
            }))
            .slice(-40),
        },
        { headers: { "X-API-Key": apiKey } }
      );
      const data = response.data;
      if (data.application_id) setResolvedApplicationId(data.application_id);

      setMessages((current) => [
        ...current,
        {
          id: `bot-${Date.now()}`,
          role: "bot",
          content: stripCitationMarkers(data.answer),
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (error) {
      console.error(error);
      const detail =
        error.response?.data?.error?.message
        || error.response?.data?.detail?.message
        || error.response?.data?.detail;
      toast.error(
        typeof detail === "string"
          ? detail
          : "Could not connect to the application. Check the API key."
      );
    } finally {
      setIsLoading(false);
    }
  };

  const clearHistory = () => {
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        role: "bot",
        content: "Hello. What would you like to know?",
        timestamp: new Date().toISOString(),
      },
    ]);
    toast.success("Customer preview cleared.");
  };

  const copyMessage = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Message copied.");
  };

  return (
    <main className="mx-auto flex h-[calc(100vh-96px)] w-full max-w-[1400px] flex-col overflow-hidden px-4 py-6 sm:px-6 lg:px-8">
      <Card
        className="mb-5 flex w-full flex-wrap items-center justify-between gap-4 p-4"
        data-testid="chat-system-status-banner"
      >
        <div className="flex items-center gap-3">
          <div className="rounded-[10px] border border-white/[0.08] bg-white/[0.04] p-2">
            <MessageSquare className="h-4 w-4 text-[#00D4FF]" aria-hidden="true" />
          </div>
          <div>
            <div className="text-card-title text-slate-100">Customer Preview</div>
            <div className="mt-1 text-[10px] text-slate-500">
              Uses the application resolved from the API key.
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant={resolvedApplicationId ? "success" : "warning"}>
            {resolvedApplicationId ? "application resolved" : "key required"}
          </Badge>
          <div className="flex items-center gap-1.5">
            <Button
              variant={apiKey ? "secondary" : "outline"}
              size="sm"
              onClick={() => setShowKeyInput((current) => !current)}
              data-testid="chat-api-key-toggle"
            >
              <KeyRound className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">
                {apiKey ? "API Key Set" : "Set API Key"}
              </span>
            </Button>
            {showKeyInput && (
              <Input
                type="password"
                value={apiKey}
                onChange={(event) => saveApiKey(event.target.value)}
                placeholder="akp_..."
                className="h-8 w-48 py-0 font-mono text-[10px]"
                data-testid="chat-api-key-input"
              />
            )}
          </div>
          <Button
            variant="danger"
            size="sm"
            onClick={clearHistory}
            data-testid="chat-clear"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Clear</span>
          </Button>
        </div>
      </Card>

      <div className="mb-4 max-h-[calc(100vh-320px)] flex-1 space-y-6 overflow-y-auto pr-1">
        <AnimatePresence initial={false}>
          {messages.map((message) => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className={`flex flex-col ${
                message.role === "user" ? "items-end" : "items-start"
              }`}
              data-testid={
                message.role === "user" ? "chat-message-user" : "chat-message-bot"
              }
            >
              <div className="mb-1.5 flex items-center gap-2 px-1 text-[11px] font-medium text-slate-400">
                <span>{message.role === "user" ? "You" : "Assistant"}</span>
                <span>•</span>
                <span>
                  {new Date(message.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              <div className="flex max-w-[85%] gap-3">
                {message.role === "bot" && (
                  <div className="hidden h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border border-white/[0.10] bg-gradient-to-br from-[#00D4FF] to-[#2563EB] shadow-md sm:flex">
                    <MessageSquare className="h-4 w-4 text-white" aria-hidden="true" />
                  </div>
                )}
                <div
                  className={`rounded-card px-5 py-3.5 text-[13px] leading-relaxed shadow-md ${
                    message.role === "user"
                      ? "rounded-tr-none border border-white/[0.10] bg-gradient-to-r from-[#2563EB] to-[#1E40AF] text-white"
                      : "surface-card rounded-tl-none text-slate-200"
                  }`}
                >
                  <div className="whitespace-pre-wrap">{message.content}</div>
                  {message.role === "bot" && (
                    <div className="mt-4 flex items-center border-t border-white/[0.06] pt-2.5 text-[11px] text-slate-400">
                      <button
                        onClick={() => copyMessage(message.content)}
                        className="flex items-center gap-1 transition hover:text-[#00D4FF]"
                        title="Copy content"
                      >
                        <Copy className="h-3.5 w-3.5" />
                        <span>Copy</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {isLoading && (
          <div className="flex flex-col items-start">
            <div className="mb-1.5 flex items-center gap-2 text-[11px] text-slate-400">
              <span>Assistant</span><span>•</span><span>Thinking...</span>
            </div>
            <div className="surface-card flex items-center gap-3 rounded-card px-5 py-4">
              <span className="text-[10px] text-slate-400">Preparing a customer response...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        className="surface-card flex w-full items-center gap-3 rounded-card p-2.5 shadow-raised"
        data-testid="chat-form"
      >
        <input
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask a customer question..."
          disabled={isLoading}
          className="flex-1 border-0 bg-transparent px-3 py-2 text-[13px] text-white outline-none placeholder-slate-500 disabled:opacity-60"
          data-testid="chat-input"
          required
        />
        <Button
          type="submit"
          disabled={isLoading || !question.trim()}
          className="h-10 px-5"
          data-testid="chat-submit"
        >
          <span>Send</span>
          <Send className="h-3.5 w-3.5" />
        </Button>
      </form>
    </main>
  );
}

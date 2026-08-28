import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { apiClient } from "@/api/client";
import { Send, Cpu, MessageSquare, Trash2, Copy, ThumbsUp, KeyRound } from "lucide-react";
import { toast } from "sonner";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const API_KEY_STORAGE = "oceanrag_chat_api_key";

// Strip bracketed citation markers like [1], [4], [10] that the LLM
// sometimes appends to answers - end users don't need them.
function stripCitationMarkers(text) {
  return String(text || "").replace(/\s*\[\d+\]/g, "");
}

export default function Chat() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [configInfo, setConfigInfo] = useState(null);
  const [topK, setTopK] = useState(4);
  const [conversationId, setConversationId] = useState(null);
  const [apiKey, setApiKey] = useState(() => localStorage.getItem(API_KEY_STORAGE) || "");
  const [showKeyInput, setShowKeyInput] = useState(false);
  const messagesEndRef = useRef(null);

  // Load chat history from localStorage on mount
  useEffect(() => {
    let isMounted = true;

    const loadHistory = () => {
      const saved = localStorage.getItem("oceanrag_chat_history");
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (isMounted) {
            setMessages(parsed.messages || []);
            setConversationId(parsed.conversationId || null);
          }
        } catch (e) {
          console.error("Error loading chat history", e);
        }
      } else if (isMounted) {
        // System greeting
        setMessages([
          {
            id: "welcome",
            role: "bot",
            content: "Welcome to **RENAI Chatbot**! I am your premium AI assistant powered by the local RAG engine. Upload files in the **Admin Console** to build my knowledge base, or ask me any general question right away.",
            timestamp: new Date().toISOString(),
            sources: [],
          }
        ]);
      }
    };

    loadHistory();

    return () => {
      isMounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Save messages to localStorage
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem("oceanrag_chat_history", JSON.stringify({ messages, conversationId }));
    } else {
      localStorage.removeItem("oceanrag_chat_history");
    }
  }, [messages, conversationId]);

  // Fetch System Details
  useEffect(() => {
    const fetchSystemDetails = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/api/system/config`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const configRes = await response.json();
        setConfigInfo(configRes);
      } catch (error) {
        console.warn("Could not fetch system info, falling back to backend health defaults.", error);
        setConfigInfo({
          status: "degraded",
          ollama_chat_model: "llama3",
          ollama_embed_model: "nomic-embed-text",
          app_name: "AI Knowledge Platform Backend",
        });
      }
    };
    fetchSystemDetails();
  }, []);

  // Auto Scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;

    const userMsg = {
      id: `user-${Date.now()}`,
      role: "user",
      content: question,
      timestamp: new Date().toISOString()
    };

    setMessages((prev) => [...prev, userMsg]);
    const currentQuestion = question;
    setQuestion("");
    setIsLoading(true);

    try {
      const response = await apiClient.post("/client/chat/messages", {
        conversation_identity: "web-user-" + (conversationId || Date.now()),
        message: currentQuestion,
        conversation_id: conversationId,
        conversation_title: "Web Chat Session",
      }, {
        headers: {
          "X-API-Key": apiKey,
        },
      });

      const data = response.data;

      // Store conversation ID for subsequent messages
      if (data.conversation_id && !conversationId) {
        setConversationId(data.conversation_id);
      }

      const botMsg = {
        id: `bot-${Date.now()}`,
        role: "bot",
        // Citations and bracketed [n] markers are intentionally hidden
        // from end users - answers render as clean prose.
        content: stripCitationMarkers(data.answer),
        timestamp: new Date().toISOString(),
        sources: [],
        conversation_id: data.conversation_id,
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (error) {
      console.error(error);
      toast.error("Failed to fetch response from RAG engine.");

      const errorMsg = {
        id: `bot-err-${Date.now()}`,
        role: "bot",
        content: "⚠️ **System Communication Error**: Failed to connect to the FastAPI RAG backend. Please verify your backend server is active and running correctly.",
        timestamp: new Date().toISOString(),
        sources: [],
        is_error: true
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearHistory = () => {
    setConversationId(null);
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        role: "bot",
        content: "Chat history cleared. I'm ready for your questions!",
        timestamp: new Date().toISOString(),
        sources: []
      }
    ]);
    toast.success("Conversation history cleared.");
  };

  const handleCopyMessage = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Message copied to clipboard.");
  };

  return (
    <main className="flex-1 w-full flex flex-col max-w-5xl mx-auto px-4 md:px-8 py-6 h-[calc(100vh-80px)] overflow-hidden">
      {/* Top Banner Context Widget */}
      <div
        className="w-full glassmorphism rounded-2xl p-4 mb-6 flex flex-wrap items-center justify-between gap-4 text-xs shadow-lg"
        data-testid="chat-system-status-banner"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-white/5 rounded-lg border border-white/10">
            <Cpu className="h-4 w-4 text-[#00D4FF]" />
          </div>
          <div>
            <div className="font-semibold text-slate-200">RAG Engine Configuration</div>
            <div className="text-slate-400 font-mono text-[10px] mt-0.5">
              {configInfo ? `LLM: ${configInfo.ollama_chat_model || "llama3"} • Embed: ${configInfo.ollama_embed_model || "nomic-embed"}` : "Loading system config..."}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* API Key input */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setShowKeyInput(!showKeyInput)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition ${
                apiKey
                  ? "border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                  : "border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
              }`}
              title={apiKey ? "API key configured" : "Set API key"}
              data-testid="chat-api-key-toggle"
            >
              <KeyRound className="h-3.5 w-3.5" />
              <span className="hidden sm:inline font-medium">{apiKey ? "Key Set" : "Set API Key"}</span>
            </button>
            {showKeyInput && (
              <input
                type="text"
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  localStorage.setItem(API_KEY_STORAGE, e.target.value);
                }}
                placeholder="akp_..."
                className="w-40 bg-slate-900 border border-white/10 rounded-md py-1 px-2 text-white font-mono text-[10px] focus:ring-1 focus:ring-[#00D4FF] focus:outline-none"
                data-testid="chat-api-key-input"
              />
            )}
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-slate-400">Search top_k chunks:</span>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="bg-slate-900 border border-white/10 rounded-md py-1 px-2 text-white font-medium text-xs focus:ring-1 focus:ring-[#00D4FF] focus:outline-none"
              data-testid="select-top-k"
            >
              <option value={2}>2</option>
              <option value={4}>4</option>
              <option value={6}>6</option>
              <option value={8}>8</option>
            </select>
          </div>

          <button
            onClick={handleClearHistory}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 hover:text-red-300 transition duration-300 focus:outline-none focus:ring-2 focus:ring-red-500/50"
            data-testid="chat-clear"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span className="font-medium hidden sm:inline">Clear Chat</span>
          </button>
        </div>
      </div>

      {/* Messages List Area */}
      <div className="flex-1 w-full overflow-y-auto pr-1 space-y-6 mb-4 max-h-[calc(100vh-280px)]">
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.3 }}
              className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
              data-testid={msg.role === "user" ? "chat-message-user" : "chat-message-bot"}
            >
              <div className="flex items-center gap-2 mb-1.5 text-xs text-slate-400 font-medium px-1">
                <span>{msg.role === "user" ? "You" : "Assistant"}</span>
                <span className="text-[10px] text-slate-500">•</span>
                <span>{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              </div>

              <div className="flex gap-3 max-w-[85%]">
                {msg.role === "bot" && (
                  <div className="hidden sm:flex h-8 w-8 rounded-full bg-gradient-to-br from-[#00D4FF] to-[#2563EB] items-center justify-center border border-white/10 shadow-md flex-shrink-0">
                    <MessageSquare className="h-4 w-4 text-white" />
                  </div>
                )}

                <div
                  className={`rounded-2xl px-5 py-3.5 shadow-md leading-relaxed text-sm ${
                    msg.role === "user"
                      ? "bg-gradient-to-r from-[#2563EB] to-[#1E40AF] text-white rounded-tr-none border border-white/10"
                      : "glassmorphism rounded-tl-none border-white/10"
                  }`}
                >
                  {/* Dynamic Markdown simulation (simple bolding, lists, code highlight) */}
                  <div className="whitespace-pre-wrap space-y-2">
                    {msg.content.split("\n").map((line, idx) => {
                      // Process bold text
                      let formatted = line;
                      const boldRegex = /\*\*(.*?)\*\*/g;
                      let matches = [...formatted.matchAll(boldRegex)];
                      if (matches.length > 0) {
                        return (
                          <p key={idx} className="leading-relaxed">
                            {formatted.split(/\*\*(.*?)\*\*/).map((part, index) => {
                              const isBold = index % 2 === 1;
                              return isBold ? <strong key={index} className="text-[#00D4FF] font-semibold">{part}</strong> : part;
                            })}
                          </p>
                        );
                      }

                      // Process list items
                      if (line.trim().startsWith("•") || line.trim().startsWith("-")) {
                        return (
                          <li key={idx} className="ml-4 list-disc text-slate-300">
                            {line.substring(2)}
                          </li>
                        );
                      }
                      if (/^\d+\.\s/.test(line.trim())) {
                        const num = line.match(/^\d+\./)[0];
                        return (
                          <li key={idx} className="ml-4 list-decimal text-slate-300">
                            <strong>{num}</strong> {line.replace(/^\d+\.\s/, "")}
                          </li>
                        );
                      }
                      return <p key={idx}>{line}</p>;
                    })}
                  </div>

                  {/* Actions (Copy / Like) */}
                  <div className="flex items-center gap-3 mt-4 pt-2.5 border-t border-white/5 text-[11px] text-slate-400">
                    <button
                      onClick={() => handleCopyMessage(msg.content)}
                      className="flex items-center gap-1 hover:text-[#00D4FF] transition"
                      title="Copy content"
                    >
                      <Copy className="h-3.5 w-3.5" />
                      <span>Copy</span>
                    </button>
                    {msg.role === "bot" && (
                      <button
                        onClick={() => toast.success("Feedback recorded! Thanks.")}
                        className="flex items-center gap-1 hover:text-[#00D4FF] transition"
                        title="Thumb up"
                      >
                        <ThumbsUp className="h-3.5 w-3.5" />
                        <span>Helpful</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Citations intentionally hidden from end users */}
            </motion.div>
          ))}
        </AnimatePresence>

        {isLoading && (
          <div className="flex flex-col items-start" data-testid="chat-loading-indicator">
            <div className="flex items-center gap-2 mb-1.5 text-xs text-slate-400 font-medium px-1">
              <span>Assistant</span>
              <span className="text-[10px] text-slate-500">•</span>
              <span className="italic">Thinking...</span>
            </div>
            <div className="flex gap-3 max-w-[80%]">
              <div className="hidden sm:flex h-8 w-8 rounded-full bg-slate-900 border border-white/10 items-center justify-center flex-shrink-0 animate-pulse">
                <Cpu className="h-4 w-4 text-[#00D4FF]" />
              </div>
              <div className="glassmorphism rounded-2xl rounded-tl-none px-5 py-4 border-white/10 flex items-center gap-3">
                <div className="flex space-x-1.5">
                  <div className="w-2 h-2 bg-[#00D4FF] rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></div>
                  <div className="w-2 h-2 bg-[#00D4FF] rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></div>
                  <div className="w-2 h-2 bg-[#00D4FF] rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></div>
                </div>
                <span className="text-xs text-slate-400 font-medium font-mono">Retrieving matching document vectors...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Sticky Bottom Input Area */}
      <form
        onSubmit={handleSubmit}
        className="w-full glassmorphism rounded-2xl p-2.5 flex items-center gap-3 border border-white/10 shadow-2xl relative"
        data-testid="chat-form"
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={isLoading ? "Generating RAG groundings..." : "Query your indexed knowledge base..."}
          disabled={isLoading}
          className="flex-1 bg-transparent border-0 outline-none text-white placeholder-slate-400 text-sm py-2 px-3 focus:ring-0 focus:outline-none"
          data-testid="chat-input"
          required
        />
        <button
          type="submit"
          disabled={isLoading || !question.trim()}
          className={`h-10 px-5 rounded-xl flex items-center justify-center gap-2 transition duration-300 font-medium text-xs tracking-wider ${
            isLoading || !question.trim()
              ? "bg-white/5 border border-white/5 text-slate-400 cursor-not-allowed"
              : "bg-[#00D4FF] text-[#040914] font-semibold hover:bg-white hover:text-[#040914] shadow-[0_0_15px_rgba(0,212,255,0.3)] hover:scale-105 active:scale-95 cursor-pointer"
          }`}
          data-testid="chat-submit"
        >
          <span>Send</span>
          <Send className="h-3.5 w-3.5" />
        </button>
      </form>
    </main>
  );
}
import { useState, useEffect, useCallback } from "react";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Copy,
  MessageSquare,
  Search,
} from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "@/api/client";
import DateRangePicker from "@/components/DateRangePicker";
import { Badge, Button, Card, Spinner } from "@/components/ui/Primitives";
import { EmptyState } from "@/components/ui/Stats";

function buildConversationFilters(dateFrom, dateTo) {
  const params = {};
  if (dateFrom) {
    params.activity_from = new Date(`${dateFrom}T00:00:00`).toISOString();
  }
  if (dateTo) {
    const exclusiveEnd = new Date(`${dateTo}T00:00:00`);
    exclusiveEnd.setDate(exclusiveEnd.getDate() + 1);
    params.activity_to = exclusiveEnd.toISOString();
  }
  return params;
}

function shortenedIdentity(identity) {
  if (!identity || identity.length <= 22) return identity;
  return `${identity.slice(0, 10)}...${identity.slice(-8)}`;
}

function formatDateTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function withConversationStats(conversation, messages) {
  return {
    ...conversation,
    message_count: messages.length,
    last_activity_at:
      messages[messages.length - 1]?.created_at || conversation.created_at,
  };
}

export default function ConversationsTab({
  applicationId,
  initialConversationId,
  onConversationClosed,
}) {
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [conversationMessages, setConversationMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("activity");
  const [sortOrder, setSortOrder] = useState("desc");

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const loadConversations = useCallback(async () => {
    setIsLoading(true);
    setListError("");
    try {
      const { data } = await apiClient.get(
        `/admin/conversations/application/${applicationId}`,
        {
          params: {
            ...buildConversationFilters(dateFrom, dateTo),
            status: statusFilter || undefined,
            search: search || undefined,
            sort_by: sortBy,
            sort_order: sortOrder,
            limit: pageSize,
            offset: page * pageSize,
          },
        }
      );
      setConversations(data.items || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error(error);
      setListError("Failed to load conversations. Try refreshing the list.");
    } finally {
      setIsLoading(false);
    }
  }, [
    applicationId,
    dateFrom,
    dateTo,
    page,
    pageSize,
    search,
    sortBy,
    sortOrder,
    statusFilter,
  ]);

  useEffect(() => {
    const timer = window.setTimeout(loadConversations, 0);
    return () => window.clearTimeout(timer);
  }, [loadConversations]);

  const openConversation = useCallback(async (conversation) => {
    setIsDetailLoading(true);
    setDetailError("");
    setSelectedConversation(conversation);
    try {
      const { data } = await apiClient.get(
        `/admin/conversations/${conversation.id}`
      );
      const messages = data.messages || [];
      setSelectedConversation(withConversationStats(data.conversation, messages));
      setConversationMessages(messages);
    } catch (error) {
      console.error(error);
      setDetailError("Failed to load conversation detail.");
    } finally {
      setIsDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!initialConversationId) return undefined;
    let cancelled = false;
    const fetchConversation = async () => {
      setIsDetailLoading(true);
      setDetailError("");
      try {
        const { data } = await apiClient.get(
          `/admin/conversations/${initialConversationId}`
        );
        if (cancelled) return;
        const messages = data.messages || [];
        setSelectedConversation(withConversationStats(data.conversation, messages));
        setConversationMessages(messages);
      } catch (error) {
        console.error(error);
        if (!cancelled) setDetailError("Failed to load conversation detail.");
      } finally {
        if (!cancelled) setIsDetailLoading(false);
      }
    };
    fetchConversation();
    return () => {
      cancelled = true;
    };
  }, [initialConversationId]);

  const closeConversation = async (conversation) => {
    try {
      await apiClient.delete(`/admin/conversations/${conversation.id}`);
      if (selectedConversation?.id === conversation.id) {
        onConversationClosed?.(selectedConversation);
      }
      toast.success("Conversation closed. Its history remains until retention cleanup.");
      setSelectedConversation(null);
      setConversationMessages([]);
      await loadConversations();
    } catch (error) {
      console.error(error);
      toast.error("Failed to close conversation.");
    }
  };

  const clearFilters = () => {
    setStatusFilter("");
    setDateFrom("");
    setDateTo("");
    setSearchInput("");
    setSearch("");
    setSortBy("activity");
    setSortOrder("desc");
    setPage(0);
  };

  const copyText = async (value, successMessage) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(successMessage);
    } catch (error) {
      console.error(error);
      toast.error("Could not copy visitor identity.");
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const firstItem = total === 0 ? 0 : page * pageSize + 1;
  const lastItem = Math.min((page + 1) * pageSize, total);

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="view-conversations">
      <Card className="p-6">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-card-title flex items-center gap-2 text-white">
              <MessageSquare className="h-4 w-4 text-[#00D4FF]" aria-hidden="true" />
              <span>Conversation History</span>
            </h3>
            <p className="text-meta mt-1 text-slate-500">
              Browse and debug conversations for this application.
            </p>
          </div>
          {!selectedConversation && (
            <Button
              variant="secondary"
              size="sm"
              onClick={loadConversations}
              disabled={isLoading}
            >
              Refresh
            </Button>
          )}
        </div>

        {selectedConversation ? (
          <div>
            <button
              onClick={() => {
                setSelectedConversation(null);
                setConversationMessages([]);
                setDetailError("");
              }}
              className="mb-4 flex items-center gap-1.5 text-[11px] font-semibold text-[#00D4FF] transition hover:text-white focus-visible:outline-none"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back to list</span>
            </button>

            <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <h4 className="text-card-title truncate text-white">
                  {selectedConversation.title || "Untitled Conversation"}
                </h4>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-[10px] text-slate-500">
                  <span>
                    Visitor:{" "}
                    <span className="font-mono text-slate-300">
                      {shortenedIdentity(selectedConversation.conversation_identity)}
                    </span>
                    <button
                      type="button"
                      onClick={() => copyText(
                        selectedConversation.conversation_identity,
                        "Visitor identity copied."
                      )}
                      className="ml-1 rounded p-1 text-slate-500 hover:bg-white/[0.06] hover:text-[#00D4FF]"
                      title="Copy visitor identity"
                      aria-label="Copy visitor identity"
                    >
                      <Copy className="h-3 w-3" />
                    </button>
                  </span>
                  <span>Created: {formatDateTime(selectedConversation.created_at)}</span>
                  <span>
                    Last activity: {formatDateTime(selectedConversation.last_activity_at)}
                  </span>
                  <span>{selectedConversation.message_count ?? conversationMessages.length} messages</span>
                  <Badge variant={selectedConversation.is_active ? "success" : "neutral"}>
                    {selectedConversation.is_active ? "active" : "closed"}
                  </Badge>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className="truncate font-mono text-[10px] text-slate-600">
                    ID: {selectedConversation.id}
                  </span>
                  <button
                    type="button"
                    onClick={() => copyText(
                      selectedConversation.id,
                      "Conversation ID copied."
                    )}
                    className="rounded p-1 text-slate-500 hover:bg-white/[0.06] hover:text-[#00D4FF]"
                    title="Copy conversation ID"
                    aria-label="Copy conversation ID"
                  >
                    <Copy className="h-3 w-3" />
                  </button>
                </div>
              </div>
              {selectedConversation.is_active && (
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => closeConversation(selectedConversation)}
                >
                  Close Conversation
                </Button>
              )}
            </div>

            {isDetailLoading ? (
              <div className="flex items-center justify-center py-12">
                <Spinner className="h-6 w-6" />
              </div>
            ) : detailError ? (
              <div role="alert" className="rounded-control border border-red-500/20 bg-red-500/[0.06] p-4 text-xs text-red-300">
                {detailError}
              </div>
            ) : (
              <div className="max-h-[460px] space-y-3 overflow-y-auto pr-2">
                {conversationMessages.length === 0 ? (
                  <p className="py-8 text-center text-xs text-slate-500">
                    No messages in this conversation.
                  </p>
                ) : (
                  conversationMessages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex flex-col ${message.role === "user" ? "items-end" : "items-start"}`}
                    >
                      <div className="mb-1 flex items-center gap-2 px-1 text-[10px] text-slate-500">
                        <span>{message.role === "user" ? "User" : "Assistant"}</span>
                        <span>•</span>
                        <span>{formatDateTime(message.created_at)}</span>
                      </div>
                      <div
                        className={`max-w-[85%] whitespace-pre-wrap rounded-card px-4 py-2.5 text-[12px] leading-relaxed ${
                          message.role === "user"
                            ? "rounded-tr-none border border-white/[0.06] bg-[#2563EB] text-white"
                            : "rounded-tl-none border border-white/[0.08] bg-white/[0.04] text-slate-200"
                        }`}
                      >
                        {message.content}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="mb-5 grid gap-3 rounded-card border border-white/[0.07] bg-white/[0.02] p-3 xl:grid-cols-[minmax(190px,1fr)_auto_repeat(3,minmax(150px,auto))]">
              <label className="relative">
                <span className="sr-only">Search title or visitor identity</span>
                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
                <input
                  type="search"
                  value={searchInput}
                  onChange={(event) => {
                    setSearchInput(event.target.value);
                    setPage(0);
                  }}
                  placeholder="Search title or visitor ID"
                  className="h-9 w-full rounded-control border border-white/[0.10] bg-[#0B1221] pl-9 pr-3 text-xs text-slate-200 outline-none focus:border-[#00D4FF]"
                  data-testid="conversation-search"
                />
              </label>

              <DateRangePicker
                dateFrom={dateFrom}
                dateTo={dateTo}
                filterLabel="conversation activity date"
                helperText="Filter by activity date"
                onChange={(from, to) => {
                  setDateFrom(from);
                  setDateTo(to);
                  setPage(0);
                }}
              />

              <label className="flex items-center gap-2 text-[10px] text-slate-500">
                <span>Status</span>
                <select
                  value={statusFilter}
                  onChange={(event) => {
                    setStatusFilter(event.target.value);
                    setPage(0);
                  }}
                  className="h-9 min-w-[105px] rounded-control border border-white/[0.10] bg-[#0B1221] px-2 text-xs text-slate-200"
                  aria-label="Filter by conversation status"
                >
                  <option value="">All</option>
                  <option value="active">Active</option>
                  <option value="closed">Closed</option>
                </select>
              </label>

              <label className="flex items-center gap-2 text-[10px] text-slate-500">
                <span>Sort by</span>
                <select
                  value={sortBy}
                  onChange={(event) => setSortBy(event.target.value)}
                  className="h-9 min-w-[135px] rounded-control border border-white/[0.10] bg-[#0B1221] px-2 text-xs text-slate-200"
                  aria-label="Sort conversations by"
                >
                  <option value="activity">Last activity</option>
                  <option value="created">Created date</option>
                </select>
              </label>

              <label className="flex items-center gap-2 text-[10px] text-slate-500">
                <span>Order</span>
                <select
                  value={sortOrder}
                  onChange={(event) => setSortOrder(event.target.value)}
                  className="h-9 min-w-[110px] rounded-control border border-white/[0.10] bg-[#0B1221] px-2 text-xs text-slate-200"
                  aria-label="Sort order"
                >
                  <option value="desc">Newest first</option>
                  <option value="asc">Oldest first</option>
                </select>
              </label>

              <div className="flex items-center xl:col-span-full xl:justify-end">
                <Button variant="ghost" size="sm" onClick={clearFilters}>
                  Clear filters
                </Button>
              </div>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Spinner className="h-6 w-6" />
              </div>
            ) : listError ? (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-red-500/20 bg-red-500/[0.06] p-4 text-xs text-red-300" role="alert">
                <span>{listError}</span>
                <Button variant="outline" size="sm" onClick={loadConversations}>
                  Retry
                </Button>
              </div>
            ) : conversations.length === 0 ? (
              <EmptyState
                icon={MessageSquare}
                title={total === 0 && (search || statusFilter || dateFrom || dateTo)
                  ? "No conversations match these filters"
                  : "No conversations found"}
                message={total === 0 && (search || statusFilter || dateFrom || dateTo)
                  ? "Try changing the search, date range, or status filter."
                  : "Conversations started through the embedded widget will appear here."}
              />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead>
                      <tr className="sticky top-0 z-10 border-b border-white/[0.08] bg-[#0D1526] text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                        <th className="py-3 pl-4 pr-3">Title</th>
                        <th className="px-3 py-3">Visitor identity</th>
                        <th className="px-3 py-3">Status</th>
                        <th className="px-3 py-3">Messages</th>
                        <th className="px-3 py-3">Created</th>
                        <th className="py-3 pl-3 pr-4">Last activity</th>
                        <th className="py-3 pl-3 pr-4 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {conversations.map((item) => {
                        const conversation = item;
                        return (
                          <tr
                            key={conversation.id}
                            className="border-b border-white/[0.05] transition duration-200 hover:bg-white/[0.03]"
                          >
                            <td className="max-w-[220px] truncate py-3 pl-4 pr-3 font-semibold text-slate-200" title={conversation.title || "Untitled"}>
                              {conversation.title || "Untitled"}
                            </td>
                            <td className="whitespace-nowrap px-3 py-3 font-mono text-slate-400">
                              <span title={conversation.conversation_identity}>
                                {shortenedIdentity(conversation.conversation_identity)}
                              </span>
                              <button
                                type="button"
                                onClick={() => copyText(
                                  conversation.conversation_identity,
                                  "Visitor identity copied."
                                )}
                                className="ml-1.5 rounded p-1 text-slate-500 hover:text-[#00D4FF]"
                                title="Copy visitor identity"
                                aria-label="Copy visitor identity"
                              >
                                <Copy className="h-3 w-3" />
                              </button>
                            </td>
                            <td className="px-3 py-3">
                              <Badge variant={conversation.is_active ? "success" : "neutral"}>
                                {conversation.is_active ? "active" : "closed"}
                              </Badge>
                            </td>
                            <td className="px-3 py-3 text-slate-400">{conversation.message_count}</td>
                            <td className="whitespace-nowrap px-3 py-3 text-slate-400">
                              {formatDateTime(conversation.created_at)}
                            </td>
                            <td className="whitespace-nowrap px-3 py-3 text-slate-400">
                              {formatDateTime(conversation.last_activity_at)}
                            </td>
                            <td className="whitespace-nowrap py-3 pl-3 pr-4 text-right">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => openConversation(conversation)}
                                data-testid={`view-conv-${conversation.id}`}
                              >
                                View
                              </Button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] pt-4">
                  <div className="flex items-center gap-3 text-[10px] text-slate-500">
                    <span>Showing {firstItem}–{lastItem} of {total}</span>
                    <label className="flex items-center gap-2">
                      <span>Per page</span>
                      <select
                        value={pageSize}
                        onChange={(event) => {
                          setPageSize(Number(event.target.value));
                          setPage(0);
                        }}
                        className="h-8 rounded-control border border-white/[0.10] bg-[#0B1221] px-2 text-xs text-slate-200"
                        aria-label="Conversations per page"
                      >
                        {[25, 50, 100].map((size) => (
                          <option key={size} value={size}>{size}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page === 0 || isLoading}
                      onClick={() => setPage((current) => Math.max(0, current - 1))}
                      aria-label="Previous page"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                      Previous
                    </Button>
                    <span className="min-w-[72px] text-center text-[10px] text-slate-500">
                      Page {page + 1} of {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page + 1 >= totalPages || isLoading}
                      onClick={() => setPage((current) => current + 1)}
                      aria-label="Next page"
                    >
                      Next
                      <ChevronRight className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </Card>
    </div>
  );
}

import { useEffect, useState } from "react";
import { MessageSquare, Star } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "@/api/client";
import { Button, Card, Spinner } from "@/components/ui/Primitives";

const PAGE_SIZE = 25;

function buildFilters(from, to, rating) {
  const params = {};
  if (from) params.created_from = new Date(`${from}T00:00:00`).toISOString();
  if (to) {
    const exclusiveEnd = new Date(`${to}T00:00:00`);
    exclusiveEnd.setDate(exclusiveEnd.getDate() + 1);
    params.created_to = exclusiveEnd.toISOString();
  }
  if (rating) params.rating = Number(rating);
  return params;
}

function MetricCard({ label, value, detail }) {
  return (
    <Card className="p-4">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
      {detail && <p className="mt-1 text-[10px] text-slate-500">{detail}</p>}
    </Card>
  );
}

export default function FeedbackTab({ applicationId, onViewConversation }) {
  const [analytics, setAnalytics] = useState(null);
  const [entries, setEntries] = useState([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [ratingFilter, setRatingFilter] = useState("");
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const loadFeedback = async () => {
      setIsLoading(true);
      setLoadError(false);
      setAnalytics(null);
      setEntries([]);
      setHasMore(false);
      const filters = buildFilters(dateFrom, dateTo, ratingFilter);
      try {
        const [analyticsResponse, entriesResponse] = await Promise.all([
          apiClient.get(
            `/admin/feedback/application/${applicationId}/analytics`,
            { params: filters },
          ),
          apiClient.get(`/admin/feedback/application/${applicationId}`, {
            params: { ...filters, limit: PAGE_SIZE, offset: page * PAGE_SIZE },
          }),
        ]);
        if (cancelled) return;
        setAnalytics(analyticsResponse.data);
        setEntries(entriesResponse.data);
        setHasMore(
          entriesResponse.data.length === PAGE_SIZE
          && (page + 1) * PAGE_SIZE < analyticsResponse.data.response_count
        );
      } catch (error) {
        console.error(error);
        if (!cancelled) {
          setLoadError(true);
          toast.error("Failed to load assistant experience feedback.");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    loadFeedback();
    return () => {
      cancelled = true;
    };
  }, [applicationId, dateFrom, dateTo, page, ratingFilter]);

  const changeFilter = (setter) => (event) => {
    setPage(0);
    setter(event.target.value);
  };

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="view-feedback">
      <Card className="p-6">
        <div className="mb-5">
          <h3 className="flex items-center gap-2 text-card-title text-white">
            <Star className="h-4 w-4 text-amber-400" aria-hidden="true" />
            Assistant experience
          </h3>
          <p className="mt-1 max-w-3xl text-meta text-slate-500">
            Customer ratings of the assistant conversation experience. These ratings
            do not measure enquiry outcomes, business follow-up, or administrator
            response quality.
          </p>
        </div>

        <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-3">
          <label className="text-[11px] text-slate-400">
            From
            <input
              type="date"
              className="mt-1 w-full rounded-control border border-white/[0.1] bg-[#0b1221] p-2 text-white"
              value={dateFrom}
              onChange={changeFilter(setDateFrom)}
            />
          </label>
          <label className="text-[11px] text-slate-400">
            Through
            <input
              type="date"
              className="mt-1 w-full rounded-control border border-white/[0.1] bg-[#0b1221] p-2 text-white"
              value={dateTo}
              onChange={changeFilter(setDateTo)}
            />
          </label>
          <label className="text-[11px] text-slate-400">
            Star rating
            <select
              className="mt-1 w-full rounded-control border border-white/[0.1] bg-[#0b1221] p-2 text-white"
              value={ratingFilter}
              onChange={changeFilter(setRatingFilter)}
            >
              <option value="">All ratings</option>
              {[5, 4, 3, 2, 1].map((rating) => (
                <option key={rating} value={rating}>{rating} stars</option>
              ))}
            </select>
          </label>
        </div>

        {isLoading && !analytics ? (
          <div className="flex justify-center py-10"><Spinner className="h-6 w-6" /></div>
        ) : loadError && !analytics ? (
          <p role="alert" className="py-8 text-center text-sm text-red-400">
            Could not load assistant-experience analytics. Refresh the tab to try again.
          </p>
        ) : analytics ? (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Rating responses" value={analytics.response_count} />
              <MetricCard
                label="Average rating"
                value={`${Number(analytics.average_rating).toFixed(1)} / 5`}
                detail="Assistant experience"
              />
              <MetricCard label="5-star responses" value={analytics.five_star_responses} />
              <MetricCard
                label="Positive ratings"
                value={`${Number(analytics.positive_rating_percentage).toFixed(1)}%`}
                detail="Share rated 4 or 5 stars"
              />
            </div>

            <div className="mt-5 rounded-card border border-white/[0.06] p-4">
              <h4 className="mb-3 text-xs font-semibold text-slate-300">Rating distribution</h4>
              <div className="space-y-2">
                {analytics.distribution.map((item) => {
                  const percentage = analytics.response_count
                    ? (item.count / analytics.response_count) * 100
                    : 0;
                  return (
                    <div key={item.rating} className="flex items-center gap-3 text-xs">
                      <span className="w-12 text-amber-300">{item.rating} ★</span>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          className="h-full rounded-full bg-amber-400"
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                      <span className="w-16 text-right text-slate-400">
                        {item.count} ({percentage.toFixed(1)}%)
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        ) : null}
      </Card>

      <Card className="p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-card-title text-white">Rating responses</h3>
            <p className="mt-1 text-meta text-slate-500">
              Individual assistant-experience ratings for this application.
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-10"><Spinner className="h-6 w-6" /></div>
        ) : loadError && entries.length === 0 ? (
          <p role="alert" className="py-8 text-center text-sm text-red-400">
            Could not load rating responses. Refresh the tab to try again.
          </p>
        ) : entries.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">
            No assistant-experience ratings match these filters.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-white/[0.08] text-[10px] uppercase text-slate-400">
                  <th className="px-3 py-3">Rating</th>
                  <th className="px-3 py-3">Conversation</th>
                  <th className="px-3 py-3">Submitted</th>
                  <th className="px-3 py-3">Feedback</th>
                  <th className="px-3 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id} className="border-b border-white/[0.05] text-slate-300">
                    <td className="px-3 py-3 font-semibold text-amber-300">
                      {`${"★".repeat(entry.rating)}${"☆".repeat(5 - entry.rating)}`}
                      <span className="ml-1 text-slate-400">{entry.rating}/5</span>
                    </td>
                    <td className="px-3 py-3">
                      <div>{entry.conversation_title || "Untitled conversation"}</div>
                      <code className="text-[10px] text-slate-500">{entry.conversation_id}</code>
                    </td>
                    <td className="px-3 py-3 text-slate-400">
                      {new Date(entry.created_at).toLocaleString()}
                    </td>
                    <td className="max-w-[240px] px-3 py-3 text-slate-400">
                      {entry.feedback_text || "Not collected"}
                    </td>
                    <td className="px-3 py-3">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onViewConversation(entry.conversation_id)}
                      >
                        <MessageSquare className="mr-1 h-3.5 w-3.5" /> View conversation
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
          <span>Page {page + 1}</span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page === 0 || isLoading}
              onClick={() => setPage((current) => Math.max(0, current - 1))}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={!hasMore || isLoading}
              onClick={() => setPage((current) => current + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Download, RefreshCw, Users } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "@/api/client";
import DateRangePicker from "@/components/DateRangePicker";
import { Badge, Button, Card, Spinner } from "@/components/ui/Primitives";

const STATUSES = ["new", "contacted", "closed"];

function queryFilters(status, from, to) {
  const params = {};
  if (status) params.status = status;
  if (from) params.created_from = new Date(`${from}T00:00:00`).toISOString();
  if (to) {
    const nextDay = new Date(`${to}T00:00:00`);
    nextDay.setDate(nextDay.getDate() + 1);
    params.created_to = nextDay.toISOString();
  }
  return params;
}

export default function LeadsTab({ applicationId }) {
  const [leads, setLeads] = useState([]);
  const [selectedLead, setSelectedLead] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  const loadLeads = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.get(
        `/admin/leads/application/${applicationId}`,
        {
          params: {
            ...queryFilters(statusFilter, dateFrom, dateTo),
            limit: 50,
            offset: page * 50,
          },
        },
      );
      setLeads(response.data);
      setHasMore(response.data.length === 50);
      setSelectedLead((current) =>
        current ? response.data.find((lead) => lead.id === current.id) || null : null
      );
    } catch (error) {
      console.error(error);
      toast.error("Failed to load enquiries.");
    } finally {
      setIsLoading(false);
    }
  }, [applicationId, dateFrom, dateTo, page, statusFilter]);

  useEffect(() => {
    let cancelled = false;
    const fetchLeads = async () => {
      setIsLoading(true);
      try {
        const response = await apiClient.get(
          `/admin/leads/application/${applicationId}`,
          {
            params: {
              ...queryFilters(statusFilter, dateFrom, dateTo),
              limit: 50,
              offset: page * 50,
            },
          },
        );
        if (cancelled) return;
        setLeads(response.data);
        setHasMore(response.data.length === 50);
        setSelectedLead((current) =>
          current ? response.data.find((lead) => lead.id === current.id) || null : null
        );
      } catch (error) {
        console.error(error);
        if (!cancelled) toast.error("Failed to load enquiries.");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    fetchLeads();
    return () => {
      cancelled = true;
    };
  }, [applicationId, dateFrom, dateTo, page, statusFilter]);

  const saveLead = async (event) => {
    event.preventDefault();
    if (!selectedLead) return;
    setIsSaving(true);
    try {
      const response = await apiClient.patch(
        `/admin/leads/application/${applicationId}/${selectedLead.id}`,
        {
          status: selectedLead.status,
          internal_note: selectedLead.internal_note || null,
        },
      );
      setSelectedLead(response.data);
      toast.success("Enquiry updated.");
      await loadLeads();
    } catch (error) {
      console.error(error);
      toast.error("Failed to update enquiry.");
    } finally {
      setIsSaving(false);
    }
  };

  const deleteLead = async () => {
    if (!selectedLead || !window.confirm("Permanently delete this enquiry?")) return;
    try {
      await apiClient.delete(
        `/admin/leads/application/${applicationId}/${selectedLead.id}`,
      );
      setSelectedLead(null);
      toast.success("Enquiry deleted.");
      await loadLeads();
    } catch (error) {
      console.error(error);
      toast.error("Failed to delete enquiry.");
    }
  };

  const exportLeads = async () => {
    try {
      const response = await apiClient.get(
        `/admin/leads/application/${applicationId}/export`,
        {
          params: queryFilters(statusFilter, dateFrom, dateTo),
          responseType: "blob",
        },
      );
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = `application-${applicationId}-leads.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error(error);
      toast.error("Failed to export enquiries.");
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="view-leads">
      <Card className="p-6">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className="text-card-title flex items-center gap-2 text-white">
              <Users className="h-4 w-4 text-[#00D4FF]" aria-hidden="true" />
              Enquiries
            </h3>
            <p className="mt-1 text-meta text-slate-500">
              Contact requests submitted for this application.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={exportLeads}>
              <Download className="mr-1 h-3.5 w-3.5" /> Export CSV
            </Button>
            <Button variant="secondary" size="sm" onClick={loadLeads}>
              <RefreshCw className="mr-1 h-3.5 w-3.5" /> Refresh
            </Button>
          </div>
        </div>

        <div className="mb-5 flex flex-wrap items-end gap-3">
          <label className="text-[11px] text-slate-400">
            Status
            <select
              className="mt-1 w-full rounded-control border border-white/[0.1] bg-[#0b1221] p-2 text-white"
              value={statusFilter}
              onChange={(event) => {
                setPage(0);
                setStatusFilter(event.target.value);
              }}
            >
              <option value="">All statuses</option>
              {STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
            </select>
          </label>
          <DateRangePicker
            dateFrom={dateFrom}
            dateTo={dateTo}
            filterLabel="enquiry submission date"
            helperText="Filter by submission date"
            onChange={(from, to) => {
              setPage(0);
              setDateFrom(from);
              setDateTo(to);
            }}
          />
        </div>

        {isLoading ? (
          <div className="flex justify-center py-10"><Spinner className="h-6 w-6" /></div>
        ) : leads.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">No enquiries found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-white/[0.08] text-[10px] uppercase text-slate-400">
                  <th className="px-3 py-3">Customer</th>
                  <th className="px-3 py-3">Contact</th>
                  <th className="px-3 py-3">Submitted</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Enquiry</th>
                  <th className="px-3 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.id} className="border-b border-white/[0.05] text-slate-300">
                    <td className="px-3 py-3">{lead.name}</td>
                    <td className="px-3 py-3">
                      <div>{lead.email || "—"}</div>
                      <div className="text-slate-500">{lead.phone || ""}</div>
                    </td>
                    <td className="px-3 py-3">{new Date(lead.created_at).toLocaleString()}</td>
                    <td className="px-3 py-3"><Badge variant={lead.status === "new" ? "warning" : "neutral"}>{lead.status}</Badge></td>
                    <td className="max-w-[240px] truncate px-3 py-3">{lead.message || "—"}</td>
                    <td className="px-3 py-3">
                      <Button variant="outline" size="sm" onClick={() => setSelectedLead(lead)}>
                        Review
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && (
          <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
            <span>Page {page + 1}</span>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((current) => Math.max(0, current - 1))}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={!hasMore}
                onClick={() => setPage((current) => current + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      {selectedLead && (
        <Card className="space-y-4 p-6" data-testid="lead-detail">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-card-title text-white">{selectedLead.name}</h3>
              <p className="mt-1 text-xs text-slate-400">
                {selectedLead.email || "No email"} · {selectedLead.phone || "No phone"}
              </p>
              <p className="mt-1 text-[10px] text-slate-500">
                Submitted {new Date(selectedLead.created_at).toLocaleString()}
              </p>
            </div>
            <Button variant="danger" size="sm" onClick={deleteLead}>Delete</Button>
          </div>
          <p className="whitespace-pre-wrap rounded-control bg-white/[0.03] p-3 text-sm text-slate-300">
            {selectedLead.message || "No enquiry message provided."}
          </p>
          <div className="rounded-control border border-white/[0.06] p-3 text-xs text-slate-400">
            <p>Consent recorded: {new Date(selectedLead.consented_at).toLocaleString()}</p>
            <p className="mt-1">{selectedLead.consent_text}</p>
          </div>
          {selectedLead.conversation_id && (
            <p className="text-[10px] text-slate-500">
              Conversation: <code>{selectedLead.conversation_id}</code>
            </p>
          )}
          <form onSubmit={saveLead} className="space-y-4">
            <label className="block text-xs text-slate-400">
              Status
              <select
                className="mt-1 w-full rounded-control border border-white/[0.1] bg-[#0b1221] p-2 text-white"
                value={selectedLead.status}
                onChange={(event) => setSelectedLead({ ...selectedLead, status: event.target.value })}
              >
                {STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
              </select>
            </label>
            <label className="block text-xs text-slate-400">
              Internal follow-up note
              <textarea
                className="mt-1 min-h-24 w-full rounded-control border border-white/[0.1] bg-[#0b1221] p-2 text-white"
                maxLength={5000}
                value={selectedLead.internal_note || ""}
                onChange={(event) => setSelectedLead({ ...selectedLead, internal_note: event.target.value })}
              />
            </label>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? "Saving..." : "Save changes"}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}

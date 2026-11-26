import { useCallback, useEffect, useState } from "react";
import { Download, MessageSquare, RefreshCw, Users } from "lucide-react";
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

function escapeHtml(value) {
  return String(value ?? "—")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatExportDate(value) {
  return value ? new Date(value).toLocaleString() : "—";
}

function leadsPrintDocument(leads, applicationId) {
  const rows = leads.map((lead) => `
    <tr>
      <td>${escapeHtml(formatExportDate(lead.created_at))}</td>
      <td>${escapeHtml(lead.name)}</td>
      <td>${escapeHtml(lead.email)}<br>${escapeHtml(lead.phone)}</td>
      <td>${escapeHtml(lead.status)}</td>
      <td>${escapeHtml(lead.message)}</td>
      <td>${escapeHtml(lead.internal_note)}</td>
    </tr>
  `).join("");

  return `<!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <title>Enquiry report - ${escapeHtml(applicationId)}</title>
        <style>
          @page { size: landscape; margin: 12mm; }
          body { color: #172033; font: 10px Arial, sans-serif; }
          h1 { margin: 0 0 6px; font-size: 20px; }
          .meta { margin: 0 0 16px; color: #526078; }
          table { width: 100%; border-collapse: collapse; table-layout: fixed; }
          th, td { padding: 7px; border: 1px solid #cbd2dc; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
          th { background: #e9eef5; font-size: 9px; text-transform: uppercase; }
          tr { break-inside: avoid; }
          th:nth-child(1) { width: 13%; }
          th:nth-child(2) { width: 13%; }
          th:nth-child(3) { width: 18%; }
          th:nth-child(4) { width: 9%; }
          th:nth-child(5) { width: 27%; }
          th:nth-child(6) { width: 20%; }
          @media screen {
            body { max-width: 1200px; margin: 32px auto; padding: 0 20px; }
          }
        </style>
      </head>
      <body>
        <h1>Enquiry report</h1>
        <p class="meta">Application: ${escapeHtml(applicationId)} · Records: ${leads.length} · Generated: ${escapeHtml(new Date().toLocaleString())}</p>
        <table>
          <thead>
            <tr>
              <th>Submitted</th>
              <th>Customer</th>
              <th>Contact</th>
              <th>Status</th>
              <th>Enquiry</th>
              <th>Internal follow-up note</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
        <script>window.addEventListener("load", () => window.print());</script>
      </body>
    </html>`;
}

export default function LeadsTab({ applicationId, onViewConversation }) {
  const [leads, setLeads] = useState([]);
  const [overview, setOverview] = useState(null);
  const [isOverviewLoading, setIsOverviewLoading] = useState(true);
  const [overviewError, setOverviewError] = useState("");
  const [overviewRefresh, setOverviewRefresh] = useState(0);
  const [selectedLead, setSelectedLead] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const loadOverview = async () => {
      setIsOverviewLoading(true);
      setOverviewError("");
      try {
        const response = await apiClient.get(
          `/admin/leads/application/${applicationId}/overview`,
          {
            params: queryFilters("", dateFrom, dateTo),
            signal: controller.signal,
          },
        );
        setOverview(response.data);
      } catch (error) {
        if (controller.signal.aborted) return;
        console.error(error);
        setOverviewError("Could not load the lead overview.");
      } finally {
        if (!controller.signal.aborted) setIsOverviewLoading(false);
      }
    };
    loadOverview();
    return () => controller.abort();
  }, [applicationId, dateFrom, dateTo, overviewRefresh]);

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
      setOverviewRefresh((current) => current + 1);
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
      setOverviewRefresh((current) => current + 1);
      await loadLeads();
    } catch (error) {
      console.error(error);
      toast.error("Failed to delete enquiry.");
    }
  };

  const exportLeads = async () => {
    const printWindow = window.open("", "_blank");
    if (!printWindow) {
      toast.error("Allow pop-ups to export the enquiry report.");
      return;
    }
    printWindow.document.write("<title>Preparing enquiry report</title><p>Preparing report…</p>");
    printWindow.document.close();
    try {
      const response = await apiClient.get(
        `/admin/leads/application/${applicationId}/export/data`,
        {
          params: queryFilters(statusFilter, dateFrom, dateTo),
        },
      );
      if (response.data.length === 0) {
        printWindow.close();
        toast.info("No enquiries match the selected filters.");
        return;
      }
      printWindow.document.open();
      printWindow.document.write(leadsPrintDocument(response.data, applicationId));
      printWindow.document.close();
      toast.info("In the print dialog, choose Save as PDF to download the report.");
    } catch (error) {
      console.error(error);
      printWindow.close();
      toast.error("Failed to export enquiries.");
    }
  };

  const refreshLeads = () => {
    setOverviewRefresh((current) => current + 1);
    loadLeads();
  };

  const viewLeadConversation = (lead) => {
    if (!lead.conversation_id) return;
    onViewConversation?.(lead.conversation_id);
  };

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="view-leads">
      <Card className="p-6">
        <div className="mb-4">
          <h3 className="text-card-title text-white">Operational overview</h3>
          <p className="mt-1 text-meta text-slate-500">
            Counts follow the selected submission-date range; the status filter below only narrows the enquiry list.
          </p>
        </div>
        {isOverviewLoading ? (
          <div className="flex justify-center py-5"><Spinner className="h-5 w-5" /></div>
        ) : overviewError ? (
          <p role="alert" className="py-4 text-sm text-red-400">{overviewError}</p>
        ) : overview ? (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
              {[
                ["Total enquiries", overview.total_count],
                ["New", overview.new_count],
                ["Contacted", overview.contacted_count],
                ["Closed", overview.closed_count],
                [
                  "Avg. time to mark contacted",
                  overview.average_first_contact_hours === null
                    ? "Not available"
                    : `${overview.average_first_contact_hours.toFixed(1)} hrs`,
                ],
              ].map(([label, value]) => (
                <div key={label} className="rounded-card border border-white/[0.06] bg-white/[0.02] p-4">
                  <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
                  <p className="mt-2 text-xl font-semibold text-white">{value}</p>
                  {label === "Avg. time to mark contacted" && (
                    <p className="mt-1 text-[10px] text-slate-500">
                      {overview.measured_first_contact_count} measured
                    </p>
                  )}
                </div>
              ))}
            </div>
            <p className="mt-3 text-[10px] text-slate-500">
              Timing measures submission to the first admin status change to “contacted”; only records tracked after this feature is enabled are included.
            </p>
          </>
        ) : null}
      </Card>

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
            <Button variant="secondary" size="sm" onClick={exportLeads} disabled={isLoading}>
              <Download className="mr-1 h-3.5 w-3.5" /> Export PDF
            </Button>
            <Button variant="secondary" size="sm" onClick={refreshLeads}>
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
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => setSelectedLead(lead)}>
                          Review
                        </Button>
                        {lead.conversation_id && (
                          <Button
                            variant="secondary"
                            size="sm"
                            aria-label={`View conversation for ${lead.name}`}
                            onClick={() => viewLeadConversation(lead)}
                          >
                            <MessageSquare className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
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
            <div className="flex gap-2">
              {selectedLead.conversation_id && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => viewLeadConversation(selectedLead)}
                >
                  <MessageSquare className="mr-1 h-3.5 w-3.5" /> View conversation
                </Button>
              )}
              <Button variant="danger" size="sm" onClick={deleteLead}>Delete</Button>
            </div>
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

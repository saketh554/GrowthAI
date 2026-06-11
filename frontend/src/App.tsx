import { FormEvent, useEffect, useMemo, useState } from "react";

type Employee = {
  id: string;
  name: string;
  grade: number;
  title: string;
  department: string;
  manager_id: string;
  home_base: string;
};

type Submission = {
  id: number;
  employee_id: string;
  trip_purpose: string;
  trip_dates: string;
  status: string;
  created_at: string;
};

type CitedClause = {
  doc_id: string;
  section: string;
  quoted_text: string;
};

type Verdict = {
  id: number;
  line_item_id: number;
  verdict: "compliant" | "flagged" | "rejected";
  reasoning: string;
  cited_clauses: CitedClause[];
  confidence: number;
  created_at: string;
};

type LineItem = {
  id: number;
  submission_id: number;
  receipt_filename: string;
  category: string | null;
  vendor: string | null;
  date: string | null;
  amount: number | null;
  currency: string | null;
  raw_extraction: Record<string, unknown> | null;
  verdicts: Verdict[];
};

type Override = {
  id: number;
  verdict_id: number;
  reviewer_comment: string;
  new_verdict: "compliant" | "flagged" | "rejected";
  created_at: string;
};

type SubmissionDetail = {
  submission: Submission;
  line_items: LineItem[];
  overrides: Override[];
};

type QAResponse = {
  answer: string;
  refused: boolean;
  refusal_reason: string | null;
  cited_clauses: CitedClause[];
};

type EmployeeCreatePayload = {
  id: string;
  name: string;
  grade: number;
  title: string;
  department: string;
  manager_id: string;
  home_base: string;
};

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const target = API_BASE ? `${API_BASE}${path}` : path;
  const response = await fetch(target, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status}: ${text}`);
  }
  return (await response.json()) as T;
}

function verdictClasses(verdict: "compliant" | "flagged" | "rejected"): string {
  if (verdict === "compliant") {
    return "border-emerald-300 bg-emerald-50";
  }
  if (verdict === "rejected") {
    return "border-rose-300 bg-rose-50";
  }
  return "border-amber-300 bg-amber-50";
}

function App() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string>("");
  const [tripPurpose, setTripPurpose] = useState("");
  const [tripDates, setTripDates] = useState("");
  const [newSubmissionId, setNewSubmissionId] = useState<number | null>(null);
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<number | null>(null);
  const [submissionDetail, setSubmissionDetail] = useState<SubmissionDetail | null>(null);
  const [uploadFiles, setUploadFiles] = useState<FileList | null>(null);
  const [overrideComment, setOverrideComment] = useState("");
  const [overrideVerdict, setOverrideVerdict] = useState<"compliant" | "flagged" | "rejected">("flagged");
  const [qaQuestion, setQaQuestion] = useState("");
  const [qaResponse, setQaResponse] = useState<QAResponse | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("Loading...");
  const [isBusy, setIsBusy] = useState(false);
  const [newEmployee, setNewEmployee] = useState<EmployeeCreatePayload>({
    id: "",
    name: "",
    grade: 5,
    title: "",
    department: "",
    manager_id: "",
    home_base: "",
  });

  const firstVerdictId = useMemo(() => {
    const verdicts = submissionDetail?.line_items?.[0]?.verdicts ?? [];
    return verdicts.length > 0 ? verdicts[verdicts.length - 1].id : null;
  }, [submissionDetail]);

  async function refreshEmployees() {
    const rows = await api<Employee[]>("/api/employees");
    setEmployees(rows);
    if (!selectedEmployeeId && rows.length > 0) {
      setSelectedEmployeeId(rows[0].id);
    }
  }

  async function refreshSubmissions() {
    const rows = await api<Submission[]>("/api/submissions");
    setSubmissions(rows);
  }

  async function refreshSubmissionDetail(submissionId: number) {
    const detail = await api<SubmissionDetail>(`/api/submissions/${submissionId}`);
    setSubmissionDetail(detail);
  }

  useEffect(() => {
    (async () => {
      try {
        await refreshEmployees();
        await refreshSubmissions();
        setStatusMessage("Ready.");
      } catch (error) {
        setStatusMessage(`Failed to load initial data: ${(error as Error).message}`);
      }
    })();
  }, []);

  async function handleCreateSubmission(event: FormEvent) {
    event.preventDefault();
    setIsBusy(true);
    try {
      const created = await api<Submission>("/api/submissions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          employee_id: selectedEmployeeId,
          trip_purpose: tripPurpose,
          trip_dates: tripDates,
        }),
      });
      setNewSubmissionId(created.id);
      setSelectedSubmissionId(created.id);
      await refreshSubmissions();
      await refreshSubmissionDetail(created.id);
      setStatusMessage(`Created submission #${created.id}`);
    } catch (error) {
      setStatusMessage(`Create submission failed: ${(error as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleUploadReceipts(event: FormEvent) {
    event.preventDefault();
    if (!selectedSubmissionId || !uploadFiles || uploadFiles.length === 0) {
      setStatusMessage("Choose submission and at least one receipt file.");
      return;
    }
    setIsBusy(true);
    try {
      const form = new FormData();
      for (const file of Array.from(uploadFiles)) {
        form.append("files", file);
      }
      await api<LineItem[]>(`/api/submissions/${selectedSubmissionId}/receipts`, {
        method: "POST",
        body: form,
      });
      await refreshSubmissions();
      await refreshSubmissionDetail(selectedSubmissionId);
      setStatusMessage(`Uploaded ${uploadFiles.length} file(s) to submission #${selectedSubmissionId}`);
    } catch (error) {
      setStatusMessage(`Upload failed: ${(error as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleLoadSubmission(submissionId: number) {
    setIsBusy(true);
    try {
      setSelectedSubmissionId(submissionId);
      await refreshSubmissionDetail(submissionId);
      setStatusMessage(`Loaded submission #${submissionId}`);
    } catch (error) {
      setStatusMessage(`Load submission failed: ${(error as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleCreateOverride(event: FormEvent) {
    event.preventDefault();
    if (!firstVerdictId) {
      setStatusMessage("No verdict available yet for override.");
      return;
    }
    setIsBusy(true);
    try {
      await api<Override>(`/api/verdicts/${firstVerdictId}/override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reviewer_comment: overrideComment,
          new_verdict: overrideVerdict,
        }),
      });
      if (selectedSubmissionId) {
        await refreshSubmissionDetail(selectedSubmissionId);
      }
      setStatusMessage(`Override added for verdict #${firstVerdictId}`);
      setOverrideComment("");
    } catch (error) {
      setStatusMessage(`Override failed: ${(error as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleAskQa(event: FormEvent) {
    event.preventDefault();
    if (!qaQuestion.trim()) {
      return;
    }
    setIsBusy(true);
    try {
      const response = await api<QAResponse>("/api/qa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: qaQuestion }),
      });
      setQaResponse(response);
      setStatusMessage(response.refused ? "Q&A returned a refusal." : "Q&A answered with citations.");
    } catch (error) {
      setStatusMessage(`Q&A failed: ${(error as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleCreateEmployee(event: FormEvent) {
    event.preventDefault();
    if (!newEmployee.id || !newEmployee.name || !newEmployee.title || !newEmployee.department || !newEmployee.manager_id || !newEmployee.home_base) {
      setStatusMessage("Fill all new employee fields before submitting.");
      return;
    }
    setIsBusy(true);
    try {
      const created = await api<Employee>("/api/employees", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newEmployee),
      });
      await refreshEmployees();
      setSelectedEmployeeId(created.id);
      setStatusMessage(`Created new employee ${created.name} (${created.id}).`);
      setNewEmployee({
        id: "",
        name: "",
        grade: 5,
        title: "",
        department: "",
        manager_id: "",
        home_base: "",
      });
    } catch (error) {
      setStatusMessage(`Create employee failed: ${(error as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleRejudgeLineItem(lineItemId: number) {
    setIsBusy(true);
    try {
      await api<LineItem>(`/api/line-items/${lineItemId}/rejudge`, {
        method: "POST",
      });
      if (selectedSubmissionId) {
        await refreshSubmissionDetail(selectedSubmissionId);
      }
      setStatusMessage(`Rejudged line item #${lineItemId}`);
    } catch (error) {
      setStatusMessage(`Rejudge failed: ${(error as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6">
        <header className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h1 className="text-2xl font-bold">Northwind Expense Pre-Review</h1>
          <p className="mt-1 text-sm text-slate-600">Part 7 reviewer UI: submission, upload, verdict review, overrides, history, and policy Q&A.</p>
          <p className="mt-2 text-sm font-medium text-indigo-700">{isBusy ? "Working..." : statusMessage}</p>
        </header>

        <section className="grid gap-4 lg:grid-cols-3">
          <form onSubmit={handleCreateSubmission} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">Create Submission</h2>
            <div className="space-y-3">
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Employee</span>
                <select
                  value={selectedEmployeeId}
                  onChange={(event) => setSelectedEmployeeId(event.target.value)}
                  className="w-full rounded border border-slate-300 px-3 py-2"
                >
                  {employees.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.name} ({employee.id})
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Trip Purpose</span>
                <input
                  value={tripPurpose}
                  onChange={(event) => setTripPurpose(event.target.value)}
                  placeholder="Quarterly client review trip"
                  className="w-full rounded border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Trip Dates</span>
                <input
                  value={tripDates}
                  onChange={(event) => setTripDates(event.target.value)}
                  placeholder="2025-06-10 to 2025-06-12"
                  className="w-full rounded border border-slate-300 px-3 py-2"
                />
              </label>
              <button
                type="submit"
                disabled={isBusy || !selectedEmployeeId || !tripPurpose || !tripDates}
                className="rounded bg-indigo-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:bg-slate-400"
              >
                Create Submission
              </button>
              {newSubmissionId && <p className="text-sm text-emerald-700">Latest created submission: #{newSubmissionId}</p>}
            </div>
          </form>

          <form onSubmit={handleUploadReceipts} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">Upload Receipts</h2>
            <div className="space-y-3">
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Submission ID</span>
                <input
                  type="number"
                  value={selectedSubmissionId ?? ""}
                  onChange={(event) => setSelectedSubmissionId(Number(event.target.value))}
                  className="w-full rounded border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Receipt Files (.pdf/.png/.jpg/.txt)</span>
                <input
                  type="file"
                  multiple
                  onChange={(event) => setUploadFiles(event.target.files)}
                  className="w-full rounded border border-slate-300 bg-white px-3 py-2"
                />
              </label>
              <button
                type="submit"
                disabled={isBusy || !selectedSubmissionId}
                className="rounded bg-indigo-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:bg-slate-400"
              >
                Upload and Review
              </button>
            </div>
          </form>

          <form onSubmit={handleCreateEmployee} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">Create New Employee</h2>
            <div className="space-y-2">
              <input
                value={newEmployee.id}
                onChange={(event) => setNewEmployee((prev) => ({ ...prev, id: event.target.value }))}
                placeholder="Employee ID (e.g. NW-09999)"
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                value={newEmployee.name}
                onChange={(event) => setNewEmployee((prev) => ({ ...prev, name: event.target.value }))}
                placeholder="Full name"
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                type="number"
                min={1}
                value={newEmployee.grade}
                onChange={(event) => setNewEmployee((prev) => ({ ...prev, grade: Number(event.target.value) }))}
                placeholder="Grade"
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                value={newEmployee.title}
                onChange={(event) => setNewEmployee((prev) => ({ ...prev, title: event.target.value }))}
                placeholder="Title"
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                value={newEmployee.department}
                onChange={(event) => setNewEmployee((prev) => ({ ...prev, department: event.target.value }))}
                placeholder="Department"
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                value={newEmployee.manager_id}
                onChange={(event) => setNewEmployee((prev) => ({ ...prev, manager_id: event.target.value }))}
                placeholder="Manager ID"
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                value={newEmployee.home_base}
                onChange={(event) => setNewEmployee((prev) => ({ ...prev, home_base: event.target.value }))}
                placeholder="Home base"
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
              <button
                type="submit"
                disabled={isBusy}
                className="rounded bg-indigo-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:bg-slate-400"
              >
                Add Employee
              </button>
            </div>
          </form>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">Submission History</h2>
            <div className="space-y-2">
              {submissions.map((submission) => (
                <button
                  key={submission.id}
                  onClick={() => handleLoadSubmission(submission.id)}
                  className="flex w-full items-center justify-between rounded border border-slate-200 px-3 py-2 text-left hover:bg-slate-50"
                >
                  <span>
                    #{submission.id} • {submission.employee_id} • {submission.status}
                  </span>
                  <span className="text-xs text-slate-500">{new Date(submission.created_at).toLocaleString()}</span>
                </button>
              ))}
              {submissions.length === 0 && <p className="text-sm text-slate-500">No submissions yet.</p>}
            </div>
          </div>

          <form onSubmit={handleAskQa} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">Policy Q&A</h2>
            <div className="space-y-3">
              <textarea
                value={qaQuestion}
                onChange={(event) => setQaQuestion(event.target.value)}
                rows={3}
                placeholder="Ask a policy question..."
                className="w-full rounded border border-slate-300 px-3 py-2"
              />
              <button
                type="submit"
                disabled={isBusy || !qaQuestion.trim()}
                className="rounded bg-indigo-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:bg-slate-400"
              >
                Ask Question
              </button>
              {qaResponse && (
                <div className={`rounded border p-3 text-sm ${qaResponse.refused ? "border-amber-300 bg-amber-50" : "border-emerald-300 bg-emerald-50"}`}>
                  <p className="font-medium">{qaResponse.refused ? "Declined" : "Answered"}</p>
                  <p className="mt-1">{qaResponse.answer}</p>
                  {qaResponse.refusal_reason && <p className="mt-1 text-xs text-slate-600">Reason: {qaResponse.refusal_reason}</p>}
                  {qaResponse.cited_clauses.length > 0 && (
                    <ul className="mt-2 list-disc pl-5 text-xs text-slate-700">
                      {qaResponse.cited_clauses.map((clause, index) => (
                        <li key={`${clause.doc_id}-${index}`}>
                          {clause.doc_id} {clause.section}: "{clause.quoted_text}"
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          </form>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">Submission Detail</h2>
          {!submissionDetail && <p className="text-sm text-slate-500">Select a submission from history to view details.</p>}
          {submissionDetail && (
            <div className="space-y-4">
              <div className="rounded border border-slate-200 p-3 text-sm">
                <p>
                  <span className="font-semibold">Submission:</span> #{submissionDetail.submission.id}
                </p>
                <p>
                  <span className="font-semibold">Employee:</span> {submissionDetail.submission.employee_id}
                </p>
                <p>
                  <span className="font-semibold">Trip:</span> {submissionDetail.submission.trip_purpose}
                </p>
                <p>
                  <span className="font-semibold">Dates:</span> {submissionDetail.submission.trip_dates}
                </p>
              </div>

              <div className="space-y-3">
                {submissionDetail.line_items.map((item) => {
                  const verdict = item.verdicts.length > 0 ? item.verdicts[item.verdicts.length - 1] : undefined;
                  return (
                    <div key={item.id} className={`rounded border p-3 ${verdict ? verdictClasses(verdict.verdict) : "border-slate-200 bg-slate-50"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <p className="font-semibold">{item.receipt_filename}</p>
                        <button
                          type="button"
                          onClick={() => handleRejudgeLineItem(item.id)}
                          disabled={isBusy}
                          className="rounded border border-indigo-300 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Rejudge
                        </button>
                      </div>
                      <p className="text-sm">
                        {item.vendor ?? "Unknown vendor"} • {item.category ?? "Uncategorized"} • {item.amount ?? "?"} {item.currency ?? ""}
                      </p>
                      {verdict && (
                        <>
                          <p className="mt-2 text-sm">
                            <span className="font-medium">Verdict:</span> {verdict.verdict} ({Math.round(verdict.confidence * 100)}%)
                          </p>
                          <p className="text-sm">{verdict.reasoning}</p>
                          {verdict.cited_clauses.length > 0 && (
                            <ul className="mt-2 list-disc pl-5 text-xs">
                              {verdict.cited_clauses.map((clause, index) => (
                                <li key={`${clause.doc_id}-${index}`}>
                                  {clause.doc_id} {clause.section}: "{clause.quoted_text}"
                                </li>
                              ))}
                            </ul>
                          )}
                        </>
                      )}
                    </div>
                  );
                })}
                {submissionDetail.line_items.length === 0 && <p className="text-sm text-slate-500">No line items yet.</p>}
              </div>

              <form onSubmit={handleCreateOverride} className="rounded border border-slate-200 p-3">
                <h3 className="font-semibold">Create Override (first verdict)</h3>
                <div className="mt-2 grid gap-2 md:grid-cols-2">
                  <select
                    value={overrideVerdict}
                    onChange={(event) => setOverrideVerdict(event.target.value as "compliant" | "flagged" | "rejected")}
                    className="rounded border border-slate-300 px-3 py-2"
                  >
                    <option value="compliant">compliant</option>
                    <option value="flagged">flagged</option>
                    <option value="rejected">rejected</option>
                  </select>
                  <input
                    value={overrideComment}
                    onChange={(event) => setOverrideComment(event.target.value)}
                    placeholder="Reviewer comment"
                    className="rounded border border-slate-300 px-3 py-2"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isBusy || !firstVerdictId || !overrideComment}
                  className="mt-2 rounded bg-indigo-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:bg-slate-400"
                >
                  Add Override
                </button>
                <div className="mt-2 space-y-1 text-xs text-slate-700">
                  {submissionDetail.overrides.map((item) => (
                    <p key={item.id}>
                      #{item.id} verdict #{item.verdict_id}: {item.new_verdict} — {item.reviewer_comment}
                    </p>
                  ))}
                  {submissionDetail.overrides.length === 0 && <p>No overrides yet.</p>}
                </div>
              </form>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default App;

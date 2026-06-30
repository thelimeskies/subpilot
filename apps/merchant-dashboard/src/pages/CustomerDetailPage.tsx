import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DataTable,
  Field,
  Modal,
  SelectInput,
  Sheet,
  StatCard,
  Tabs,
  TextInput,
  type BadgeTone,
  type DataTableColumn
} from "@subpilot/ui";
import {
  ArrowLeft,
  Ban,
  CreditCard,
  GitMerge,
  Mail,
  Pencil,
  Plus,
  StickyNote
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { createPortalSession } from "../api/billing";
import { isApiError } from "../api/client";
import { useData } from "../data/store";
import { useFeatureFlags } from "../features/FeatureFlagsContext";
import { usePermissions } from "../auth/AuthContext";
import {
  findInvoicesByCustomer,
  findPaymentsByCustomer,
  findSubscriptionsByCustomer,
  formatCurrency,
  formatRelative
} from "../data/selectors";
import type { CustomerStatus, Invoice, PaymentMethod, Subscription } from "../data/seed";

type TabKey = "profile" | "subscriptions" | "invoices" | "methods" | "activity" | "notes";

interface EditForm {
  name: string;
  email: string;
  phone: string;
  country: string;
  notes: string;
}

interface AddMethodState {
  brand: PaymentMethod["brand"];
  last4: string;
  expiry: string;
}

interface MergeState {
  searchQuery: string;
  targetId: string;
}

export function CustomerDetailPage() {
  const { customerId } = useParams<{ customerId: string }>();
  const navigate = useNavigate();
  const { isEnabled } = useFeatureFlags();
  const tokenizedCardsEnabled = isEnabled("tokenized_cards");
  const {
    customers,
    subscriptions,
    invoices,
    payments,
    plans,
    auditEvents,
    updateCustomer,
    blockCustomer,
    mergeCustomer,
    addCustomerPaymentMethod,
    setCustomerDefaultPaymentMethod,
    logAuditEvent
  } = useData();
  const { notify, confirm } = useFeedback();
  const { can } = usePermissions();
  const canEditCustomer = can("create_customer");
  const canBlockCustomer = can("create_customer");
  const canManagePaymentMethods = can("create_payment_method_session");
  const canSendPortalLink = can("create_payment_method_session");
  const canMergeCustomer = can("create_customer");
  const [tab, setTab] = useState<TabKey>("profile");
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [methodOpen, setMethodOpen] = useState<AddMethodState | null>(null);
  const [portalOpen, setPortalOpen] = useState(false);
  const [mergeState, setMergeState] = useState<MergeState | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteSheetOpen, setNoteSheetOpen] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [blocking, setBlocking] = useState(false);
  const [savingNote, setSavingNote] = useState(false);
  const [savingMethod, setSavingMethod] = useState(false);
  const [savingDefaultMethodId, setSavingDefaultMethodId] = useState<string | null>(null);
  const [portalBusy, setPortalBusy] = useState(false);

  const customer = customers.find((c) => c.id === customerId);

  const customerSubs = useMemo<Subscription[]>(
    () => (customer ? findSubscriptionsByCustomer(subscriptions, customer.id) : []),
    [customer, subscriptions]
  );
  const customerInvoices = useMemo<Invoice[]>(
    () => (customer ? findInvoicesByCustomer(invoices, customer.id) : []),
    [customer, invoices]
  );
  const customerPayments = useMemo(
    () => (customer ? findPaymentsByCustomer(payments, customer.id) : []),
    [customer, payments]
  );
  const customerActivity = useMemo(
    () => (customer ? auditEvents.filter((a) => a.target.includes(customer.email) || a.target.includes(customer.id) || a.target.includes(customer.name)) : []),
    [customer, auditEvents]
  );

  if (!customer) {
    return (
      <div className="mer-empty-state">
        <h2>Customer not found</h2>
        <p>We couldn&rsquo;t locate <code>{customerId}</code>.</p>
        <Link to="/customers" className="mer-card-link">
          <ArrowLeft size={14} aria-hidden="true" /> Back to customers
        </Link>
      </div>
    );
  }

  function openEdit() {
    if (!customer) return;
    setEditForm({
      name: customer.name,
      email: customer.email,
      phone: customer.phone,
      country: customer.country,
      notes: customer.notes
    });
    setEditOpen(true);
  }

  async function submitEdit() {
    if (!customer || !editForm) return;
    if (!editForm.name.trim() || !editForm.email.trim()) {
      notify({ tone: "warning", title: "Missing details", description: "Name and email are required." });
      return;
    }
    setSavingProfile(true);
    try {
      await updateCustomer(customer.id, {
        name: editForm.name.trim(),
        email: editForm.email.trim(),
        phone: editForm.phone.trim(),
        country: editForm.country,
        notes: editForm.notes.trim()
      });
      logAuditEvent({ actor: "You", action: "Updated customer profile", target: customer.email });
      notify({ tone: "success", title: "Profile updated", description: `${editForm.name}'s record was saved.` });
      setEditOpen(false);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not update profile",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSavingProfile(false);
    }
  }

  function openAddMethod() {
    setMethodOpen({
      brand: "Visa",
      last4: "",
      expiry: "12/29"
    });
  }

  async function submitAddMethod() {
    if (!customer || !methodOpen) return;
    if (!/^\d{4}$/.test(methodOpen.last4)) {
      notify({ tone: "warning", title: "Invalid card", description: "Last 4 digits must be exactly 4 numbers." });
      return;
    }
    setSavingMethod(true);
    try {
      await addCustomerPaymentMethod(customer.id, {
        brand: methodOpen.brand,
        last4: methodOpen.last4,
        expiry: methodOpen.expiry
      });
      logAuditEvent({ actor: "You", action: "Added payment method", target: `${customer.email} · ${methodOpen.brand} ···· ${methodOpen.last4}` });
      notify({ tone: "success", title: "Card added", description: `${methodOpen.brand} ···· ${methodOpen.last4} is now on file.` });
      setMethodOpen(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not add card",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSavingMethod(false);
    }
  }

  async function makeDefaultMethod(method: PaymentMethod) {
    if (!customer || method.isDefault || savingDefaultMethodId) return;
    setSavingDefaultMethodId(method.id);
    try {
      await setCustomerDefaultPaymentMethod(method.id);
      logAuditEvent({ actor: "You", action: "Updated default payment method", target: `${customer.email} · ${method.brand} ···· ${method.last4}` });
      notify({ tone: "success", title: "Default updated", description: `${method.brand} ···· ${method.last4} is now the default card.` });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not update default",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSavingDefaultMethodId(null);
    }
  }

  async function copyPortalLink() {
    if (!customer) return;
    setPortalBusy(true);
    try {
      const session = await createPortalSession(customer.id);
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        navigator.clipboard.writeText(session.url).catch(() => undefined);
      }
      logAuditEvent({ actor: "You", action: "Copied portal link", target: customer.email });
      notify({ tone: "info", title: "Portal link copied", description: session.url });
      setPortalOpen(false);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not create portal link",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setPortalBusy(false);
    }
  }

  async function emailPortalLink() {
    if (!customer) return;
    setPortalBusy(true);
    try {
      const session = await createPortalSession(customer.id, { sendEmail: true });
      logAuditEvent({ actor: "You", action: "Emailed portal link", target: customer.email });
      notify({
        tone: "success",
        title: session.emailQueued ? "Portal email queued" : "Portal link created",
        description: session.emailQueued ? `Magic link will reach ${customer.email} shortly.` : session.url
      });
      setPortalOpen(false);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not create portal email",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setPortalBusy(false);
    }
  }

  async function submitMerge() {
    if (!customer || !mergeState || !mergeState.targetId) {
      notify({ tone: "warning", title: "Pick a customer", description: "Search and pick the customer to merge into." });
      return;
    }
    const target = customers.find((c) => c.id === mergeState.targetId);
    if (!target) return;
    const ok = await confirm({
      destructive: true,
      title: `Merge ${customer.name} into ${target.name}?`,
      description: "This is irreversible. All subscriptions, invoices, payments, and notes move to the target customer. The original record is kept for audit only.",
      confirmLabel: "Merge customers"
    });
    if (!ok) return;
    setBlocking(true);
    try {
      await mergeCustomer(customer.id, target.id);
      logAuditEvent({ actor: "You", action: "Merged customer", target: `${customer.email} → ${target.email}` });
      notify({ tone: "success", title: "Customers merged", description: `${customer.name} → ${target.name}.` });
      setMergeState(null);
      navigate(`/customers/${target.id}`, { replace: true });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not merge customer",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setBlocking(false);
    }
  }

  async function handleBlock() {
    if (!customer) return;
    const ok = await confirm({
      destructive: true,
      title: `Block ${customer.name}?`,
      description: "Blocking pauses all subscriptions, stops new charges, and emails the customer.",
      confirmLabel: "Block customer"
    });
    if (!ok) return;
    setBlocking(true);
    try {
      const result = await blockCustomer(customer.id);
      logAuditEvent({ actor: "You", action: "Blocked customer", target: customer.email });
      const countLabel = `${result.pausedSubscriptions} subscription${result.pausedSubscriptions === 1 ? "" : "s"}`;
      notify({
        tone: "info",
        title: "Customer blocked",
        description: result.emailSent
          ? `${countLabel} paused and ${customer.email} was notified.`
          : `${countLabel} paused.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not block customer",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setBlocking(false);
    }
  }

  async function submitNote() {
    if (!customer) return;
    if (!noteDraft.trim()) {
      notify({ tone: "warning", title: "Empty note", description: "Add some text before saving." });
      return;
    }
    const stamped = `${new Date().toISOString().slice(0, 10)} · You: ${noteDraft.trim()}`;
    const merged = customer.notes ? `${customer.notes}\n${stamped}` : stamped;
    setSavingNote(true);
    try {
      await updateCustomer(customer.id, { notes: merged });
      logAuditEvent({ actor: "You", action: "Added customer note", target: customer.email });
      notify({ tone: "success", title: "Note saved", description: "Visible to your team only." });
      setNoteDraft("");
      setNoteSheetOpen(false);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not save note",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSavingNote(false);
    }
  }

  const totalLifetime = customerPayments
    .filter((p) => p.amount > 0)
    .reduce((s, p) => s + p.amount, 0);
  const failedCount = customerPayments.filter((p) => p.status === "failed").length;
  const activeSubsCount = customerSubs.filter((s) => s.status === "active" || s.status === "trialing").length;

  const subColumns: DataTableColumn<Subscription>[] = [
    {
      key: "plan",
      header: "Plan",
      render: (s) => {
        const p = plans.find((x) => x.id === s.planId);
        return p ? (
          <Link to={`/plans/${p.id}`} className="mer-entity-cell">
            <strong>{p.name}</strong>
            <small>{p.code}</small>
          </Link>
        ) : <span>{s.planId}</span>;
      }
    },
    { key: "status", header: "Status", render: (s) => <Badge tone={subTone(s.status)}>{prettyStatus(s.status)}</Badge> },
    { key: "amount", header: "Amount", align: "right", render: (s) => formatCurrency(s.amount) },
    { key: "next", header: "Next bill", render: (s) => s.cancelAt ?? s.currentPeriodEnd },
    {
      key: "view",
      header: "",
      render: (s) => <Link to={`/subscriptions/${s.id}`} className="sp-button sp-button--ghost">View</Link>
    }
  ];

  const invoiceColumns: DataTableColumn<Invoice>[] = [
    {
      key: "number",
      header: "Invoice",
      render: (i) => (
        <Link to={`/invoices/${i.id}`} className="mer-entity-cell">
          <strong>{i.number}</strong>
          <small>{i.id}</small>
        </Link>
      )
    },
    { key: "status", header: "Status", render: (i) => <Badge tone={invoiceTone(i.status)}>{prettyStatus(i.status)}</Badge> },
    { key: "amount", header: "Amount", align: "right", render: (i) => formatCurrency(i.amountDue) },
    { key: "issued", header: "Issued", render: (i) => i.issuedAt },
    { key: "due", header: "Due", render: (i) => i.dueAt }
  ];

  return (
    <>
      <PageHeader
        eyebrow={
          <span className="mer-breadcrumb-eyebrow">
            <Link to="/customers" className="mer-card-link">
              <ArrowLeft size={12} aria-hidden="true" /> Customers
            </Link>
            <span> / {customer.id}</span>
          </span>
        }
        title={customer.name}
        description={`${customer.email} · ${customer.phone} · ${customer.country}`}
        actions={
          <>
            {canEditCustomer ? (
              <Button variant="secondary" icon={<Pencil size={16} />} onClick={openEdit}>Edit profile</Button>
            ) : null}
            {canSendPortalLink ? (
              <Button variant="secondary" icon={<Mail size={16} />} onClick={() => setPortalOpen(true)}>Send portal link</Button>
            ) : null}
            {canMergeCustomer ? (
              <Button variant="secondary" icon={<GitMerge size={16} />} onClick={() => setMergeState({ searchQuery: "", targetId: "" })}>Merge</Button>
            ) : null}
            {customer.status !== "blocked" && canBlockCustomer ? (
              <Button variant="danger" icon={<Ban size={16} />} onClick={handleBlock} disabled={blocking}>
                {blocking ? "Blocking..." : "Block"}
              </Button>
            ) : null}
          </>
        }
      />

      <div className="mer-detail-meta">
        <Badge tone={customerTone(customer.status)}>{prettyStatus(customer.status)}</Badge>
        <span>Customer since <strong>{customer.createdAt}</strong></span>
        <span>Last payment <strong>{customer.lastPaymentAt && customer.lastPaymentAt !== "—" ? formatRelative(customer.lastPaymentAt) : "—"}</strong></span>
      </div>

      <section className="sp-grid sp-grid-4">
        <StatCard label="Active subs" value={String(activeSubsCount)} delta={`${customerSubs.length} total`} tone="success" />
        <StatCard label="MRR" value={formatCurrency(customer.mrr)} delta="Normalized" tone="teal" />
        <StatCard label="Lifetime collected" value={formatCurrency(totalLifetime)} delta={`${customerPayments.filter((p) => p.amount > 0).length} payments`} tone="info" />
        <StatCard label="Failed attempts" value={String(failedCount)} delta={failedCount > 0 ? "Needs attention" : "All clear"} tone={failedCount > 0 ? "warning" : "neutral"} />
      </section>

      <Tabs
        value={tab}
        onChange={(v) => setTab(v as TabKey)}
        items={[
          { label: "Profile", value: "profile" },
          { label: "Subscriptions", value: "subscriptions", count: customerSubs.length },
          { label: "Invoices", value: "invoices", count: customerInvoices.length },
          { label: "Payment methods", value: "methods", count: customer.paymentMethods.length },
          { label: "Activity", value: "activity", count: customerActivity.length },
          { label: "Notes", value: "notes" }
        ]}
      />

      {tab === "profile" ? (
        <Card>
          <CardHeader title="Profile" description="Core contact and billing details for this customer." />
          <div className="mer-totals">
            <div className="mer-totals__row"><span>Name</span><strong>{customer.name}</strong></div>
            <div className="mer-totals__row"><span>Email</span><strong>{customer.email}</strong></div>
            <div className="mer-totals__row"><span>Phone</span><strong>{customer.phone}</strong></div>
            <div className="mer-totals__row"><span>Country</span><strong>{customer.country}</strong></div>
            <div className="mer-totals__row"><span>Status</span><Badge tone={customerTone(customer.status)}>{prettyStatus(customer.status)}</Badge></div>
            <div className="mer-totals__row"><span>Created</span><strong>{customer.createdAt}</strong></div>
          </div>
        </Card>
      ) : null}

      {tab === "subscriptions" ? (
        <Card>
          <CardHeader title="Subscriptions" description={`${customerSubs.length} subscription${customerSubs.length === 1 ? "" : "s"} on file.`} />
          {customerSubs.length ? (
            <DataTable columns={subColumns} rows={customerSubs} getRowKey={(s) => s.id} />
          ) : <p className="mer-empty">No subscriptions yet.</p>}
        </Card>
      ) : null}

      {tab === "invoices" ? (
        <Card>
          <CardHeader title="Invoices" description={`${customerInvoices.length} invoice${customerInvoices.length === 1 ? "" : "s"} issued.`} />
          {customerInvoices.length ? (
            <DataTable columns={invoiceColumns} rows={customerInvoices} getRowKey={(i) => i.id} />
          ) : <p className="mer-empty">No invoices issued yet.</p>}
        </Card>
      ) : null}

      {tab === "methods" ? (
        <Card>
          <CardHeader
            title="Payment methods"
            description={`${customer.paymentMethods.length} method${customer.paymentMethods.length === 1 ? "" : "s"} on file.`}
            action={tokenizedCardsEnabled && canManagePaymentMethods ? <Button variant="secondary" icon={<Plus size={14} />} onClick={openAddMethod}>Add method</Button> : undefined}
          />
          {customer.paymentMethods.length ? (
            <div className="mer-line-items">
              {customer.paymentMethods.map((m) => (
                <div key={m.id} className="mer-line-items__row">
                  <div>
                    <strong>{m.brand} ···· {m.last4}</strong>
                    <small>Expires {m.expiry} · {m.id}</small>
                  </div>
                  <span>{m.isDefault ? <Badge tone="success">Default</Badge> : null}</span>
                  <span>
                    {!m.isDefault && canManagePaymentMethods ? (
                      <Button
                        variant="ghost"
                        onClick={() => makeDefaultMethod(m)}
                        disabled={savingDefaultMethodId === m.id || Boolean(savingDefaultMethodId)}
                      >
                        {savingDefaultMethodId === m.id ? "Saving..." : "Make default"}
                      </Button>
                    ) : null}
                  </span>
                </div>
              ))}
            </div>
          ) : <p className="mer-empty">No payment methods on file.</p>}
        </Card>
      ) : null}

      {tab === "activity" ? (
        <Card>
          <CardHeader title="Activity" description={`${customerActivity.length} audit event${customerActivity.length === 1 ? "" : "s"} for this customer.`} />
          {customerActivity.length ? (
            <ul className="mer-timeline">
              {customerActivity.map((a) => (
                <li key={a.id} className="mer-timeline__row">
                  <span className="mer-timeline__dot" />
                  <div className="mer-timeline__text">
                    <strong>{a.action}</strong>
                    <small>by {a.actor} · {a.target}</small>
                  </div>
                  <span className="mer-timeline__time">{formatRelative(a.occurredAt)}</span>
                </li>
              ))}
            </ul>
          ) : <p className="mer-empty">No activity yet for this customer.</p>}
        </Card>
      ) : null}

      {tab === "notes" ? (
        <Card>
          <CardHeader
            title="Internal notes"
            description="Visible to your team only."
            action={canEditCustomer ? <Button variant="secondary" icon={<StickyNote size={14} />} onClick={() => setNoteSheetOpen(true)}>Add note</Button> : undefined}
          />
          {customer.notes ? (
            <pre className="mer-pre">{customer.notes}</pre>
          ) : <p className="mer-empty">No notes yet. Capture context that will help your team support this customer.</p>}
        </Card>
      ) : null}

      {/* Edit profile sheet */}
      <Sheet
        open={editOpen}
        title="Edit profile"
        description="Update contact and metadata. Subscriptions and payments are unaffected."
        onClose={() => setEditOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button onClick={submitEdit} disabled={savingProfile}>
              {savingProfile ? "Saving..." : "Save changes"}
            </Button>
          </>
        }
      >
        {editForm ? (
          <div className="mer-stack">
            <Field label="Full name">
              <TextInput value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
            </Field>
            <Field label="Email">
              <TextInput type="email" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
            </Field>
            <div className="mer-form-grid">
              <Field label="Phone">
                <TextInput value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} />
              </Field>
              <Field label="Country">
                <SelectInput value={editForm.country} onChange={(e) => setEditForm({ ...editForm, country: e.target.value })}>
                  <option value="Nigeria">Nigeria</option>
                  <option value="Ghana">Ghana</option>
                  <option value="Kenya">Kenya</option>
                  <option value="South Africa">South Africa</option>
                </SelectInput>
              </Field>
            </div>
            <Field label="Notes">
              <TextInput value={editForm.notes} onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })} />
            </Field>
          </div>
        ) : null}
      </Sheet>

      {/* Add note sheet */}
      <Sheet
        open={noteSheetOpen}
        title="Add note"
        description="Captured with timestamp and your name. Visible only to your team."
        onClose={() => setNoteSheetOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setNoteSheetOpen(false)}>Cancel</Button>
            <Button onClick={submitNote} disabled={savingNote}>
              {savingNote ? "Saving..." : "Save note"}
            </Button>
          </>
        }
      >
        <div className="mer-stack">
          <Field label="Note">
            <TextInput
              placeholder="What should your team know?"
              value={noteDraft}
              onChange={(e) => setNoteDraft(e.target.value)}
            />
          </Field>
        </div>
      </Sheet>

      {/* Add payment method modal */}
      <Modal
        open={!!methodOpen}
        title="Add payment method"
        description="Attach a tokenized card for downstream billing and customer portal usage."
        onClose={() => setMethodOpen(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setMethodOpen(null)}>Cancel</Button>
            <Button onClick={submitAddMethod} icon={<CreditCard size={14} />} disabled={savingMethod}>
              {savingMethod ? "Adding..." : "Add method"}
            </Button>
          </>
        }
      >
        {methodOpen ? (
          <div className="mer-stack">
            <Field label="Card brand">
              <SelectInput value={methodOpen.brand} onChange={(e) => setMethodOpen({ ...methodOpen, brand: e.target.value as PaymentMethod["brand"] })}>
                <option value="Visa">Visa</option>
                <option value="Mastercard">Mastercard</option>
                <option value="Verve">Verve</option>
                <option value="Amex">Amex</option>
              </SelectInput>
            </Field>
            <div className="mer-form-grid">
              <Field label="Last 4 digits">
                <TextInput maxLength={4} value={methodOpen.last4} onChange={(e) => setMethodOpen({ ...methodOpen, last4: e.target.value })} />
              </Field>
              <Field label="Expiry (MM/YY)">
                <TextInput value={methodOpen.expiry} onChange={(e) => setMethodOpen({ ...methodOpen, expiry: e.target.value })} />
              </Field>
            </div>
            <p className="mer-hint">Bank account payment methods are not enabled in this backend yet.</p>
          </div>
        ) : null}
      </Modal>

      {/* Send portal link modal */}
      <Modal
        open={portalOpen}
        title="Send portal link"
        description={`${customer.name} can manage their subscription, payment methods, and invoices from their portal.`}
        onClose={() => setPortalOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPortalOpen(false)}>Cancel</Button>
            <Button variant="secondary" onClick={copyPortalLink} disabled={portalBusy}>
              {portalBusy ? "Creating..." : "Copy link"}
            </Button>
            <Button onClick={emailPortalLink} icon={<Mail size={14} />} disabled={portalBusy}>
              {portalBusy ? "Creating..." : "Email link"}
            </Button>
          </>
        }
      >
        <div className="mer-stack">
          <Field label="Portal URL">
            <TextInput readOnly value="Generated after you choose Copy link or Email link" />
          </Field>
          <p className="mer-hint">Magic links expire in 24 hours and are single-use.</p>
        </div>
      </Modal>

      {/* Merge customer modal */}
      <Modal
        open={!!mergeState}
        title="Merge customer"
        description="Pick the destination customer. The current record will be marked merged and locked."
        onClose={() => setMergeState(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setMergeState(null)}>Cancel</Button>
            <Button variant="danger" onClick={submitMerge} disabled={blocking}>
              {blocking ? "Merging..." : "Merge customers"}
            </Button>
          </>
        }
      >
        {mergeState ? (
          <div className="mer-stack">
            <Field label="Search">
              <TextInput
                placeholder="Search by name or email"
                value={mergeState.searchQuery}
                onChange={(e) => setMergeState({ ...mergeState, searchQuery: e.target.value })}
              />
            </Field>
            <Field label="Merge into">
              <SelectInput value={mergeState.targetId} onChange={(e) => setMergeState({ ...mergeState, targetId: e.target.value })}>
                <option value="">Select destination customer…</option>
                {customers
                  .filter((c) => c.id !== customer.id && c.status !== "blocked")
                  .filter((c) => {
                    const q = mergeState.searchQuery.trim().toLowerCase();
                    if (!q) return true;
                    return c.name.toLowerCase().includes(q) || c.email.toLowerCase().includes(q);
                  })
                  .slice(0, 20)
                  .map((c) => (
                    <option key={c.id} value={c.id}>{c.name} ({c.email})</option>
                  ))}
              </SelectInput>
            </Field>
            <p className="mer-hint">All subscriptions, invoices, payments, and notes move to the destination.</p>
          </div>
        ) : null}
      </Modal>
    </>
  );
}

function customerTone(status: CustomerStatus): BadgeTone {
  switch (status) {
    case "active": return "success";
    case "delinquent": return "warning";
    case "churned": return "neutral";
    case "blocked": return "danger";
    default: return "neutral";
  }
}

function subTone(status: Subscription["status"]): BadgeTone {
  switch (status) {
    case "active": return "success";
    case "trialing": return "info";
    case "past_due": return "warning";
    case "paused": return "info";
    case "cancelled": return "neutral";
    case "incomplete": return "warning";
    default: return "neutral";
  }
}

function invoiceTone(status: Invoice["status"]): BadgeTone {
  switch (status) {
    case "paid": return "success";
    case "open": return "info";
    case "past_due": return "warning";
    case "uncollectible": return "danger";
    case "void": return "neutral";
    case "draft": return "neutral";
    default: return "neutral";
  }
}

function prettyStatus(status: string): string {
  return status
    .split("_")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

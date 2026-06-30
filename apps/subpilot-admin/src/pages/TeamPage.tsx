import { useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Modal,
  SegmentedControl,
  SelectInput,
  Sheet,
  TextInput
} from "@subpilot/ui";
import { Key, Mail, MoreHorizontal, Shield, ShieldOff, UserPlus } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { usePlatformPermissions } from "../auth/AuthContext";
import { useTeam, type TeamMemberRow } from "../api/team";

type RoleFilter = "all" | "Owner" | "Operator" | "Support" | "Read-only";

const FE_TO_BACKEND_ROLE: Record<string, string> = {
  Owner: "owner",
  Operator: "operator",
  Support: "support",
  "Read-only": "read_only",
};

const FE_TO_BACKEND_STATUS: Record<string, string> = {
  Active: "active",
  Invited: "invited",
  Suspended: "suspended",
};

export function TeamPage() {
  const { notify } = useFeedback();
  const { canManageTeam } = usePlatformPermissions();
  const [filter, setFilter] = useState<RoleFilter>("all");
  const [inviteOpen, setInviteOpen] = useState(false);
  const [editing, setEditing] = useState<TeamMemberRow | null>(null);
  const [revokeFor, setRevokeFor] = useState<TeamMemberRow | null>(null);

  // Invite form state
  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<string>("Operator");
  const [inviteSubmitting, setInviteSubmitting] = useState(false);
  const [lastInviteUrl, setLastInviteUrl] = useState<string | null>(null);

  // Edit form state
  const [editName, setEditName] = useState("");
  const [editRole, setEditRole] = useState<string>("Operator");
  const [editStatus, setEditStatus] = useState<string>("Active");
  const [editMfa, setEditMfa] = useState(false);
  const [editSubmitting, setEditSubmitting] = useState(false);

  const { rows: allRows, loading, error, invite, update, suspend, reactivate } = useTeam({
    role: filter === "all" ? undefined : FE_TO_BACKEND_ROLE[filter],
  });

  const rows = allRows;

  const counts = useMemo(
    () => ({
      total: allRows.length,
      active: allRows.filter((m) => m.status === "Active").length,
      invited: allRows.filter((m) => m.status === "Invited").length,
      mfa: allRows.filter((m) => m.mfa).length,
    }),
    [allRows],
  );

  const openEdit = (m: TeamMemberRow) => {
    setEditing(m);
    setEditName(m.name);
    setEditRole(m.role);
    setEditStatus(m.status);
    setEditMfa(m.mfa);
  };

  const handleInvite = async () => {
    if (!inviteEmail.trim()) {
      notify({ tone: "danger", title: "Email required", description: "Please enter a work email." });
      return;
    }
    setInviteSubmitting(true);
    try {
      const result = await invite({
        email: inviteEmail.trim(),
        displayName: inviteName.trim() || undefined,
        role: FE_TO_BACKEND_ROLE[inviteRole] ?? "operator",
      });
      setLastInviteUrl(result.invite.url);
      setInviteOpen(false);
      setInviteName("");
      setInviteEmail("");
      setInviteRole("Operator");
      notify({
        tone: "success",
        title: "Invitation sent",
        description: `${result.admin.email} will appear as Invited until they accept.`,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not send invitation.";
      notify({ tone: "danger", title: "Invite failed", description: message });
    } finally {
      setInviteSubmitting(false);
    }
  };

  const handleSave = async () => {
    if (!editing) return;
    setEditSubmitting(true);
    try {
      await update({
        rawId: editing.rawId,
        role: FE_TO_BACKEND_ROLE[editRole],
        status: FE_TO_BACKEND_STATUS[editStatus],
        displayName: editName,
        mfaEnabled: editMfa,
      });
      setEditing(null);
      notify({
        tone: "success",
        title: "Member updated",
        description: `${editName}'s settings have been saved.`,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not update member.";
      notify({ tone: "danger", title: "Update failed", description: message });
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleRevoke = async () => {
    if (!revokeFor) return;
    try {
      if (revokeFor.status === "Suspended") {
        await reactivate(revokeFor.rawId);
        notify({
          tone: "success",
          title: "Access restored",
          description: `${revokeFor.name} can sign in again.`,
        });
      } else {
        await suspend(revokeFor.rawId);
        notify({
          tone: "danger",
          title: "Access revoked",
          description: `${revokeFor.name} has been suspended.`,
        });
      }
      setRevokeFor(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Action failed.";
      notify({ tone: "danger", title: "Action failed", description: message });
    }
  };

  return (
    <>
      <PageHeader
        eyebrow={<span className="adm-kicker">Platform team</span>}
        title="Admin team"
        description="Manage who can sign in to the SubPilot admin console, what they can do, and how they authenticate."
        actions={
          <>
            <Button
              variant="ghost"
              icon={<Shield size={16} />}
              onClick={() =>
                notify({
                  tone: "info",
                  title: "Audit log opened",
                  description: "All admin sign-ins and actions for the past 90 days are available."
                })
              }
            >
              Audit access
            </Button>
            {canManageTeam ? (
              <Button icon={<UserPlus size={16} />} onClick={() => setInviteOpen(true)}>Invite teammate</Button>
            ) : null}
          </>
        }
      />

      {error ? (
        <Card><span className="adm-muted">{error}</span></Card>
      ) : null}
      {lastInviteUrl ? (
        <Card tone="mint">
          <CardHeader title="Latest invite link" description="Copy this link if the email cannot be delivered (dev/staging only)." />
          <code style={{ wordBreak: "break-all", fontSize: 12 }}>{lastInviteUrl}</code>
        </Card>
      ) : null}

      <section className="sp-grid sp-grid-4">
        <Card><span className="sp-stat-card__label">Members</span><strong style={{ display: "block", fontSize: 22, fontWeight: 700 }}>{counts.total}</strong></Card>
        <Card><span className="sp-stat-card__label">Active</span><strong style={{ display: "block", fontSize: 22, fontWeight: 700 }}>{counts.active}</strong></Card>
        <Card><span className="sp-stat-card__label">Pending invites</span><strong style={{ display: "block", fontSize: 22, fontWeight: 700 }}>{counts.invited}</strong></Card>
        <Card><span className="sp-stat-card__label">MFA enrolled</span><strong style={{ display: "block", fontSize: 22, fontWeight: 700 }}>{counts.mfa} / {counts.total}</strong></Card>
      </section>

      <div className="adm-search-row">
        <SegmentedControl
          label="Filter by role"
          value={filter}
          onChange={(v) => setFilter(v as RoleFilter)}
          items={[
            { label: "All", value: "all" },
            { label: "Owners", value: "Owner" },
            { label: "Operators", value: "Operator" },
            { label: "Support", value: "Support" },
            { label: "Read-only", value: "Read-only" }
          ]}
        />
      </div>

      <Card>
        <CardHeader title="Members" description="Anyone with credentials to the SubPilot admin console." />
        {loading && rows.length === 0 ? (
          <span className="adm-muted">Loading…</span>
        ) : (
          <table className="sp-table">
            <thead>
              <tr><th>Name</th><th>Role</th><th>Status</th><th>MFA</th><th>Last active</th><th>Invited by</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((m) => (
                <tr key={m.id}>
                  <td>
                    <div className="adm-team-cell">
                      <span className="adm-profile__avatar" aria-hidden="true">{m.initials}</span>
                      <div>
                        <strong>{m.name}</strong>
                        <small>{m.email}</small>
                      </div>
                    </div>
                  </td>
                  <td><Badge tone={m.role === "Owner" ? "teal" : m.role === "Operator" ? "info" : m.role === "Support" ? "success" : "neutral"}>{m.role}</Badge></td>
                  <td><Badge tone={m.status === "Active" ? "success" : m.status === "Invited" ? "warning" : "danger"}>{m.status}</Badge></td>
                  <td>{m.mfa ? <Badge tone="success">Enrolled</Badge> : <Badge tone="warning">Required</Badge>}</td>
                  <td><span className="adm-muted">{m.lastActive === "—" ? "—" : formatTime(m.lastActive)}</span></td>
                  <td><span className="adm-muted">{m.invitedBy}</span></td>
                  <td className="sp-align-right">
                    <div className="adm-row-actions">
                      {canManageTeam ? (
                        <Button variant="ghost" onClick={() => openEdit(m)}>Edit</Button>
                      ) : null}
                      {canManageTeam ? (
                        <Button variant="ghost" icon={<MoreHorizontal size={14} />} aria-label="More" onClick={() => setRevokeFor(m)} />
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && !loading ? (
                <tr><td colSpan={7}><span className="adm-muted">No members match this filter.</span></td></tr>
              ) : null}
            </tbody>
          </table>
        )}
      </Card>

      <section className="sp-grid sp-grid-2">
        <Card tone="mint">
          <CardHeader title="Authentication policy" description="Applies to every admin who can sign in." />
          <ul className="adm-toggle-list">
            <li className="adm-toggle-row"><input type="checkbox" defaultChecked /> <strong>Require MFA for all roles</strong></li>
            <li className="adm-toggle-row"><input type="checkbox" defaultChecked /> <strong>SSO via Google Workspace</strong></li>
            <li className="adm-toggle-row"><input type="checkbox" /> <strong>IP allowlist (corporate VPN)</strong></li>
            <li className="adm-toggle-row"><input type="checkbox" defaultChecked /> <strong>Session timeout after 12h</strong></li>
            <li className="adm-toggle-row"><input type="checkbox" /> <strong>Block sign-ins from new countries</strong></li>
          </ul>
        </Card>

        <Card>
          <CardHeader title="Role permissions" description="Granular capability matrix per role." />
          <table className="sp-table">
            <thead>
              <tr><th>Capability</th><th>Owner</th><th>Operator</th><th>Support</th><th>Read-only</th></tr>
            </thead>
            <tbody>
              {[
                ["Suspend / reinstate merchants", true, true, false, false],
                ["Issue refunds", true, true, false, false],
                ["Rotate webhook secrets", true, true, false, false],
                ["Approve KYC", true, false, false, false],
                ["Invite teammates", true, false, false, false],
                ["View merchant data", true, true, true, true]
              ].map(([cap, ...rest]) => (
                <tr key={cap as string}>
                  <td><strong>{cap as string}</strong></td>
                  {rest.map((on, i) => (
                    <td key={i}>{on ? <Badge tone="success">Allowed</Badge> : <Badge tone="neutral">—</Badge>}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </section>

      {/* Invite */}
      <Modal
        open={inviteOpen}
        title="Invite a teammate"
        description="Send a magic-link invitation to join the SubPilot admin console."
        onClose={() => setInviteOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setInviteOpen(false)}>Cancel</Button>
            <Button onClick={handleInvite} icon={<Mail size={14} />} disabled={inviteSubmitting}>
              {inviteSubmitting ? "Sending…" : "Send invitation"}
            </Button>
          </>
        }
      >
        <div className="adm-form-grid">
          <Field label="Full name">
            <TextInput value={inviteName} onChange={(e) => setInviteName(e.target.value)} placeholder="Adaeze Okoro" />
          </Field>
          <Field label="Work email">
            <TextInput value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="adaeze@subpilot.dev" />
          </Field>
          <Field label="Role">
            <SelectInput value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}>
              <option>Owner</option>
              <option>Operator</option>
              <option>Support</option>
              <option>Read-only</option>
            </SelectInput>
          </Field>
        </div>
      </Modal>

      {/* Edit */}
      <Sheet
        open={!!editing}
        title={editing ? `Edit ${editing.name}` : ""}
        description="Change role, MFA, and view scope."
        onClose={() => setEditing(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
            <Button onClick={handleSave} disabled={editSubmitting}>
              {editSubmitting ? "Saving…" : "Save changes"}
            </Button>
          </>
        }
      >
        {editing ? (
          <>
            <div className="adm-form-grid">
              <Field label="Name"><TextInput value={editName} onChange={(e) => setEditName(e.target.value)} /></Field>
              <Field label="Email"><TextInput defaultValue={editing.email} disabled /></Field>
              <Field label="Role">
                <SelectInput value={editRole} onChange={(e) => setEditRole(e.target.value)}>
                  <option>Owner</option>
                  <option>Operator</option>
                  <option>Support</option>
                  <option>Read-only</option>
                </SelectInput>
              </Field>
              <Field label="Status">
                <SelectInput value={editStatus} onChange={(e) => setEditStatus(e.target.value)}>
                  <option>Active</option>
                  <option>Suspended</option>
                </SelectInput>
              </Field>
            </div>
            <h3 className="adm-sheet-section">Security</h3>
            <ul className="adm-toggle-list">
              <li className="adm-toggle-row">
                <input type="checkbox" checked={editMfa} onChange={(e) => setEditMfa(e.target.checked)} />{" "}
                <strong>MFA enrolled</strong>
              </li>
            </ul>
            <Button
              variant="ghost"
              icon={<Key size={14} />}
              onClick={() => {
                if (!editing) return;
                notify({
                  tone: "info",
                  title: "Reset email queued",
                  description: `${editing.name} will receive a password reset link at ${editing.email}.`
                });
              }}
            >
              Send password reset email
            </Button>
          </>
        ) : null}
      </Sheet>

      {/* Suspend / Reactivate */}
      <Modal
        open={!!revokeFor}
        title={
          revokeFor
            ? revokeFor.status === "Suspended"
              ? `Reactivate ${revokeFor.name}?`
              : `Revoke access for ${revokeFor.name}?`
            : ""
        }
        description={
          revokeFor?.status === "Suspended"
            ? "They will be able to sign in again immediately."
            : "They will be signed out within a minute and their invitation links will stop working."
        }
        onClose={() => setRevokeFor(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRevokeFor(null)}>Cancel</Button>
            <Button
              variant={revokeFor?.status === "Suspended" ? undefined : "danger"}
              onClick={handleRevoke}
              icon={<ShieldOff size={14} />}
            >
              {revokeFor?.status === "Suspended" ? "Reactivate" : "Revoke access"}
            </Button>
          </>
        }
      >
        <p>This is reversible: you can {revokeFor?.status === "Suspended" ? "suspend" : "re-invite"} the teammate later. Audit log entries will be preserved.</p>
      </Modal>
    </>
  );
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

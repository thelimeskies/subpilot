import { useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DataTable,
  Field,
  Modal,
  SegmentedControl,
  SelectInput,
  Sheet,
  StatCard,
  TextInput,
  type BadgeTone,
  type DataTableColumn
} from "@subpilot/ui";
import {
  Mail,
  Send,
  ShieldOff,
  Trash2,
  UserCheck,
  UserPlus
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { isApiError } from "../api/client";
import { usePermissions } from "../auth/AuthContext";
import { useData } from "../data/store";
import { formatRelative } from "../data/selectors";
import type { TeamMember } from "../data/seed";

const ROLES: TeamMember["role"][] = ["Owner", "Admin", "Finance", "Support", "Read-only"];
const INVITE_ROLES: TeamMember["role"][] = ["Admin", "Finance", "Support", "Read-only"];

interface InviteForm {
  email: string;
  role: TeamMember["role"];
  message: string;
}

interface RoleChangeState {
  member: TeamMember;
  role: TeamMember["role"];
}

export function TeamPage() {
  const {
    teamMembers,
    inviteTeamMember,
    updateTeamMember,
    resendTeamInvite,
    resetTeamMemberMfa,
    removeTeamMember,
    logAuditEvent
  } = useData();
  const { notify, confirm } = useFeedback();
  const { can } = usePermissions();
  const canManageTeam = can("manage_team_roles");

  const [inviteOpen, setInviteOpen] = useState<InviteForm | null>(null);
  const [roleOpen, setRoleOpen] = useState<RoleChangeState | null>(null);
  const [savingTeam, setSavingTeam] = useState(false);

  const stats = useMemo(() => {
    const active = teamMembers.filter((m) => m.status === "active").length;
    const invited = teamMembers.filter((m) => m.status === "invited").length;
    const mfa = teamMembers.filter((m) => m.mfaEnabled).length;
    return {
      active,
      invited,
      mfa,
      mfaPct: teamMembers.length > 0 ? (mfa / teamMembers.length) * 100 : 0
    };
  }, [teamMembers]);

  // ---------- Invite ----------
  function openInvite() {
    setInviteOpen({ email: "", role: "Support", message: "" });
  }
  function patchInvite(patch: Partial<InviteForm>) {
    setInviteOpen((prev) => (prev ? { ...prev, ...patch } : prev));
  }
  async function submitInvite() {
    if (!inviteOpen) return;
    const email = inviteOpen.email.trim();
    if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      notify({ tone: "warning", title: "Valid email required", description: "Enter a valid work email address." });
      return;
    }
    if (teamMembers.some((m) => m.email.toLowerCase() === email.toLowerCase())) {
      notify({ tone: "warning", title: "Already a member", description: `${email} is already on the team.` });
      return;
    }
    setSavingTeam(true);
    try {
      await inviteTeamMember({
        name: email.split("@")[0],
        email,
        role: inviteOpen.role,
        mfaEnabled: false,
        message: inviteOpen.message
      });
      logAuditEvent({ actor: "You", action: "Invited teammate", target: email });
      notify({
        tone: "success",
        title: "Invite sent",
        description: `${email} will receive a setup link.`
      });
      setInviteOpen(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not send invite",
        description: isApiError(err) ? err.reason : "The backend rejected the team invite."
      });
    } finally {
      setSavingTeam(false);
    }
  }

  // ---------- Resend invite ----------
  async function handleResend(member: TeamMember) {
    setSavingTeam(true);
    try {
      await resendTeamInvite(member.id);
      logAuditEvent({ actor: "You", action: "Resent invite", target: member.email });
      notify({
        tone: "info",
        title: "Invite resent",
        description: `${member.email} will receive a new setup link.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not resend invite",
        description: isApiError(err) ? err.reason : "The backend rejected the resend request."
      });
    } finally {
      setSavingTeam(false);
    }
  }

  // ---------- Change role ----------
  function openRoleChange(member: TeamMember) {
    setRoleOpen({ member, role: member.role });
  }
  async function submitRoleChange() {
    if (!roleOpen) return;
    if (roleOpen.role === roleOpen.member.role) {
      setRoleOpen(null);
      return;
    }
    setSavingTeam(true);
    try {
      await updateTeamMember(roleOpen.member.id, { role: roleOpen.role });
      logAuditEvent({
        actor: "You",
        action: `Changed role to ${roleOpen.role}`,
        target: roleOpen.member.email
      });
      notify({
        tone: "success",
        title: "Role updated",
        description: `${roleOpen.member.name} is now ${roleOpen.role}.`
      });
      setRoleOpen(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not update role",
        description: isApiError(err) ? err.reason : "The backend rejected the role change."
      });
    } finally {
      setSavingTeam(false);
    }
  }

  // ---------- Reset MFA ----------
  async function handleMfaReset(member: TeamMember) {
    setSavingTeam(true);
    try {
      await resetTeamMemberMfa(member.id);
      logAuditEvent({ actor: "You", action: "Reset MFA", target: member.email });
      notify({
        tone: "info",
        title: "MFA reset",
        description: `${member.name} will be prompted to enrol again on next sign-in.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not reset MFA",
        description: isApiError(err) ? err.reason : "The backend rejected the MFA reset."
      });
    } finally {
      setSavingTeam(false);
    }
  }

  // ---------- Remove ----------
  async function handleRemove(member: TeamMember) {
    if (member.role === "Owner") {
      notify({
        tone: "warning",
        title: "Owner cannot be removed",
        description: "Transfer ownership first from Settings → Danger zone."
      });
      return;
    }
    const ok = await confirm({
      destructive: true,
      title: `Remove ${member.name}?`,
      description: `${member.email} will lose access immediately. Their personal data is retained per audit policy.`,
      confirmLabel: "Remove member"
    });
    if (!ok) return;
    setSavingTeam(true);
    try {
      await removeTeamMember(member.id);
      logAuditEvent({ actor: "You", action: "Removed teammate", target: member.email });
      notify({ tone: "warning", title: "Member removed", description: member.email });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not remove member",
        description: isApiError(err) ? err.reason : "The backend rejected the remove request."
      });
    } finally {
      setSavingTeam(false);
    }
  }

  const columns: DataTableColumn<TeamMember>[] = [
    {
      key: "name",
      header: "Member",
      render: (m) => (
        <span className="mer-entity-cell">
          <strong>{m.name}</strong>
          <small>{m.email}</small>
        </span>
      )
    },
    {
      key: "role",
      header: "Role",
      render: (m) => <Badge tone={roleTone(m.role)}>{m.role}</Badge>
    },
    {
      key: "mfa",
      header: "MFA",
      render: (m) =>
        m.mfaEnabled ? <Badge tone="success">Enabled</Badge> : <Badge tone="warning">Off</Badge>
    },
    {
      key: "status",
      header: "Status",
      render: (m) => <Badge tone={statusTone(m.status)}>{prettyStatus(m.status)}</Badge>
    },
    {
      key: "lastSeen",
      header: "Last seen",
      render: (m) => (m.lastSeenAt && m.lastSeenAt !== "—" ? formatRelative(m.lastSeenAt) : "—")
    },
    ...(canManageTeam
      ? [
          {
            key: "actions",
            header: "",
            render: (m: TeamMember) => (
              <div className="mer-row-actions">
                {m.status === "invited" ? (
                  <Button variant="ghost" icon={<Send size={14} />} onClick={() => handleResend(m)} disabled={savingTeam}>
                    Resend
                  </Button>
                ) : null}
                {m.status !== "disabled" && m.role !== "Owner" ? (
                  <Button variant="ghost" icon={<UserCheck size={14} />} onClick={() => openRoleChange(m)} disabled={savingTeam}>
                    Role
                  </Button>
                ) : null}
                {m.status !== "disabled" && m.role !== "Owner" && m.mfaEnabled ? (
                  <Button variant="ghost" icon={<ShieldOff size={14} />} onClick={() => handleMfaReset(m)} disabled={savingTeam}>
                    Reset MFA
                  </Button>
                ) : null}
                {m.status !== "disabled" && m.role !== "Owner" ? (
                  <Button variant="ghost" icon={<Trash2 size={14} />} onClick={() => handleRemove(m)} disabled={savingTeam}>
                    Remove
                  </Button>
                ) : null}
              </div>
            )
          } as DataTableColumn<TeamMember>
        ]
      : [])
  ];

  return (
    <>
      <PageHeader
        eyebrow="People"
        title="Team"
        description="Members, roles, and MFA hygiene for your merchant workspace."
        actions={
          canManageTeam ? (
            <Button icon={<UserPlus size={16} />} onClick={openInvite}>Invite member</Button>
          ) : null
        }
      />

      <section className="sp-grid sp-grid-4">
        <StatCard label="Active members" value={String(stats.active)} delta={`${teamMembers.length} total`} tone="info" />
        <StatCard label="Pending invites" value={String(stats.invited)} delta={stats.invited > 0 ? "Awaiting acceptance" : "All accepted"} tone={stats.invited > 0 ? "warning" : "success"} />
        <StatCard label="MFA enrolled" value={`${stats.mfaPct.toFixed(0)}%`} delta={`${stats.mfa} of ${teamMembers.length}`} tone={stats.mfaPct >= 80 ? "success" : "warning"} />
        <StatCard label="Roles in use" value={String(new Set(teamMembers.map((m) => m.role)).size)} delta={`Owner, ${ROLES.slice(1).join(", ")}`} tone="neutral" />
      </section>

      <Card>
        <CardHeader title="Team members" description="Roles map to permissions across plans, billing, and settings." />
        <DataTable columns={columns} rows={teamMembers} getRowKey={(m) => m.id} emptyText="No teammates yet — invite your first." />
      </Card>

      {/* ---------- Invite Sheet ---------- */}
      <Sheet
        open={!!inviteOpen}
        onClose={() => setInviteOpen(null)}
        title="Invite teammate"
        description="They'll receive a setup link to create their password and enrol in MFA."
        footer={
          <>
            <Button variant="ghost" onClick={() => setInviteOpen(null)}>Cancel</Button>
            <Button onClick={submitInvite} icon={<Mail size={14} />} disabled={savingTeam}>
              {savingTeam ? "Sending…" : "Send invite"}
            </Button>
          </>
        }
      >
        {inviteOpen ? (
          <div className="sp-form-grid">
            <Field label="Work email" hint="They'll receive a setup link at this address.">
              <TextInput
                type="email"
                placeholder="teammate@yourcompany.com"
                value={inviteOpen.email}
                onChange={(e) => patchInvite({ email: e.target.value })}
              />
            </Field>
            <Field label="Role" hint="You can change this later from this page.">
              <SelectInput
                value={inviteOpen.role}
                onChange={(e) => patchInvite({ role: e.target.value as TeamMember["role"] })}
              >
                {INVITE_ROLES.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </SelectInput>
            </Field>
            <Field label="Personal message (optional)">
              <TextInput
                placeholder="Welcome to the team!"
                value={inviteOpen.message}
                onChange={(e) => patchInvite({ message: e.target.value })}
              />
            </Field>
          </div>
        ) : null}
      </Sheet>

      {/* ---------- Change role Modal ---------- */}
      <Modal
        open={!!roleOpen}
        onClose={() => setRoleOpen(null)}
        title="Change role"
        description={roleOpen ? `Update the role for ${roleOpen.member.name}.` : ""}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRoleOpen(null)}>Cancel</Button>
            <Button onClick={submitRoleChange} icon={<UserCheck size={14} />} disabled={savingTeam}>
              {savingTeam ? "Updating…" : "Update role"}
            </Button>
          </>
        }
      >
        {roleOpen ? (
          <div className="sp-form-grid">
            <SegmentedControl
              value={roleOpen.role}
              onChange={(v) => setRoleOpen((prev) => (prev ? { ...prev, role: v as TeamMember["role"] } : prev))}
              label="Role"
              items={INVITE_ROLES.map((r) => ({ label: r, value: r }))}
            />
            <p className="mer-hint">
              {roleHint(roleOpen.role)}
            </p>
          </div>
        ) : null}
      </Modal>
    </>
  );
}

function roleTone(role: TeamMember["role"]): BadgeTone {
  switch (role) {
    case "Owner": return "danger";
    case "Admin": return "warning";
    case "Finance": return "info";
    case "Support": return "teal";
    default: return "neutral";
  }
}

function statusTone(status: TeamMember["status"]): BadgeTone {
  switch (status) {
    case "active": return "success";
    case "invited": return "warning";
    case "disabled": return "neutral";
    default: return "neutral";
  }
}

function prettyStatus(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function roleHint(role: TeamMember["role"]): string {
  switch (role) {
    case "Admin": return "Full access except ownership transfer and workspace deletion.";
    case "Finance": return "Read/write access to invoices, payments, and payouts. No team or settings changes.";
    case "Support": return "Read access to customers and subscriptions. Can resend portal links.";
    case "Read-only": return "View-only across the dashboard. Cannot mutate any data.";
    default: return "";
  }
}

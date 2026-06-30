import { Button, Field, SelectInput, TextInput } from "@subpilot/ui";
import { Plus, Trash2 } from "lucide-react";
import type { OnboardingDraft, TeamInvite } from "../useOnboardingDraft";

interface Props {
  draft: OnboardingDraft;
  setTeam: (team: TeamInvite[]) => void;
}

const ROLES: TeamInvite["role"][] = ["Admin", "Finance", "Support", "Read-only"];

export function InviteTeamStep({ draft, setTeam }: Props) {
  const team = draft.team;

  function addRow() {
    setTeam([...team, { email: "", role: "Admin" }]);
  }

  function updateRow(index: number, patch: Partial<TeamInvite>) {
    setTeam(team.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  function removeRow(index: number) {
    setTeam(team.filter((_, i) => i !== index));
  }

  return (
    <div className="mer-step">
      <header className="mer-step__head">
        <h2>Invite your team</h2>
        <p>Add finance and support teammates. You can skip this and invite people later.</p>
      </header>

      {team.length === 0 ? (
        <div className="mer-empty-state">
          <strong>No invites yet.</strong>
          <span>Add a row to invite a teammate, or skip and continue.</span>
        </div>
      ) : (
        <div className="mer-team-rows">
          {team.map((row, index) => (
            <div key={index} className="mer-team-row">
              <Field label={index === 0 ? "Work email" : ""}>
                <TextInput
                  type="email"
                  value={row.email}
                  onChange={(e) => updateRow(index, { email: e.target.value })}
                  placeholder="teammate@yourbrand.com"
                />
              </Field>
              <Field label={index === 0 ? "Role" : ""}>
                <SelectInput value={row.role} onChange={(e) => updateRow(index, { role: e.target.value as TeamInvite["role"] })}>
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </SelectInput>
              </Field>
              <Button
                type="button"
                variant="ghost"
                icon={<Trash2 size={14} />}
                onClick={() => removeRow(index)}
                aria-label={`Remove invite ${index + 1}`}
              >
                Remove
              </Button>
            </div>
          ))}
        </div>
      )}

      <div className="mer-step__actions">
        <Button type="button" variant="secondary" icon={<Plus size={14} />} onClick={addRow}>
          Add another invite
        </Button>
      </div>
    </div>
  );
}

export function validateTeamStep(draft: OnboardingDraft) {
  if (draft.team.length === 0) return true;
  return draft.team.every((row) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(row.email.trim()));
}

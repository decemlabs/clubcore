/**
 * ChangeRoleModal — owner-gated dialog to change a staff user's role (Phase 112 TEAM-01).
 *
 * Opens from an «Изменить роль» DropdownMenuItem in the Settings Team list for active,
 * non-self users. Gated by can(role, 'update', 'users') — already true only for owner.
 *
 * Props:
 *   user    — the user whose role is being changed (id, fullName, role)
 *   open    — dialog open state
 *   onOpenChange — dialog open state setter
 *
 * Validation:
 *   - selectedRole must differ from user.role to enable confirm button
 *   - Confirm disabled when selectedRole === user.role or busy
 *
 * On success: Sonner toast + usersKeys.lists() invalidated via hook; modal closes
 * On 409: mapped Russian toast; modal stays open
 *
 * Info callout: "Роль вступит в силу при следующем входе сотрудника."
 */
import { useState } from 'react';
import { toast } from 'sonner';
import { ShieldCheck } from '@/components/icons';
import { AdaptiveModal } from '@/components/modals/AdaptiveModal';
import { IconChip, ModalButton, Field, ChipGroup } from '@/components/modals/fields';
import { useChangeUserRole, ApiError } from '@/features/users/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ROLE_LABEL: Record<'owner' | 'reception', string> = {
  owner: 'Владелец',
  reception: 'Ресепшн',
};

const ROLE_OPTIONS = [
  { value: 'reception', label: 'Ресепшн' },
  { value: 'owner', label: 'Владелец' },
];

// ---------------------------------------------------------------------------
// Error handler — maps ApiError codes to Russian toasts
// ---------------------------------------------------------------------------

function handleRoleChangeError(err: unknown) {
  if (err instanceof ApiError) {
    if (err.code === 'cannot_change_own_role') {
      toast.error('Нельзя изменить собственную роль');
    } else if (
      err.code === 'cannot_change_last_owner_role' ||
      err.code === 'cannot_demote_last_owner'
    ) {
      // Map BOTH codes for robustness (backend emits cannot_change_last_owner_role;
      // UI-SPEC lists cannot_demote_last_owner — handle both per plan note)
      toast.error('Нельзя понизить единственного владельца');
    } else if (err.code === 'forbidden') {
      toast.error('Недостаточно прав');
    } else {
      toast.error('Не удалось изменить роль. Попробуйте ещё раз.');
    }
  } else {
    toast.error('Не удалось изменить роль. Попробуйте ещё раз.');
  }
}

// ---------------------------------------------------------------------------
// ChangeRoleModal
// ---------------------------------------------------------------------------

export interface ChangeRoleModalUser {
  id: string;
  fullName: string;
  role: 'owner' | 'reception';
}

export interface ChangeRoleModalProps {
  user: ChangeRoleModalUser;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ChangeRoleModal({ user, open, onOpenChange }: ChangeRoleModalProps) {
  const changeRole = useChangeUserRole();
  const [selectedRole, setSelectedRole] = useState<'owner' | 'reception'>(user.role);
  const [busy, setBusy] = useState(false);

  const sameRole = selectedRole === user.role;
  const canConfirm = !sameRole && !busy;

  function handleOpenChange(value: boolean) {
    if (!value) {
      onOpenChange(false);
      // Reset state after dialog animation
      setTimeout(() => {
        setSelectedRole(user.role);
        setBusy(false);
      }, 300);
    }
  }

  function handleSubmit() {
    if (!canConfirm) return;
    setBusy(true);
    changeRole.mutate(
      { id: user.id, role: selectedRole },
      {
        onSuccess: () => {
          handleOpenChange(false);
          toast.success('Роль изменена', {
            description: `${user.fullName} → ${ROLE_LABEL[selectedRole]}`,
          });
        },
        onError: (err) => {
          setBusy(false);
          handleRoleChangeError(err);
        },
      },
    );
  }

  const description = `${user.fullName} · ${ROLE_LABEL[user.role]}`;

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={handleOpenChange}
      title="Изменить роль"
      icon={<IconChip tone="indigo" icon={ShieldCheck} />}
      description={description}
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={busy} onClick={() => handleOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton variant="primary" disabled={!canConfirm} onClick={handleSubmit}>
            Сохранить роль
          </ModalButton>
        </>
      }
    >
      {/* Role picker */}
      <Field label="Новая роль" required>
        <ChipGroup
          options={ROLE_OPTIONS}
          value={selectedRole}
          onChange={(v) => setSelectedRole(v as 'owner' | 'reception')}
        />
      </Field>

      {/* Info callout — role applies on next login */}
      <div className="mt-3.5 rounded-xl border-[0.5px] border-border bg-surface-2 px-3.5 py-3 text-[12.5px] leading-snug text-fg-muted">
        Роль вступит в силу при следующем входе сотрудника.
        Текущая сессия продолжается с прежними правами.
      </div>
    </AdaptiveModal>
  );
}

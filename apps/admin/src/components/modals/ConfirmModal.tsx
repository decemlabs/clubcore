import { useEffect, useState } from 'react';
import { AdaptiveModal } from './AdaptiveModal';
import { ModalButton, ModalInput } from './fields';
import type { ConfirmPayload } from './modals-context';

/**
 * Универсальный диалог подтверждения. Управляется ConfirmPayload из modals-context:
 * заголовок/сообщение, кнопки, тон (default|danger) и опциональный type-to-confirm
 * (нужно ввести `requireText`, чтобы разблокировать действие). Переиспользуется всеми
 * деструктивными и необратимыми действиями фазы (архив/удаление/выход без сохранения).
 */
export function ConfirmModal({
  open,
  onOpenChange,
  payload,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  payload?: ConfirmPayload;
}) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);

  // Сброс ввода/занятости при каждом открытии (модалка остаётся смонтированной).
  useEffect(() => {
    if (open) {
      setText('');
      setBusy(false);
    }
  }, [open]);

  if (!payload) return null;

  const needsText = Boolean(payload.requireText);
  const canConfirm = !needsText || text.trim() === payload.requireText;

  const confirm = async () => {
    if (!canConfirm || busy) return;
    try {
      setBusy(true);
      await payload.onConfirm();
      onOpenChange(false);
    } catch {
      setBusy(false);
    }
  };

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      title={payload.title}
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={() => onOpenChange(false)}>
            {payload.cancelLabel ?? 'Отмена'}
          </ModalButton>
          <ModalButton
            variant={payload.tone === 'danger' ? 'danger' : 'primary'}
            disabled={!canConfirm || busy}
            onClick={confirm}
          >
            {payload.confirmLabel ?? 'Подтвердить'}
          </ModalButton>
        </>
      }
    >
      {payload.message ? (
        <div className="text-[13.5px] leading-relaxed text-fg-muted [&_b]:font-semibold [&_b]:text-fg">
          {payload.message}
        </div>
      ) : null}

      {needsText ? (
        <div className="mt-3.5">
          <label className="mb-1.5 block text-xs font-semibold text-fg-muted">
            Введите <b className="font-semibold text-fg">{payload.requireText}</b>, чтобы
            подтвердить
          </label>
          <ModalInput
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={payload.requireText}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && canConfirm) confirm();
            }}
          />
        </div>
      ) : null}
    </AdaptiveModal>
  );
}

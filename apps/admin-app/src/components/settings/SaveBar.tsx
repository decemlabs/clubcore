import { useState } from 'react';

export function SaveBar({
  count,
  onSave,
  onCancel,
}: {
  count: number;
  onSave: () => void;
  onCancel: () => void;
}) {
  const [saving, setSaving] = useState(false);
  if (count === 0) return null;
  const word = count === 1 ? 'разделе' : 'разделах';

  return (
    <div className="pointer-events-none sticky bottom-4 z-20 flex justify-center">
      <div className="pointer-events-auto flex items-center gap-3 rounded-full border-[0.5px] border-border bg-surface px-3 py-2 shadow-3">
        <span className="ml-1.5 size-2 animate-pulse rounded-full bg-primary" />
        <span className="text-[13px] font-medium">
          Есть несохранённые изменения{' '}
          <span className="text-fg-subtle">
            в {count} {word}
          </span>
        </span>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-full px-3 py-1.5 text-[12.5px] font-semibold text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Отменить
        </button>
        <button
          type="button"
          disabled={saving}
          onClick={() => {
            setSaving(true);
            window.setTimeout(() => {
              setSaving(false);
              onSave();
            }, 700);
          }}
          className="rounded-full bg-primary px-4 py-1.5 text-[12.5px] font-semibold text-[#06120c] transition-opacity hover:bg-[#5ee9b8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-70"
        >
          {saving ? 'Сохраняем…' : 'Сохранить'}
        </button>
      </div>
    </div>
  );
}

import { Initials } from '@/components/ui/initials';
import { MoreHorizontal } from '@/components/icons';
import type { ClientDetail, NoteItem } from '@/features/clients/detail';
import { Card, CardHead, Chip, RichText } from './shared';

function Note({ note }: { note: NoteItem }) {
  return (
    <div className="border-t-[0.5px] border-border px-5 py-3.5 first:border-t-0">
      <div className="mb-2 flex items-center gap-2">
        <Initials
          initials={note.authorInitials}
          color={note.authorColor}
          className="size-6 text-[10px]"
        />
        <span className="text-[13px] font-semibold">
          {note.author}
          {note.authorTag ? (
            <span className="font-normal text-fg-subtle"> · {note.authorTag}</span>
          ) : null}
        </span>
        <span className="text-[12.5px] text-fg-subtle">{note.date}</span>
        <button
          type="button"
          aria-label="Действия с заметкой"
          className="ml-auto grid size-7 place-items-center rounded-lg text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <MoreHorizontal className="size-[15px]" />
        </button>
      </div>
      <div className="text-[13.5px] leading-relaxed text-fg">
        <RichText value={note.body} />
      </div>
      {note.tags ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {note.tags.map((t) => (
            <Chip key={t.label} warn={t.warn}>
              {t.label}
            </Chip>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function NotesTab({ notes }: { notes: ClientDetail['notes'] }) {
  return (
    <Card>
      <CardHead title="Заметки администратора" sub="Видны всем администраторам · клиент не видит" />
      <div className="border-t-[0.5px] border-border bg-surface-2 px-5 py-4">
        <textarea
          placeholder={notes.composePlaceholder}
          className="min-h-[60px] w-full resize-y rounded-xl border-[0.5px] border-border bg-surface px-3 py-2.5 text-[13px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-fg-subtle"
        />
        <div className="mt-2.5 flex items-center justify-between gap-3 text-xs text-fg-subtle">
          <span>Будет видна всем администраторам клуба</span>
          <button
            type="button"
            className="inline-flex h-8 items-center rounded-full bg-fg px-3.5 text-[12.5px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
          >
            Добавить
          </button>
        </div>
      </div>
      <div>
        {notes.items.map((note) => (
          <Note key={note.id} note={note} />
        ))}
      </div>
    </Card>
  );
}

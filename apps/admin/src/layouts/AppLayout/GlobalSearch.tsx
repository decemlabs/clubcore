import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { CommandPalette } from './CommandPalette';

/**
 * Триггер глобального поиска в шапке: выглядит как поле, но открывает ⌘K-палитру
 * (реальный инпут — внутри палитры). Глобальный хоткей ⌘K / Ctrl+K тоже открывает её.
 */
export function GlobalSearch() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="relative flex h-10 w-full max-w-xl items-center rounded-full bg-surface pl-10 pr-3 text-left text-[13px] text-fg-subtle outline-none ring-1 ring-border transition hover:ring-border-strong focus-visible:ring-2 focus-visible:ring-ink/20"
      >
        <Search className="absolute left-3.5 size-4 text-fg-subtle" strokeWidth={2} />
        <span className="truncate">Поиск по клиентам, тренерам, абонементам…</span>
        <kbd className="ml-auto hidden h-5 select-none items-center rounded-md bg-black/[0.05] px-1.5 text-[11px] font-semibold text-fg-subtle md:inline-flex dark:bg-white/10">
          ⌘ K
        </kbd>
      </button>
      <CommandPalette open={open} onOpenChange={setOpen} />
    </>
  );
}

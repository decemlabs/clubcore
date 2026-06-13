interface PagePlaceholderProps {
  title: string;
  hint?: string;
}

/**
 * Заглушка страницы до интеграции HTML-шаблона.
 * Удаляется/заменяется реальным контентом по мере поступления макетов.
 */
export function PagePlaceholder({ title, hint }: PagePlaceholderProps) {
  return (
    <div className="flex h-full flex-col gap-2 px-8 py-8">
      <h1 className="text-[28px] font-semibold tracking-tight text-fg">{title}</h1>
      <p className="text-[14px] text-fg-muted">
        {hint ?? 'Страница ждёт интеграции HTML-шаблона.'}
      </p>
    </div>
  );
}

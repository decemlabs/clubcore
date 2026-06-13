import type { ReactNode } from 'react';
import { useIsMobile } from '@/hooks/use-mobile';
import { cn } from '@/lib/cn';
import { X } from '@/components/icons';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Drawer, DrawerContent, DrawerDescription, DrawerTitle } from '@/components/ui/drawer';

export type ModalSize = 'default' | 'wide';

const MAX_W: Record<ModalSize, string> = {
  default: 'sm:max-w-[540px]',
  wide: 'sm:max-w-[720px]',
};

export interface AdaptiveModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  /** Ведущий элемент шапки: иконка-чип или аватар (слева от заголовка). */
  icon?: ReactNode;
  size?: ModalSize;
  /** Левая инфо-строка футера (напр. «К оплате: 24 600 ₽»). */
  footerInfo?: ReactNode;
  /** Кнопки действий футера. На мобильном растягиваются на всю ширину. */
  footerActions?: ReactNode;
  children: ReactNode;
}

function CloseButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Закрыть"
      className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-3 text-fg-muted transition-colors hover:bg-border hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <X className="size-3.5" strokeWidth={2.4} />
    </button>
  );
}

export function AdaptiveModal({
  open,
  onOpenChange,
  title,
  description,
  icon,
  size = 'default',
  footerInfo,
  footerActions,
  children,
}: AdaptiveModalProps) {
  const isMobile = useIsMobile();

  const body = (
    <div className="min-h-0 flex-1 overflow-y-auto px-5 py-[18px] sm:px-[22px]">{children}</div>
  );

  const foot =
    footerInfo || footerActions ? (
      <div className="flex shrink-0 flex-col-reverse gap-2.5 border-t-[0.5px] border-border bg-surface-2 px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-[22px]">
        {footerInfo ? (
          <div className="text-xs text-fg-muted max-sm:text-center">{footerInfo}</div>
        ) : null}
        {footerActions ? (
          <div className="flex gap-2 max-sm:flex-col-reverse sm:shrink-0 [&>button]:max-sm:w-full">
            {footerActions}
          </div>
        ) : null}
      </div>
    ) : null;

  if (isMobile) {
    return (
      <Drawer open={open} onOpenChange={onOpenChange}>
        <DrawerContent className="max-h-[92dvh] border-border bg-surface">
          <div className="flex items-start gap-3 px-5 pb-3 pt-2 sm:px-[22px]">
            {icon ? <div className="shrink-0">{icon}</div> : null}
            <div className="min-w-0 flex-1">
              <DrawerTitle className="text-[17px] font-bold leading-tight tracking-[-0.3px]">
                {title}
              </DrawerTitle>
              {description ? (
                <DrawerDescription className="mt-1 text-[12.5px] leading-snug text-fg-muted">
                  {description}
                </DrawerDescription>
              ) : null}
            </div>
            <CloseButton onClick={() => onOpenChange(false)} />
          </div>
          <div className="border-t-[0.5px] border-border" />
          {body}
          {foot}
        </DrawerContent>
      </Drawer>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className={cn(
          'flex max-h-[calc(100dvh-48px)] flex-col gap-0 overflow-hidden rounded-[18px] border-border bg-surface p-0',
          MAX_W[size],
        )}
      >
        <div className="flex items-start gap-3.5 border-b-[0.5px] border-border px-[22px] py-4">
          {icon ? <div className="shrink-0">{icon}</div> : null}
          <div className="min-w-0 flex-1">
            <DialogTitle className="text-[17px] font-bold leading-tight tracking-[-0.3px]">
              {title}
            </DialogTitle>
            {description ? (
              <DialogDescription className="mt-1 text-[12.5px] leading-snug text-fg-muted">
                {description}
              </DialogDescription>
            ) : (
              <DialogDescription className="sr-only">{title}</DialogDescription>
            )}
          </div>
          <CloseButton onClick={() => onOpenChange(false)} />
        </div>
        {body}
        {foot}
      </DialogContent>
    </Dialog>
  );
}

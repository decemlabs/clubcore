import { toast } from 'sonner';
import { AdaptiveModal } from './AdaptiveModal';
import { ModalButton, ResultItem, ResultList, Section } from './fields';
import { RECENT_CHECKINS } from './options';

function QrScanner() {
  return (
    <>
      <div
        className="relative mx-auto mb-3.5 mt-1 aspect-square max-w-[280px] overflow-hidden rounded-[18px] shadow-[inset_0_0_0_0.5px_rgba(255,255,255,0.06)]"
        style={{
          background:
            'radial-gradient(120% 90% at 30% 20%, rgba(45,212,164,0.08), transparent 60%), linear-gradient(135deg,#1c1917,#2a2826)',
        }}
      >
        <div
          className="absolute inset-8 rounded-xl"
          style={{
            background:
              'repeating-linear-gradient(0deg, transparent 0, transparent 16px, rgba(255,255,255,0.04) 16px, rgba(255,255,255,0.04) 17px), repeating-linear-gradient(90deg, transparent 0, transparent 16px, rgba(255,255,255,0.04) 16px, rgba(255,255,255,0.04) 17px)',
          }}
        />
        <span className="absolute left-[26px] top-[26px] size-[26px] rounded-tl-md border-l-[3px] border-t-[3px] border-primary" />
        <span className="absolute right-[26px] top-[26px] size-[26px] rounded-tr-md border-r-[3px] border-t-[3px] border-primary" />
        <span className="absolute bottom-[26px] left-[26px] size-[26px] rounded-bl-md border-b-[3px] border-l-[3px] border-primary" />
        <span className="absolute bottom-[26px] right-[26px] size-[26px] rounded-br-md border-b-[3px] border-r-[3px] border-primary" />
        <span
          className="absolute left-9 right-9 h-0.5 rounded-sm bg-[linear-gradient(90deg,transparent,var(--primary),transparent)] shadow-[0_0_14px_1px_var(--primary)]"
          style={{ animation: 'qr-scan 2.6s cubic-bezier(0.45,0,0.55,1) infinite' }}
        />
        <span className="absolute bottom-2.5 left-1/2 flex -translate-x-1/2 items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.4px] text-[rgba(245,245,244,0.7)]">
          <span className="size-1.5 animate-pulse rounded-full bg-primary shadow-[0_0_0_3px_rgba(45,212,164,0.25)]" />
          Сканирование
        </span>
      </div>
      <div className="mx-3 mb-1 text-center text-[12.5px] leading-snug text-fg-muted">
        Камера ищет код · клиент открывает QR во вкладке «Моя карта»
      </div>
    </>
  );
}

export function CheckinModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const simulate = () => {
    toast.success('Чек-ин принят', { description: 'Марк Левин · Годовой' });
    onOpenChange(false);
  };

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      title="Чек-ин по QR"
      description="Поднесите телефон или браслет клиента к камере"
      footerInfo={
        <>
          Можно ввести <b className="font-[650] text-fg">код вручную</b> или найти клиента в списке
        </>
      }
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={() => onOpenChange(false)}>
            Код вручную
          </ModalButton>
          <ModalButton onClick={simulate}>Симулировать</ModalButton>
        </>
      }
    >
      <QrScanner />
      <Section>Последние чек-ины</Section>
      <ResultList>
        {RECENT_CHECKINS.map((c) => (
          <ResultItem
            key={`${c.initials}-${c.time}`}
            initials={c.initials}
            color={c.color}
            name={c.name}
            meta={c.meta}
            aside={
              <>
                {c.time}
                <br />
                <span
                  className={
                    c.now ? 'font-semibold text-primary-deep dark:text-primary' : 'text-fg-subtle'
                  }
                >
                  {c.ago}
                </span>
              </>
            }
          />
        ))}
      </ResultList>
    </AdaptiveModal>
  );
}

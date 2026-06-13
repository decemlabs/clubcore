/**
 * CashboxKpis — KPI strip for the cash ledger (Phase 103-03).
 *
 * Приход / Возвраты / Нетто — computed client-side from payments items.
 * Amounts in kopecks; formatted via formatRub(kopecks / 100).
 * Нетто shown in text-danger when negative.
 */
import { cn } from '@/lib/cn';
import { StatStrip } from '@/components/layout/StatStrip';
import { KpiTile } from '@/components/ui/KpiTile';
import { Banknote, Undo2, Wallet } from '@/components/icons';
import { formatRub } from '@/lib/format';

export function CashboxKpis({
  prikhod,
  vozvrat,
  netto,
}: {
  prikhod: number;
  vozvrat: number;
  netto: number;
}) {
  return (
    <StatStrip className="grid-cols-1 gap-4 sm:grid-cols-3">
      <KpiTile
        icon={Banknote}
        label="Приход"
        value={formatRub(prikhod / 100)}
      />
      <KpiTile
        icon={Undo2}
        label="Возвраты"
        value={
          vozvrat > 0 ? (
            <span className="text-danger">{formatRub(vozvrat / 100)}</span>
          ) : (
            formatRub(0)
          )
        }
      />
      <KpiTile
        icon={Wallet}
        label="Нетто"
        value={
          <span className={cn(netto < 0 && 'text-danger')}>
            {formatRub(netto / 100)}
          </span>
        }
      />
    </StatStrip>
  );
}

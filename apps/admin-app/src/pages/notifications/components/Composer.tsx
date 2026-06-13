import { useState } from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { Send } from '@/components/icons';
import { CHANNEL_LABEL, type AudienceOpt, type Channel } from '@/features/notifications/types';
import { PanelHead, Vars } from './parts';

const FIELD =
  'h-[42px] w-full rounded-[11px] border-[0.5px] border-border-strong bg-surface-2 px-3.5 text-[14px] text-fg outline-none transition-colors focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)]';
const LABEL = 'mb-1.5 block text-[12px] font-semibold text-fg-muted';

function MiniSeg<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { v: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="grid w-full auto-cols-fr grid-flow-col gap-[3px] rounded-[10px] bg-surface-3 p-[3px]">
      {options.map((o) => {
        const active = o.v === value;
        return (
          <button
            key={o.v}
            type="button"
            onClick={() => onChange(o.v)}
            className={cn(
              'h-[34px] rounded-lg text-[12.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active ? 'bg-surface text-fg shadow-1' : 'text-fg-muted hover:text-fg',
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

const VAR_CHIPS = ['{имя}', '{абонемент}', '{дата}', '{филиал}'];

export function Composer({
  audiences,
  defaultMessage,
}: {
  audiences: AudienceOpt[];
  defaultMessage: string;
}) {
  const [audIdx, setAudIdx] = useState(1);
  const [channel, setChannel] = useState<Channel>('sms');
  const [subject, setSubject] = useState('Ваш абонемент скоро закончится');
  const [message, setMessage] = useState(defaultMessage);
  const [time, setTime] = useState<'now' | 'later'>('now');

  const aud = audiences[audIdx] ?? audiences[0]!;

  return (
    <div>
      <PanelHead title="Массовая рассылка" />
      <div className="grid gap-[18px] p-[18px] lg:grid-cols-[minmax(0,1fr)_300px]">
        {/* Form */}
        <div className="min-w-0">
          <div className="mb-3.5">
            <label className={LABEL}>Аудитория</label>
            <select
              value={audIdx}
              onChange={(e) => setAudIdx(Number(e.target.value))}
              className={cn(FIELD, 'cursor-pointer appearance-none')}
            >
              {audiences.map((a, i) => (
                <option key={a.label} value={i}>
                  {a.label}
                </option>
              ))}
            </select>
            <div className="mt-2 flex items-center justify-between rounded-[11px] bg-primary-soft px-3.5 py-2.5">
              <span className="text-[13px] font-[650] text-primary-deep dark:text-primary">
                Получателей
              </span>
              <span className="text-[16px] font-bold tabular-nums text-primary-deep dark:text-primary">
                {aud.n}
              </span>
            </div>
          </div>

          <div className="mb-3.5">
            <label className={LABEL}>Канал</label>
            <MiniSeg
              value={channel}
              onChange={setChannel}
              options={[
                { v: 'sms', label: 'SMS' },
                { v: 'push', label: 'Push' },
                { v: 'email', label: 'Email' },
              ]}
            />
          </div>

          {channel === 'email' ? (
            <div className="mb-3.5">
              <label className={LABEL}>Тема письма</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className={FIELD}
              />
            </div>
          ) : null}

          <div className="mb-3.5">
            <label className={LABEL}>Сообщение</label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className={cn(FIELD, 'min-h-[110px] resize-y py-3 leading-relaxed')}
            />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {VAR_CHIPS.map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setMessage((m) => `${m} ${v}`.trim())}
                  className="rounded-full border-[0.5px] border-border-strong bg-surface px-2.5 py-[5px] font-mono text-[11.5px] font-semibold text-fg-muted transition-colors hover:border-fg-subtle hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {v}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className={LABEL}>Время отправки</label>
            <MiniSeg
              value={time}
              onChange={setTime}
              options={[
                { v: 'now', label: 'Сейчас' },
                { v: 'later', label: 'Запланировать' },
              ]}
            />
          </div>
        </div>

        {/* Preview */}
        <div className="lg:sticky lg:top-[90px] lg:self-start">
          <div className="rounded-[20px] border-[0.5px] border-border bg-surface-2 px-3.5 py-4">
            <div className="mb-3 text-center text-[11px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
              Предпросмотр
            </div>
            <div className="rounded-[14px] rounded-bl-[4px] border-[0.5px] border-border bg-surface px-3.5 py-3 shadow-1">
              <div className="mb-2 flex items-center gap-1.5">
                <span className="grid size-4 place-items-center rounded-[4px] bg-fg text-[9px] font-extrabold text-primary dark:bg-primary dark:text-[#06120c]">
                  М
                </span>
                <span className="text-[11px] font-bold text-fg-muted">Мой зал</span>
              </div>
              <div className="text-[13px] leading-relaxed">
                {channel === 'email' && subject ? (
                  <div className="mb-1 font-semibold">{subject}</div>
                ) : null}
                <Vars text={message} />
              </div>
            </div>
            <div className="mt-3 text-center text-[11px] text-fg-subtle">
              {CHANNEL_LABEL[channel]} · ~{message.length} символов · 1 сегмент
            </div>
          </div>
          <button
            type="button"
            onClick={() => toast.success(`Рассылка запущена · ${aud.n} получателей`)}
            className="mt-3 inline-flex h-[42px] w-full items-center justify-center gap-2 rounded-[10px] bg-fg text-[13.5px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
          >
            <Send className="size-[15px]" strokeWidth={2.2} />
            Отправить {aud.n} клиентам
          </button>
          <button
            type="button"
            onClick={() => toast('Сохранено в черновики')}
            className="mt-2 inline-flex h-[42px] w-full items-center justify-center rounded-[10px] border-[0.5px] border-border-strong bg-surface text-[13.5px] font-semibold text-fg transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            В черновики
          </button>
        </div>
      </div>
    </div>
  );
}

import { useState } from 'react';
import { toast } from 'sonner';
import { useImportExport } from '@/features/import-export/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { PageHeader } from '@/components/layout/PageHeader';
import { Segmented } from '@/components/ui/Segmented';
import {
  FileText,
  Table,
  Info,
  TriangleAlert,
  CheckCircle2,
  Download,
  Check,
} from '@/components/icons';
import {
  Btn,
  Panel,
  Callout,
  Stepper,
  Dropzone,
  FileChip,
  MapRowItem,
  PreviewTable,
  ErrorRowItem,
  FormatCard,
  ChecklistItem,
  type Step,
} from './components/parts';

const STEPS: Step[] = [
  { key: 'upload', label: 'Загрузка' },
  { key: 'map', label: 'Маппинг' },
  { key: 'preview', label: 'Предпросмотр' },
  { key: 'errors', label: 'Ошибки' },
];

const FORMATS = [
  { key: 'csv', icon: FileText, name: 'CSV', sub: 'Для Excel / Sheets' },
  { key: 'xlsx', icon: Table, name: 'XLSX', sub: 'Excel с форматами' },
  { key: 'pdf', icon: FileText, name: 'PDF', sub: 'Для печати' },
] as const;

const DATASETS = [
  { key: 'clients', label: 'Клиенты и абонементы (847)' },
  { key: 'payments', label: 'История платежей' },
  { key: 'attendance', label: 'Посещаемость' },
];

function Foot({ back, right }: { back?: React.ReactNode; right: React.ReactNode }) {
  return (
    <div className="mt-4 flex items-center justify-between gap-2">
      {back ?? <span />}
      {right}
    </div>
  );
}

export function ImportExportPage() {
  const { data, isPending, isError, refetch } = useImportExport();
  const [view, setView] = useState<'import' | 'export'>('import');
  const [step, setStep] = useState(0);
  const [file, setFile] = useState(false);
  const [mapValues, setMapValues] = useState<string[]>([]);
  const [format, setFormat] = useState<'csv' | 'xlsx' | 'pdf'>('csv');
  const [datasets, setDatasets] = useState<Record<string, boolean>>({
    clients: true,
    payments: true,
    attendance: false,
  });
  const [running, setRunning] = useState(false);
  const [imported, setImported] = useState(false);

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  const map = mapValues.length ? mapValues : data.mapRows.map((r) => r.field);
  const setMap = (i: number, v: string) =>
    setMapValues((prev) =>
      (prev.length ? prev : data.mapRows.map((r) => r.field)).map((x, idx) => (idx === i ? v : x)),
    );

  const runImport = () => {
    setRunning(true);
    window.setTimeout(() => {
      setRunning(false);
      setImported(true);
      toast.success(`Импорт завершён · ${data.readyCount} клиентов добавлено`);
    }, 900);
  };

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHeader
        title={view === 'import' ? 'Импорт данных' : 'Экспорт данных'}
        subtitle={
          view === 'import'
            ? 'Загрузите файл с клиентами — мы сопоставим колонки, проверим и добавим в базу.'
            : 'Выгрузите клиентов, платежи или отчёты в нужном формате.'
        }
        actions={
          <Segmented
            ariaLabel="Импорт или экспорт"
            options={[
              { value: 'import', label: 'Импорт' },
              { value: 'export', label: 'Экспорт' },
            ]}
            value={view}
            onChange={(v) => setView(v)}
          />
        }
      />

      {view === 'import' ? (
        <>
          <Stepper steps={STEPS} current={step} onGo={setStep} />

          {/* Шаг 1 — загрузка */}
          {step === 0 ? (
            <>
              <Panel title="Загрузка файла" caption="CSV или XLSX до 10 МБ · до 5 000 строк за раз">
                {file ? (
                  <FileChip
                    name={data.fileName}
                    meta={data.fileMeta}
                    onRemove={() => setFile(false)}
                  />
                ) : (
                  <Dropzone onPick={() => setFile(true)} />
                )}
                <div className="mt-3.5">
                  <Callout tone="info" icon={Info}>
                    Первая строка должна содержать заголовки колонок.{' '}
                    <button
                      type="button"
                      onClick={() => toast('Шаблон скачивается')}
                      className="font-semibold text-fg underline-offset-2 hover:underline"
                    >
                      Скачать шаблон-пример
                    </button>{' '}
                    для корректного импорта.
                  </Callout>
                </div>
              </Panel>
              <Foot
                right={
                  <Btn disabled={!file} onClick={() => setStep(1)}>
                    Далее · сопоставить колонки
                  </Btn>
                }
              />
            </>
          ) : null}

          {/* Шаг 2 — маппинг */}
          {step === 1 ? (
            <>
              <Panel
                title="Сопоставление колонок"
                caption={`Свяжите колонки файла с полями системы · ${data.recognizedLabel}`}
              >
                {data.mapRows.map((row, i) => (
                  <MapRowItem
                    key={row.src}
                    row={row}
                    fields={data.fields}
                    value={map[i] ?? row.field}
                    onChange={(v) => setMap(i, v)}
                  />
                ))}
              </Panel>
              <Foot
                back={
                  <Btn variant="ghost" onClick={() => setStep(0)}>
                    Назад
                  </Btn>
                }
                right={<Btn onClick={() => setStep(2)}>Далее · предпросмотр</Btn>}
              />
            </>
          ) : null}

          {/* Шаг 3 — предпросмотр */}
          {step === 2 ? (
            <>
              <Panel
                title="Предпросмотр"
                caption={
                  <>
                    Первые строки после сопоставления ·{' '}
                    <b className="font-semibold text-primary-deep dark:text-primary">
                      {data.readyCount} готовы
                    </b>{' '}
                    · <b className="font-semibold text-danger">{data.errorCount} с ошибками</b>
                  </>
                }
                bodyless
              >
                <PreviewTable rows={data.previewRows} />
              </Panel>
              <Callout tone="warn" icon={TriangleAlert}>
                В <b>{data.errorCount} строках</b> найдены ошибки. Их можно пропустить или исправить
                на следующем шаге.
              </Callout>
              <Foot
                back={
                  <Btn variant="ghost" onClick={() => setStep(1)}>
                    Назад
                  </Btn>
                }
                right={<Btn onClick={() => setStep(3)}>Проверить ошибки</Btn>}
              />
            </>
          ) : null}

          {/* Шаг 4 — ошибки */}
          {step === 3 ? (
            <>
              <Panel
                title="Отчёт об ошибках"
                caption={`${data.errorCount} строк требуют внимания перед импортом`}
              >
                {data.errorRows.map((row) => (
                  <ErrorRowItem key={row.line} row={row} onSkip={() => toast('Строка пропущена')} />
                ))}
                <div className="mt-3 text-[12px] text-fg-subtle">
                  … и ещё {data.moreErrors} строк с ошибками
                </div>
              </Panel>
              {imported ? (
                <Callout tone="ok" icon={CheckCircle2}>
                  <b>Импорт завершён.</b> Добавлено {data.readyCount} клиентов, {data.errorCount}{' '}
                  пропущено.
                </Callout>
              ) : null}
              <Foot
                back={
                  <Btn variant="ghost" onClick={() => setStep(2)}>
                    Назад
                  </Btn>
                }
                right={
                  imported ? (
                    <span />
                  ) : (
                    <Btn onClick={runImport} disabled={running}>
                      <Check className="size-3.5" strokeWidth={2.6} />
                      {running ? 'Импорт…' : `Импортировать ${data.readyCount} строк`}
                    </Btn>
                  )
                }
              />
            </>
          ) : null}
        </>
      ) : (
        /* Экспорт */
        <>
          <Panel>
            <div className="mb-2 text-[12px] font-semibold text-fg-muted">Формат</div>
            <div className="grid grid-cols-1 gap-2.5 min-[520px]:grid-cols-3">
              {FORMATS.map((f) => (
                <FormatCard
                  key={f.key}
                  icon={f.icon}
                  name={f.name}
                  sub={f.sub}
                  active={format === f.key}
                  onClick={() => setFormat(f.key)}
                />
              ))}
            </div>

            <div className="mb-1 mt-[18px] text-[12px] font-semibold text-fg-muted">
              Что выгрузить
            </div>
            <div className="divide-y divide-border">
              {DATASETS.map((d) => (
                <ChecklistItem
                  key={d.key}
                  label={d.label}
                  checked={!!datasets[d.key]}
                  onToggle={() => setDatasets((p) => ({ ...p, [d.key]: !p[d.key] }))}
                />
              ))}
            </div>
          </Panel>
          <Foot
            right={
              <Btn
                onClick={() =>
                  toast(`Экспорт ${format.toUpperCase()} запущен · файл скоро будет готов`)
                }
              >
                <Download className="size-[14px]" />
                Скачать {format.toUpperCase()}
              </Btn>
            }
          />
        </>
      )}
    </div>
  );
}

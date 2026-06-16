/**
 * Доменные типы экрана «Импорт / Экспорт» (ImportExport.html).
 * Импорт — мастер из 4 шагов (загрузка → маппинг → предпросмотр → ошибки);
 * экспорт — выбор формата и датасетов.
 */

export interface MapRow {
  /** Колонка файла (mono). */
  src: string;
  /** Пример значения. */
  sample: string;
  /** Поле системы по умолчанию. */
  field: string;
}

export interface PreviewRow {
  ok: boolean;
  name: string;
  phone: string;
  plan: string;
  email: string;
  /** Индексы невалидных ячеек: 0=name,1=phone,2=plan,3=email. */
  bad: number[];
}

export interface ErrorRow {
  line: number;
  title: string;
  detail: string;
}

export interface ImportExportData {
  fileName: string;
  fileMeta: string;
  /** Поля системы для маппинга (последнее — «Пропустить»). */
  fields: string[];
  mapRows: MapRow[];
  previewRows: PreviewRow[];
  errorRows: ErrorRow[];
  moreErrors: number;
  recognizedLabel: string;
  readyCount: number;
  errorCount: number;
}

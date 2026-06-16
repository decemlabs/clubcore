/** Сид-данные экрана «Импорт / Экспорт» (ImportExport.html). */
import type { ImportExportData } from '@/features/import-export/types';

const SKIP = '— Пропустить —';

export const importExportData: ImportExportData = {
  fileName: 'clients_export_2026.csv',
  fileMeta: '312 строк · 84 КБ · загружено',
  fields: ['Имя', 'Фамилия', 'Телефон', 'Email', 'Абонемент', 'Дата рождения', SKIP],
  mapRows: [
    { src: 'full_name', sample: 'Анна Петрова', field: 'Имя' },
    { src: 'phone', sample: '+7 916 224-18-03', field: 'Телефон' },
    { src: 'email', sample: 'anna.p@mail.ru', field: 'Email' },
    { src: 'plan', sample: '12 месяцев', field: 'Абонемент' },
    { src: 'birth', sample: '14.03.1994', field: 'Дата рождения' },
    { src: 'notes', sample: 'утренние тренировки', field: SKIP },
  ],
  previewRows: [
    {
      ok: true,
      name: 'Анна Петрова',
      phone: '+7 916 224-18-03',
      plan: '12 месяцев',
      email: 'anna.p@mail.ru',
      bad: [],
    },
    {
      ok: true,
      name: 'Максим Соколов',
      phone: '+7 903 552-10-44',
      plan: '6 месяцев',
      email: 'm.sokolov@mail.ru',
      bad: [],
    },
    { ok: false, name: 'Игорь', phone: '89163320911', plan: '', email: 'нет email', bad: [1, 3] },
    {
      ok: true,
      name: 'Карина Левчук',
      phone: '+7 916 408-22-71',
      plan: '3 месяца',
      email: 'karina.l@mail.ru',
      bad: [],
    },
    {
      ok: false,
      name: '',
      phone: '+7 905 118-44-20',
      plan: 'годовой',
      email: 'sv@bk',
      bad: [0, 3],
    },
    {
      ok: true,
      name: 'Павел Сидоров',
      phone: '+7 919 887-03-55',
      plan: '12 месяцев',
      email: 'pavel.s@mail.ru',
      bad: [],
    },
  ],
  errorRows: [
    {
      line: 3,
      title: 'Строка 3 · Игорь',
      detail: 'Не указана фамилия · телефон в неверном формате · нет email',
    },
    {
      line: 5,
      title: 'Строка 5 · (без имени)',
      detail: 'Не указано имя · email «sv@bk» некорректен',
    },
    {
      line: 18,
      title: 'Строка 18 · Олег Романов',
      detail: 'Дубликат: клиент с таким телефоном уже есть',
    },
    { line: 27, title: 'Строка 27 · Мария К.', detail: 'Тариф «премиум» не найден в системе' },
  ],
  moreErrors: 10,
  recognizedLabel: '6 из 6 распознано',
  readyCount: 298,
  errorCount: 14,
};

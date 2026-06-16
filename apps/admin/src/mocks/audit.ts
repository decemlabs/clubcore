/** Сид-данные экрана «Журнал действий» (Audit.html). */
import type { AuditActor, AuditData } from '@/features/audit/types';

const MK: AuditActor = {
  name: 'Маша Костина',
  gradient: 'linear-gradient(135deg,#8b5cf6,#ec4899)',
  initials: 'МК',
};
const AL: AuditActor = {
  name: 'Артём Лебедев',
  gradient: 'linear-gradient(135deg,#6366f1,#818cf8)',
  initials: 'АЛ',
};
const DS: AuditActor = {
  name: 'Дмитрий Сомов',
  gradient: 'linear-gradient(135deg,#0ea5e9,#38bdf8)',
  initials: 'ДС',
};

export const auditData: AuditData = {
  groups: [
    {
      label: 'Сегодня · 30 апреля',
      date: '30 апреля',
      events: [
        {
          id: 'EV-90412',
          time: '14:12',
          action: 'edit',
          actor: MK,
          lead: 'Изменён ',
          obj: 'абонемент',
          tail: ' · Анна Петрова',
          object: 'Абонемент · Анна Петрова',
          ip: '31.184.220.14',
          diff: [
            { label: 'Тариф', old: '«6 месяцев»', new: '«12 месяцев»' },
            { label: 'Действует до', old: '14.08.2026', new: '14.02.2027' },
          ],
        },
        {
          id: 'EV-90357',
          time: '13:40',
          action: 'create',
          actor: MK,
          lead: 'Создан ',
          obj: 'клиент',
          tail: ' · Алина Маркова',
          object: 'Клиент · Алина Маркова',
          ip: '31.184.220.14',
          diff: [
            { label: 'Имя', old: '—', new: 'Алина Маркова' },
            { label: 'Телефон', old: '—', new: '+7 916 770-22-10' },
          ],
        },
        {
          id: 'EV-90291',
          time: '12:30',
          action: 'delete',
          actor: AL,
          lead: 'Удалён ',
          obj: 'тариф',
          tail: ' · «Пробный»',
          object: 'Тариф · Пробный',
          ip: '95.24.18.7',
          diff: [{ label: 'Статус', old: 'активен', new: 'удалён' }],
        },
        {
          id: 'EV-90244',
          time: '11:05',
          action: 'edit',
          actor: DS,
          lead: 'Изменена ',
          obj: 'роль',
          tail: ' · Ресепшн',
          object: 'Роль · Ресепшн',
          ip: '176.59.40.2',
          diff: [
            { label: 'Доступ к «Касса»', old: 'нет', new: 'просмотр' },
            { label: 'Доступ к «Отчёты»', old: 'просмотр', new: 'нет' },
          ],
        },
      ],
    },
    {
      label: 'Вчера · 29 апреля',
      date: '29 апреля',
      events: [
        {
          id: 'EV-90118',
          time: '21:30',
          action: 'login',
          actor: MK,
          lead: 'Вход в систему',
          obj: '',
          tail: '',
          object: 'Сессия',
          ip: '31.184.220.14',
          diff: [
            { label: 'Устройство', old: '—', new: 'Chrome · macOS' },
            { label: 'Филиал', old: '—', new: 'Тверская' },
          ],
        },
        {
          id: 'EV-90077',
          time: '18:02',
          action: 'edit',
          actor: AL,
          lead: 'Изменены ',
          obj: 'настройки филиала',
          tail: ' · Тверская',
          object: 'Филиал · Тверская',
          ip: '95.24.18.7',
          diff: [
            { label: 'Комиссия зала', old: '25%', new: '30%' },
            { label: 'Часы (Сб)', old: '10:00–20:00', new: '10:00–22:00' },
          ],
        },
        {
          id: 'EV-90013',
          time: '09:14',
          action: 'create',
          actor: DS,
          lead: 'Создана ',
          obj: 'тренировка',
          tail: ' · Йога 15:00',
          object: 'Тренировка · Йога',
          ip: '176.59.40.2',
          diff: [
            { label: 'Направление', old: '—', new: 'Йога' },
            { label: 'Тренер', old: '—', new: 'Ольга Власова' },
          ],
        },
      ],
    },
  ],
};

export const VISIT_HISTORY = [
  { id: 'v1', date: '29 апр, Ср', time: '19:14', duration: '1ч 12м', kind: 'Самостоятельно' },
  { id: 'v2', date: '27 апр, Пн', time: '08:42', duration: '1ч 04м', kind: 'С Аней Соколовой', trainer: true },
  { id: 'v3', date: '24 апр, Пт', time: '20:01', duration: '0ч 48м', kind: 'Самостоятельно' },
  { id: 'v4', date: '22 апр, Ср', time: '08:30', duration: '1ч 10м', kind: 'С Аней Соколовой', trainer: true },
  { id: 'v5', date: '20 апр, Пн', time: '19:36', duration: '1ч 22м', kind: 'Самостоятельно' },
  { id: 'v6', date: '17 апр, Пт', time: '18:55', duration: '0ч 55м', kind: 'Самостоятельно' },
];

export const TRAINING_HISTORY = [
  { id: 'th1', date: '27 апр', trainer: 'Аня Соколова', initials: 'АС', color: '#f59e0b', bg: '#fef3c7', focus: 'Ноги + спина', notes: 'Хорошо потянули становую, добавили вес' },
  { id: 'th2', date: '22 апр', trainer: 'Аня Соколова', initials: 'АС', color: '#f59e0b', bg: '#fef3c7', focus: 'Грудь + руки', notes: 'Жим лёжа: 3×8 на 60 кг' },
  { id: 'th3', date: '15 апр', trainer: 'Лиза Орлова', initials: 'ЛО', color: '#a855f7', bg: '#f3e8ff', focus: 'Йога — раскрытие бёдер', notes: 'Пробовали голубя, нужно больше работы' },
  { id: 'th4', date: '8 апр', trainer: 'Аня Соколова', initials: 'АС', color: '#f59e0b', bg: '#fef3c7', focus: 'Функционал', notes: 'Круговая, 4 круга' },
];

// Purchases — money in / out
export const PURCHASE_HISTORY = [
  { id: 'p1', date: '28 апр', kind: 'sub', title: 'Продление абонемента', sub: 'Месячный · 30 дней', amount: 4900, status: 'ok', card: '•••• 4821' },
  { id: 'p2', date: '27 апр', kind: 'training', title: 'Персональная тренировка', sub: 'Аня Соколова · 27 апр, 08:30', amount: 2200, status: 'ok', card: '•••• 4821' },
  { id: 'p3', date: '22 апр', kind: 'training', title: 'Персональная тренировка', sub: 'Аня Соколова · 22 апр, 08:30', amount: 2200, status: 'ok', card: '•••• 4821' },
  { id: 'p4', date: '20 апр', kind: 'shop', title: 'Шейкер · бутылка 700 мл', sub: 'Магазин на ресепшене', amount: 690, status: 'ok', card: '•••• 4821' },
  { id: 'p5', date: '15 апр', kind: 'training', title: 'Йога — раскрытие бёдер', sub: 'Лиза Орлова · 15 апр, 19:00', amount: 2000, status: 'ok', card: '•••• 4821' },
  { id: 'p6', date: '10 апр', kind: 'training', title: 'Персональная тренировка', sub: 'Не пришёл · возврат 50%', amount: -1100, status: 'refund', card: '•••• 4821' },
  { id: 'p7', date: '28 мар', kind: 'sub', title: 'Продление абонемента', sub: 'Месячный · 30 дней', amount: 4900, status: 'ok', card: '•••• 4821' },
];

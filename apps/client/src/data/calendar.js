// Calendar — next 21 days from a fixed anchor date so the prototype is stable.

function buildCalendar() {
  const days = [];
  const now = new Date('2026-04-30T09:00:00');
  const dows = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
  for (let i = 0; i < 21; i++) {
    const d = new Date(now);
    d.setDate(now.getDate() + i);
    // Pseudo availability — most days have slots
    const hasSlot = i % 7 !== 6 && i !== 4;
    days.push({
      key: `d${i}`,
      date: d,
      dow: dows[d.getDay()],
      num: d.getDate(),
      month: d.getMonth(),
      isToday: i === 0,
      hasSlot,
    });
  }
  return days;
}

export const CALENDAR = buildCalendar();

export const TIME_SLOTS = ['08:00', '09:00', '10:00', '11:30', '13:00', '15:00', '16:30', '18:00', '19:00', '20:30'];

export const BUSY_SLOTS = {
  t1: ['09:00', '13:00', '18:00'],
  t2: ['10:00', '15:00', '19:00'],
  t3: ['08:00', '11:30', '20:30'],
  t4: ['16:30', '19:00'],
  t5: ['09:00', '13:00'],
  t6: ['11:30', '18:00', '20:30'],
};

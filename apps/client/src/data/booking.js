// Trainer-cancelled scenario — used when tweaks.gymEvent === 'trainer-cancelled'
export const TRAINER_CANCEL = {
  trainer: 'Аня Соколова',
  initials: 'АС',
  bg: '#fef3c7',
  color: '#f59e0b',
  date: 'Сегодня, 18:00',
  reason: 'заболела',
  reasonFull: 'Аня приболела и не сможет провести тренировку сегодня.',
  refund: 2200,
  systemMessage: {
    id: 'a-cancel',
    kind: 'cancel',
    body: 'Тренировка с Аней на сегодня в 18:00 отменена. Вернули 2 200 ₽ на карту •••• 4821. Извини!',
    time: 'Сейчас',
  },
};

// Upcoming booking shown on home + as an entry into manage flow
export const UPCOMING_BOOKING = {
  id: 'b-next',
  trainer: 'Аня Соколова',
  trainerShort: 'Аня',
  trainerInstr: 'Аней',
  trainerInitials: 'АС',
  trainerColor: '#f59e0b',
  trainerBg: '#fef3c7',
  date: 'Сегодня',
  dayNum: 30,
  month: 3, // апрель
  dow: 'Ср',
  time: '18:00',
  duration: 60,
  hoursTo: 9,         // hours until session — drives free-cancel UI
  focus: 'Ноги + спина',
  price: 2200,
};

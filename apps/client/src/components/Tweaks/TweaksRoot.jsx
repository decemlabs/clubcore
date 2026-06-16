// Tweaks panel content — wired to TweaksContext + UIContext.
// Mounted by App.jsx. Listens for host activate/deactivate via TweaksPanel.

import React, { useEffect, useState } from 'react';
import {
  TweaksPanel, TweakSection, TweakRow, TweakRadio, TweakSelect,
  TweakText, TweakButton,
} from './TweaksPanel.jsx';

import { useTweaksCtx } from '@/context/TweaksContext.jsx';
import { useUI } from '@/context/UIContext.jsx';
import { ACCENT_PRESETS } from '@/utils/accent.js';
import { triggerInstall, canInstall } from '@/services/pwa.js';
import { TRAINERS } from '@/data';

export function TweaksRoot() {
  const { t, setTweak } = useTweaksCtx();
  const ui = useUI();
  const [, force] = useState(0);

  useEffect(() => {
    const onInstallable = () => force((n) => n + 1);
    window.addEventListener('pwa:installable', onInstallable);
    return () => window.removeEventListener('pwa:installable', onInstallable);
  }, []);

  return (
    <TweaksPanel title="Tweaks">
      <TweakSection label="Тема" />
      <TweakRadio
        label="Оформление"
        value={t.theme}
        options={[
          { value: 'light', label: 'Светлая' },
          { value: 'dark',  label: 'Тёмная' },
        ]}
        onChange={(v) => setTweak('theme', v)}
      />
      <TweakRow label="Акцент">
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {Object.keys(ACCENT_PRESETS).map((c) => (
            <button
              key={c}
              onClick={() => setTweak('accent', c)}
              style={{
                width: 24, height: 24, borderRadius: 999, border: 0,
                background: c, cursor: 'pointer',
                outline: t.accent === c ? '2px solid #29261b' : '0.5px solid rgba(0,0,0,0.1)',
                outlineOffset: t.accent === c ? 2 : 0,
              }}
            />
          ))}
        </div>
      </TweakRow>

      <TweakSection label="Главный экран" />
      <TweakRadio
        label="Вариант"
        value={t.homeVariant}
        options={[
          { value: 'classic',  label: 'Карточки' },
          { value: 'qr-hero',  label: 'QR' },
          { value: 'minimal',  label: 'Min' },
        ]}
        onChange={(v) => setTweak('homeVariant', v)}
      />

      <TweakSection label="Состояние" />
      <TweakRadio
        label="Абонемент"
        value={t.subState}
        options={[
          { value: 'active',   label: 'Активен' },
          { value: 'expiring', label: 'Истекает' },
          { value: 'expired',  label: 'Истёк' },
        ]}
        onChange={(v) => setTweak('subState', v)}
      />
      <TweakRadio
        label="Данные"
        value={t.dataMode}
        options={[
          { value: 'normal', label: 'Заполнено' },
          { value: 'empty',  label: 'Пусто (новичок)' },
        ]}
        onChange={(v) => setTweak('dataMode', v)}
      />
      <TweakRadio
        label="Событие"
        value={t.gymEvent || 'none'}
        options={[
          { value: 'none',                label: 'Обычно' },
          { value: 'trainer-cancelled',   label: 'Тренер отменил' },
        ]}
        onChange={(v) => setTweak('gymEvent', v)}
      />
      <TweakRadio
        label="Карточка абонемента"
        value={t.subCardStyle || 'eyebrow'}
        options={[
          { value: 'eyebrow', label: 'Eyebrow' },
          { value: 'split',   label: 'Split' },
          { value: 'stripe',  label: 'Stripe' },
        ]}
        onChange={(v) => setTweak('subCardStyle', v)}
      />
      <TweakText
        label="Имя"
        value={t.userName}
        onChange={(v) => setTweak('userName', v)}
      />

      <TweakSection label="Push-нотификация" />
      <TweakSelect
        label="Тип"
        value={t.pushKind || 'idle'}
        options={[
          { value: 'idle',     label: 'Не показывать' },
          { value: 'message',  label: 'Сообщение от тренера' },
          { value: 'promo',    label: 'Промо · −15%' },
          { value: 'schedule', label: 'Изменение расписания' },
          { value: 'cancel',   label: 'Тренировка отменена' },
        ]}
        onChange={(v) => {
          setTweak('pushKind', v);
          if (v !== 'idle') ui.setPushKind(v);
          else ui.setPushKind(null);
        }}
      />
      <TweakButton
        label="Показать ещё раз"
        onClick={() => {
          const k = t.pushKind && t.pushKind !== 'idle' ? t.pushKind : 'message';
          ui.setPushKind(null);
          setTimeout(() => ui.setPushKind(k), 50);
        }}
      />

      <TweakSection label="Навигация" />
      <TweakButton label={ui.qrOpen ? 'Закрыть QR' : 'Открыть QR-пропуск'} onClick={() => ui.setQrOpen((o) => !o)} />
      <TweakButton label={ui.plansOpen ? 'Закрыть тарифы' : 'Открыть тарифы'} onClick={() => ui.setPlansOpen((o) => !o)} />
      <TweakButton label={ui.manageOpen ? 'Закрыть управление записью' : 'Управление записью'} onClick={() => ui.setManageOpen((o) => !o)} />
      <TweakButton label={ui.referralOpen ? 'Закрыть рефералку' : 'Приведи друга'} onClick={() => ui.setReferralOpen((o) => !o)} />
      <TweakButton label={ui.gymInfoOpen ? 'Закрыть «О зале»' : 'О зале — адрес, часы'} onClick={() => ui.setGymInfoOpen((o) => !o)} />
      <TweakButton label={ui.notifsOpen ? 'Закрыть уведомления' : 'Уведомления'} onClick={() => ui.setNotifsOpen((o) => !o)} />
      <TweakButton label="Детали тренера (Аня)" onClick={() => ui.setTrainerDetail(TRAINERS[0])} />
      <TweakButton
        label="Чекаут · тестовый платёж"
        onClick={() => ui.setCheckoutCtx({
          kind: 'training',
          title: 'Тренировка с Аней',
          subtitle: 'Завтра, 18:00 · 1 час',
          amount: 2200,
        })}
      />

      <TweakSection label="PWA" />
      <TweakButton
        label="Установить как приложение"
        onClick={async () => {
          if (canInstall()) {
            await triggerInstall();
          } else {
            alert('Установка доступна после загрузки страницы в браузере, который поддерживает PWA. В предпросмотре эта функция не активна — но manifest, icons и SW настроены.');
          }
        }}
      />
      <TweakButton label="Открыть оффлайн-страницу" onClick={() => window.open('/offline.html', '_blank')} />

      <TweakSection label="Сценарии · оплата" />
      <TweakSelect
        label="Исход оплаты"
        value={t.paymentOutcome || 'ok'}
        options={[
          { value: 'ok',         label: 'Успех' },
          { value: 'payment',    label: 'Ошибка платежа' },
          { value: 'slot-busy',  label: 'Слот уже занят' },
          { value: 'offline',    label: 'Нет связи' },
        ]}
        onChange={(v) => setTweak('paymentOutcome', v)}
      />
      <TweakButton
        label="Запись подтверждена"
        onClick={() => ui.setBookingConfirmedCtx({
          date: 'Среда, 30 апреля', time: '18:00',
          trainer: 'Аня Соколова', kind: 'Ноги + спина',
        })}
      />
      <TweakButton
        label="Чек / квитанция"
        onClick={() => ui.setReceiptCtx({
          ctx: { title: 'Годовой абонемент', subtitle: 'Подписка на 365 дней', kind: 'sub' },
          total: 42000,
        })}
      />
      <TweakButton
        label="Отмена записи (с возвратом)"
        onClick={() => ui.setCancelBookingOpen({
          date: 'Сегодня', time: '18:00',
          trainer: 'Аня Соколова', amount: 2200, hoursLeft: 5,
        })}
      />

      <TweakSection label="Сценарии · абонемент" />
      <TweakButton label="Заморозить" onClick={() => ui.setSubManageMode('freeze')} />
      <TweakButton label="Продлить"   onClick={() => ui.setSubManageMode('extend')} />
      <TweakButton label="Возврат"    onClick={() => ui.setSubManageMode('refund')} />

      <TweakSection label="Сценарии · аккаунт" />
      <TweakButton label="Способы оплаты"      onClick={() => ui.setPaymentMethodsOpen(true)} />
      <TweakButton label="Изменить телефон (SMS)" onClick={() => ui.setSmsVerifyCtx({ channel: 'phone', target: '+7 916 555-12-34' })} />
      <TweakButton label="Изменить email (код)"   onClick={() => ui.setSmsVerifyCtx({ channel: 'email', target: 'sasha@example.com' })} />
      <TweakButton label="Удалить аккаунт"     onClick={() => ui.setDeleteAccountOpen(true)} />

      <TweakSection label="Сценарии · тренеры" />
      <TweakButton label="Тренер отменил тренировку" onClick={() => ui.setTrainerCancelledOpen(true)} />
      <TweakButton
        label="Оценить тренировку"
        onClick={() => ui.setReviewCtx({
          date: '29 апр, Ср', trainer: 'Аня Соколова',
          kind: 'Ноги + спина', initials: 'АС',
          bg: '#fef3c7', color: '#a36a16',
        })}
      />
    </TweaksPanel>
  );
}

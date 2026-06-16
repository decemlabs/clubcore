/**
 * Reopen reset test for BookModal.
 *
 * Verifies that closing and reopening the modal restores all useState initial
 * values — the core correctness claim of plan 006.  BookModal is chosen because
 * it is a single exported component with plain props (no ModalsProvider needed)
 * and uses ChipGroup (aria-pressed) buttons that are directly assertable without
 * a visual browser.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BookModal } from './BookModal';

function setup(open: boolean, onOpenChange: (v: boolean) => void) {
  return render(<BookModal open={open} onOpenChange={onOpenChange} />);
}

describe('BookModal — reset on reopen', () => {
  it('Тип тренировки сбрасывается к «Персональная» после закрытия и повторного открытия', async () => {
    const user = userEvent.setup();

    let open = true;
    const { rerender } = setup(true, (v) => {
      open = v;
    });

    // Initial state: «Персональная» is pressed, «Групповая» is not.
    const personal = screen.getByRole('button', { name: 'Персональная' });
    const group = screen.getByRole('button', { name: 'Групповая' });

    expect(personal).toHaveAttribute('aria-pressed', 'true');
    expect(group).toHaveAttribute('aria-pressed', 'false');

    // User switches to «Групповая».
    await user.click(group);
    expect(group).toHaveAttribute('aria-pressed', 'true');
    expect(personal).toHaveAttribute('aria-pressed', 'false');

    // Close the modal (open → false).
    expect(open).toBe(true); // confirm the click didn't close it
    rerender(
      <BookModal
        open={false}
        onOpenChange={(v) => {
          open = v;
        }}
      />,
    );

    // Reopen (open → true).
    rerender(
      <BookModal
        open={true}
        onOpenChange={(v) => {
          open = v;
        }}
      />,
    );

    // The default must be restored: «Персональная» is pressed again.
    expect(screen.getByRole('button', { name: 'Персональная' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Групповая' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('Слот сбрасывается к «18:00» после закрытия и повторного открытия', async () => {
    const user = userEvent.setup();

    const { rerender } = render(<BookModal open={true} onOpenChange={() => {}} />);

    const slot18 = screen.getByRole('button', { name: '18:00' });
    const slot19 = screen.getByRole('button', { name: '19:00' });

    expect(slot18).toHaveAttribute('aria-pressed', 'true');

    await user.click(slot19);
    expect(slot19).toHaveAttribute('aria-pressed', 'true');
    expect(slot18).toHaveAttribute('aria-pressed', 'false');

    rerender(<BookModal open={false} onOpenChange={() => {}} />);
    rerender(<BookModal open={true} onOpenChange={() => {}} />);

    expect(screen.getByRole('button', { name: '18:00' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '19:00' })).toHaveAttribute('aria-pressed', 'false');
  });
});

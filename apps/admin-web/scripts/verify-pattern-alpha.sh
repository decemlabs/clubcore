#!/usr/bin/env bash
# Verify the Pattern α ESLint zone (Phase 22 D-22-12 / FE-11) fires correctly.
# Strategy: copy the fixture into src/features/clients/__test__/illegal.ts (which IS in
# the rule's `target` glob), run ESLint, assert the rule message appears + non-zero exit,
# then clean up.
set -e
cd "$(dirname "$0")/.."

SRC_FIXTURE="src/__fixtures/features/illegal-cross-feature-import.ts"
TMP_DIR="src/features/clients/__test__"
TMP_FILE="$TMP_DIR/illegal-pattern-alpha.ts"

mkdir -p "$TMP_DIR"
cp "$SRC_FIXTURE" "$TMP_FILE"

# Run ESLint — expect non-zero exit and the Pattern α message.
set +e
OUTPUT=$(pnpm exec eslint "$TMP_FILE" 2>&1)
STATUS=$?
set -e

rm -f "$TMP_FILE"
rmdir "$TMP_DIR" 2>/dev/null || true

if [ "$STATUS" -eq 0 ]; then
  echo "FAIL: ESLint did not error on Pattern α fixture (status=0)" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

if ! echo "$OUTPUT" | grep -q "Pattern α"; then
  echo "FAIL: ESLint error did not match 'Pattern α' message" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

echo "PASS: Pattern α ESLint zone fires correctly"

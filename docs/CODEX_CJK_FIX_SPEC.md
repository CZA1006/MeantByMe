# Codex Spec — CJK (Chinese) tokenization fix in `core/`

Fix the P1 Chinese defect recorded in [STATUS.md](STATUS.md) → "🔴 P1 — Chinese (CJK) tokenization gap".
Work on `nick/runtime` (branch off `develop` @ `6600b08`). **Do not push**; leave local commits for review.

**Read first:** `docs/STATUS.md` (measured evidence), `DECISIONS.md` (D1–D17), `AGENTS.md`.

## Why (measured 2026-07-24)
`tokenize()` matches `\b[\w']+\b`, and CJK characters are `\w`, so
`tokenize("我不想明天出门。")` returns the single token `['我不想明天出门']`. Consequences:

| Behaviour | English | Chinese |
|---|---|---|
| `tokenize("我不想明天出门。")` | — | `['我不想明天出门']` (single token) |
| `core_slots_present(...)` | `True` | **`False`** → never reaches LOW band, always an extra clarification round |
| locked-token subset check | passes | **fails** (`{'明天'} ⊄ {'我不想明天出门'}`) |
| memory token-overlap similarity | works | **empty intersection** → `similarity_band` never `high` |

**Impact:** after `CONFIRM_HEARD_CONTENT` locks fragments,
`GatewayIntentAdapter._validate_contract` rejects otherwise-valid Chinese
candidates as "dropped confirmed tokens" and the session **silently degrades to
template fallback**. Memory reranking and the D11 band downgrade never fire for
Chinese. The LLM (`step-explore`) handles Chinese correctly — the defect is
entirely in the deterministic core.

## 1. Language-aware tokenization — `core/personalization/text.py`
Change `tokenize()` so CJK runs split into **individual characters** while
non-CJK text keeps whole words. Keep `normalize()` **unchanged** (it already
preserves CJK and strips punctuation) so `expression_hash` / `idempotency_key` /
exact-match ranking stay byte-for-byte identical.

```python
_CJK_RANGES = ("㐀-䶿", "一-鿿", "豈-﫿")

def _is_cjk(char: str) -> bool: ...

def tokenize(text: str) -> list[str]:
    # split each word-run: CJK chars become one token each, latin runs stay words
```

Mixed input must work: `tokenize("我想去 hospital")` → `['我','想','去','hospital']`.
**English tokenization must be identical to today — hard requirement.**

## 2. Locked-token checks must tokenize BOTH sides
`GatewayIntentAdapter._validate_contract` (`src/meantbyme/adapters/intent/gateway.py`)
builds `{normalize(t) for t in locked_tokens}` and compares against
`set(tokenize(candidate.text))` — mismatched granularity. Build the locked set
with `tokenize()` as well (union of `tokenize(t)` per locked token), then
subset-check. Apply the **same fix** to `adapters/intent/template.py::_assert_locked`
and `adapters/intent/mock.py::_assert_confirmed_context` (same bug pattern).

## 3. CJK core-slot detection — `core/policies/uncertainty.py`
`PREDICATES` / `TIME_WORDS` / `FUNCTION_WORDS` are English word sets and cannot
match per-character CJK tokens. Make `core_slots_present()` language-aware:

- **Latin input** → keep the existing token-set logic unchanged.
- **CJK input** → substring containment against CJK word lists on the normalized
  text, e.g. predicates `{想, 要, 去, 来, 做, 吃, 喝, 停, 换, 见, 打, 付, 签, 需要, 帮, 走, 回}`
  and time words `{今天, 明天, 后天, 昨天, 早上, 中午, 下午, 晚上, 周一…周日, 星期一…星期日}`.
  Keep the same semantic rule: predicate **and** (time **or** another content token).

`assess_uncertainty()` band logic (D10) otherwise unchanged.

## 4. Record the decision
Add **D18 — Language-aware tokenization (CJK)** to `DECISIONS.md`: what changed,
why (the measured defect above), the invariant that English behaviour is
unchanged and `normalize()`/`expression_hash` are untouched, and that ranking/
band semantics for CJK now match their English equivalents. Add a change-record
row and update the summary table.

## 5. Tests (both languages)
Cover, for **English (no regression)** and **Chinese (now correct)**:
- `tokenize` output shape, including mixed CJK + latin;
- `core_slots_present` / `assess_uncertainty` band for a complete vs fragmented Chinese utterance;
- locked-token subset check **accepts** a valid Chinese candidate preserving the locked fragment and still **rejects** one that drops it;
- memory token-overlap similarity reaches `high` for a matching Chinese memory (via `search_verified_memories`);
- `expression_hash` for an existing English string is **unchanged** (guards the idempotency key).

Also check whether the ZH samples in `demo/eval/dataset.jsonl` still need the
spaced-token workaround — de-hack that fixture if the fix makes it unnecessary.

## 6. Acceptance
- All existing tests stay green (52 + new); `core/` AST isolation green.
- `core/` diff limited to `personalization/text.py` and `policies/uncertainty.py` (adapter fixes are outside core).
- Mock eval still passes hard gates:
  `./.venv/bin/python -m meantbyme.eval --dataset demo/eval/dataset.jsonl --mode mock --report artifacts/eval_report.json`
- No secrets; no real StepFun calls in automated tests.

**Report back:** files changed, before/after `tokenize` examples for EN + ZH,
confirmation English behaviour and `expression_hash` are unchanged, and the mock
eval aggregate.

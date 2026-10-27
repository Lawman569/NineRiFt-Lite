# NineRiFt-Lite — Release-Readiness Report (2026-10-27)

## Scope of review

Five prepared PRs against `master` (all author-owned branches; **none merged**):

| PR | Branch | Fix | Tests |
|----|--------|-----|-------|
| #1 | `fix/selfile-filter-logic` | always-true `or 'max'` clobbering firmware filters | 7-case matrix (in-repo) |
| #2 | `fix/string-comparisons` | 22 identity comparisons → equality checks | 12 |
| #3 | `fix/flash-progress-bar` | `progress`/`maxprog` → `NumericProperty`; dead `setprogbar` removed | 4 |
| #4 | `fix/fwget-duplicate-download` | duplicate download removed; `getboth` reset (determinism) | 6 |
| #5 | `fix/loadrepo-unsafe-eval` | `eval()` → strict `json.loads` + structure validation (RCE closed) | 5 |

## Correctness & security verdict

- #1–#4: behavior-only fixes, all RED-verified then GREEN.
- #5: security-critical. `loadRepo()` previously `eval()`-ed downloaded **and**
  cached repo JSON (RCE). Fix parses with `json.loads` and validates document
  shape (`repo → infos{name, dirname, files_URL}, files{DRV, BMS, BLE}`) **before
  any state mutation**. AST lint enforces no `eval`/`exec` in `fwget.py`.
- Conflict between #1 and #2 (same `main.py:139` line) is resolved at the PR
  level: `fix/string-comparisons` now contains #1 plus the equality form.
  All five report `MERGEABLE / CLEAN` on GitHub.

## Test evidence

- Integrated tree (`integration/test-fixes`, all five branches merged in
  recommended order 1→2→3→4→5): **27/27 repo tests + 7-case selfile matrix**
  pass; `python3 -m py_compile` clean on every module.
- On PR #2's branch: 12/12 unit tests redone after the conflict-resolution
  merge commit; the AST lint suite caught a resolution mistake on
  `main.py:139` before any PR merge (self-proof the guardrails work).
- Final combined diff audited hunk-by-hunk: only the four app modules and
  seven new test files change; no accidental work included.

## Tests requiring environments NOT available in this Termux session

1. **Kivy/apk (on-device UI/property emission)** — all suites are stdlib-only
   AST extraction because Kivy can't be imported under Termux. Validation of
   actual KV bindings firing (PR #3) requires building the APK
   (Buildozer/Linux CI) and a device smoke test.
2. **BLE/UART link validation** — real connections (nbclient `connect()`,
   flashing transport) are out of scope for the suite; `mocklink.py` provides
   an in-process substitute for the happy path. Real radios must be exercised
   manually (CUBOT X100 + Termux USB passthrough).
3. **Windows-specific** — nothing in the suite needs Windows, but the
   Play-Store release path historically relies on Windows-side signing;
   verify separately.
4. **Firmware downloads against the real repo** — tests use monkeypatched
   `requests`; live `files.scooterhacking.org` responses should be spot-checked
   manually before release (never flash real firmware without a review of the
   target file itself).

## Residual risks / known debt

- `loadRepo()` writes/downloads via plaintext eval of md5 (now via json, but
  there is no signature/trust chain on repo JSON — see note; a hostile cache
  file can still poison version lists without executing code).
- `loadRepo()` hash/eval-less now, but fetches are not verified by
  `requests` to HTTPS; consider upgrading the production repo URL to HTTPS.
- `fwget.getFile()` fetches both `.md5` and content every call even when
  cache hits (dedup could be tightened opportunistically).
- `nbclient` connect/disconnect state machine is only partially covered by
  semantic analysis; BLE teardown edge cases untouched.

## Merge-order recommendation (verified locally, conflict-free)

`#1 → #2 → #3 → #4 → #5` — after each merge GitHub should report the next PR
`MERGEABLE/CLEAN` because #2's head already carries #1.

## Gate: what is NOT done (needs explicit approval)

- Merge any PR, delete branches, publish release artifacts, flash hardware.

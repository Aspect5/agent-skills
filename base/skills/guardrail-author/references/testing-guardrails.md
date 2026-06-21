# Testing guardrails — prove-it-fires AND prove-no-false-block

A guardrail with no test is a hope, and a guardrail tested only on the bad case is
half a hope — it might block *everything*. Every guardrail this skill ships gets
**two** tests, and both must pass before it is claimed working. These are the
deterministic part of the system, so they are *tests*, not evals: the block/allow
boundary has a single correct answer, so you assert on it exactly.

> Only load this file when writing the tests. The two tests map directly to
> `base:tested-fires` and `base:no-false-block`; fixtures map to
> `base:synthetic-fixtures`.

## The two-test contract

For surface S with a check `C`:

1. **fires-on-bad (`base:tested-fires`)** — feed `C` the realistic bad input for S;
   assert `C` **blocks** (non-zero exit, and ideally the expected reason on stderr).
2. **passes-on-good (`base:no-false-block`)** — feed `C` *each* legitimate neighbor
   named in the spec (the false-block set from `guardrail-catalog.md`); assert `C`
   **allows** (exit 0) for every one.

A third, cheap, high-value test for any non-trivial check:

3. **fails-closed (`base:fail-closed`)** — feed `C` a malformed / unreadable input
   (a path that doesn't exist, garbage on stdin, a truncated command) and assert it
   **blocks**, not allows. This is the test that catches an allow-on-error bug — the
   exact failure mode that silently neuters a guardrail.

## Fixture discipline (`base:synthetic-fixtures`) — never test with a real danger

The test must not itself become the danger surface:

- **Secrets:** use synthetic strings that match the *shape* but are fake and
  known-non-live. **Critical subtlety:** a good secret check (this one included)
  deliberately ALLOWS strings carrying a placeholder marker — `EXAMPLE`,
  `your-key-here`, `FAKE`, `TEST` — because that is exactly how it satisfies
  `base:no-false-block` on `.env.example` files. So the two tests need *different*
  fixtures:
  - **fires-on-bad fixture** — shape-valid, high-entropy, and **free of any
    placeholder marker**, or the check will (correctly) allow it and the fires test
    will fail. Use a random body: AWS-shaped `AKIA` + 16 random uppercase alnum
    (e.g. `AKIA2E0ACFH3KN5TFIMZ`); GitHub-shaped `ghp_` + a 36-char random body.
  - **passes-on-good fixture** — the placeholder forms: `AKIAIOSFODNN7EXAMPLE`
    (AWS's documented dummy), `API_KEY=your-key-here`, `sk-THIS_IS_A_FAKE_TEST_KEY`,
    or a truncated `-----BEGIN PRIVATE KEY-----\nNOTAREALKEY\n-----END…`. These
    SHOULD be allowed — that is the no-false-block guarantee.
  Put the fires fixture in a file or heredoc and point the check at it *as if it were
  staged content*; adding the fixture path to the check's own allowlist is **wrong**
  (it would defeat the fires test).
- **Protected-branch / push:** create a **throwaway local repo** in a temp dir, add a
  fake `origin`, create a `main`, and test the check against a `git push --force
  origin main` *command string* — never run the push against a real remote. The
  check parses the command; it does not need a live push to fire.
- **Destructive command:** test the check against the command **string**
  (`"rm -rf /"`, `"rm -rf ./build"`); never let the test actually execute it. If a
  test must exercise real `rm`, confine it to a path inside a `tempfile`-created
  directory and assert on the check's verdict, not on filesystem effects.

## Recipe per harness — how to invoke the check in a test

The check is a plain script with a stable exit-code contract, so tests are simple
process assertions in any language. Two portable shapes:

### Python (pytest-style)

```python
import subprocess, sys
from pathlib import Path

CHECK = Path(__file__).resolve().parents[1] / ".agents/guardrails/guardrail_check.py"

def run(mode, *args, stdin=None):
    return subprocess.run(
        [sys.executable, str(CHECK), "--mode", mode, *args],
        input=stdin, text=True, capture_output=True,
    )

def test_secret_fires(tmp_path):
    f = tmp_path / "leak.txt"
    f.write_text("aws_secret = AKIA2E0ACFH3KN5TFIMZ\n")   # shape-valid, no placeholder marker
    r = run("secret", "--path", str(f))
    assert r.returncode != 0            # base:tested-fires
    assert "redacted" in r.stderr.lower() or "secret" in r.stderr.lower()

def test_secret_allows_example_placeholder(tmp_path):
    f = tmp_path / ".env.example"
    f.write_text("API_KEY=your-key-here\n")
    r = run("secret", "--path", str(f))
    assert r.returncode == 0            # base:no-false-block

def test_secret_fails_closed_on_missing_file():
    r = run("secret", "--path", "/no/such/file")
    assert r.returncode != 0            # base:fail-closed
```

### Shell (framework-agnostic)

```sh
#!/bin/sh
root="$(git rev-parse --show-toplevel)"
check="$root/.agents/guardrails/guardrail_check.py"

# fires-on-bad  (shape-valid, NO placeholder marker — see Fixture discipline above)
printf 'AKIA2E0ACFH3KN5TFIMZ\n' | python3 "$check" --mode secret --stdin
test $? -ne 0 || { echo "FAIL: secret check did not fire"; exit 1; }

# passes-on-good
printf 'API_KEY=your-key-here\n' | python3 "$check" --mode secret --stdin --name .env.example
test $? -eq 0 || { echo "FAIL: secret check false-blocked a placeholder"; exit 1; }

echo "PASS"
```

Note the **direct exit-code check** (`$?`, `test … -ne 0`) — never `| tail`/`| head`,
which masks the very exit code under test (the same trap that would silently break
the guardrail in production).

## Where the tests live

Place the guardrail tests where the project's tests already live and run, mirroring
an existing test's framework and runner (so they run in the same CI job that runs
everything else). Register them in the project's suite per its convention — a test
that exists but never runs proves nothing. Resolve the test command via Step 0
precedence and run both tests; **capture the literal pass lines** for the self-check
(report results, never assert them).

## The boundary test is the durable one

The fires-on-bad test proves the guardrail works *today*. The passes-on-good test is
what keeps it working *tomorrow*: it pins the block/allow boundary so a future
"tighten the regex" change that starts catching `.env.example` fails CI instead of
silently making the guardrail hated and then deleted. When you add a pattern to a
check, add a passes-on-good case for the nearest legitimate neighbor in the same PR.

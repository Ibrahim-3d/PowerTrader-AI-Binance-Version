# Development Learnings
Captured from Phase 1 security implementation session.

---

## GitHub Fork Contributor Workflow

When invited to a repo but not added as collaborator with push access:

```bash
# Fork via API
gh api -X POST repos/{owner}/{repo}/forks

# Add fork as separate remote
git remote add fork https://github.com/{your-account}/{repo}.git

# Push feature branch to fork
git push fork feat/your-branch

# Create PR from fork to upstream
gh pr create --repo {owner}/{repo} --head "{your-account}:feat/your-branch" --base main
```

- `origin` = upstream owner repo (read-only for you)
- `fork` = your fork (push target)
- PRs go from `your-account:branch` into `owner:main`

---

## CI Workflows on Fork PRs

GitHub blocks workflow runs from first-time fork contributors until owner approves. Status shows as `action_required`. Cannot bypass this.

**What to do instead:** Run all CI steps locally before submitting PR. When owner approves, everything passes first try.

```bash
# Simulate Code Quality workflow locally
black --check app/new_file.py          # formatting
flake8 app/new_file.py \
  --max-line-length=100 \
  --select=E9,F63,F7,F82             # hard errors only (block CI)
flake8 app/new_file.py \
  --max-line-length=100 \
  --exit-zero                         # soft warnings (won't block)
python -m pytest app/test_new_file.py -q
```

Flake8 severity:
- `E9, F63, F7, F82` = hard errors, always block CI
- `F401` (unused import), `F841` (unused var) = soft warnings, `--exit-zero` so they don't block
- Still clean them up - sets a quality standard

Run Black **per branch** not whole codebase. Each branch only touches specific new files.

---

## PR Review Comment API Workflow

### Get inline Copilot comment IDs
```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments \
  --jq '.[] | select(.in_reply_to_id == null) | {id, url: .html_url, body: .body[:80]}'
```

### Reply to a specific inline thread
```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies \
  -X POST -f body="Your reply here"
```

### Resolve a thread (GraphQL - needs write access or PR author)
```bash
gh api graphql -f query='
mutation {
  resolveReviewThread(input: {threadId: "PRRT_kwDO..."}) {
    thread { isResolved }
  }
}'
```

### Get thread IDs (for resolveReviewThread mutation)
```bash
gh api graphql -f query='
{
  repository(owner: "...", name: "...") {
    pullRequest(number: N) {
      reviewThreads(first: 20) {
        nodes {
          id
          isResolved
          comments(first: 1) { nodes { databaseId body } }
        }
      }
    }
  }
}'
```

### Two different comment types, two different endpoints

| Type | Endpoint |
|------|----------|
| PR conversation (issue-level) | `/repos/{owner}/{repo}/issues/{pr}/comments` |
| Inline review comment | `/repos/{owner}/{repo}/pulls/{pr}/comments` |
| Update issue-level comment | `PATCH /repos/{owner}/{repo}/issues/comments/{id}` |
| Update inline review comment | `PATCH /repos/{owner}/{repo}/pulls/comments/{id}` |

---

## GitHub Anchor Links in PR Comments

`#discussion_r{id}` anchors **only work when the thread is expanded** (not resolved/collapsed). Clicking a link to a resolved thread scrolls to the top of the page because the element is hidden in the DOM.

**Do not use:** `[r3255439908](https://github.com/.../pull/80#discussion_r3255439908)`

**Do use:** Plain numbered list `#1`, `#2` with a note directing owner to Files Changed tab:
```markdown
> **Note:** Threads resolved and collapsed. Open **Files changed** tab,
> click **"Show resolved"** to view individual threads.

| # | File | Topic | Status |
|---|------|-------|--------|
| 1 | `pt_credentials.py` | Topic description | Resolved |
```

---

## Responding to Copilot/Reviewer Comments

Better than one big summary comment: reply **inline on each thread** directly. Owner reads justification next to the code line.

Good reply structure:
1. Why the original code was written that way (design intent)
2. What was wrong with it (the actual issue)
3. What was changed and why (justify fix, not just describe it)
4. Open question or trade-off if relevant (opens discussion)

Avoid em dashes `—` in GitHub markdown comments. Use hyphen-minus `-` instead. Em dashes can cause unexpected rendering in some GitHub clients.

---

## Fact-Checking Code Claims Before Stating Them

Before saying "fixed X", verify on the actual branch:

```bash
git checkout feat/your-branch

# Check import is actually removed
python -c "
with open('app/file.py') as f: src = f.read()
print('thing_in_question' in src)
"

# Check function exists
grep -n "def function_name" app/file.py

# Check usage (not just import line)
python -c "
with open('app/file.py') as f: src = f.read()
body = '\n'.join(l for l in src.split('\n') if 'from typing' not in l)
print('NameToCheck' in body)
"
```

Run tests after every claim to confirm behavior unchanged.

---

## Atomic File Writes (Cross-Platform)

Standard pattern for preventing partial-write corruption:

```python
tmp = filepath + ".tmp"
try:
    with open(tmp, "wb") as f:
        f.write(content)
    os.replace(tmp, filepath)  # atomic on all platforms
except Exception:
    try:
        os.remove(tmp)
    except OSError:
        pass
    raise
```

`os.replace()` is atomic on POSIX. On Windows it's best-effort but still safer than direct write. Critical for credential files where partial writes leave key/secret mismatched.

---

## Credential Rotation - All Files Must Move Together

When rotating credentials, backup and restore ALL related files atomically:

```python
# Wrong - rollback only restores key+secret
backup(key_file)
backup(secret_file)
# metadata gets updated inside encrypt_credentials()
# on failure, metadata now says "rotated" but key/secret are old

# Correct - snapshot everything first
backup(key_file)
backup(secret_file)
backup(metadata_file)  # critical - keeps rotation timestamp consistent
```

If rotation fails, all three must be restored together. Metadata timestamp inconsistency causes false "rotation not due" readings even when old credentials are in use.

---

## SQLite Thread Safety

`PRAGMA journal_mode=WAL` requires a brief exclusive write lock. If two threads both call it simultaneously on the same DB file, one gets `SQLITE_LOCKED`. Fix: serialize connection creation with a lock.

```python
def _create_connection(self):
    with self._create_lock:  # serialize so only one thread sets WAL at a time
        conn = sqlite3.connect(self.db_path, ...)
        self._apply_pragmas(conn)
        return conn
```

`BEGIN IMMEDIATE` for write transactions prevents SQLITE_BUSY at transaction start rather than mid-write. Retry with exponential backoff handles contention.

SQLite uses file-level locking. "Deadlock" is a misnomer - true deadlocks cannot occur. The actual issue is write contention (SQLITE_BUSY/SQLITE_LOCKED).

---

## Thread-Safe Singleton Initialization (Double-Checked Locking)

```python
class Singleton:
    _instance = None
    _class_lock = threading.Lock()   # guards singleton creation
    _init_lock = threading.Lock()    # guards lazy init (separate!)

    def __new__(cls):
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialised = False
            return cls._instance

    def _ensure_init(self):
        if self._initialised:          # fast path - no lock
            return
        with self._init_lock:
            if self._initialised:      # re-check after lock acquired
                return
            # ... do init ...
            self._initialised = True
```

Two separate locks needed: `_class_lock` guards the singleton reference itself, `_init_lock` guards the initialisation. Using one lock for both causes deadlock when `_ensure_init` is called from methods that themselves run under `_class_lock`.

---

## Removing Imports Safely

Before removing an import, verify:
1. Not used in any non-import line
2. Was not added by you and intended for future use
3. Check body only (exclude import lines themselves)

```python
with open('app/file.py') as f:
    src = f.read()
body = '\n'.join(l for l in src.split('\n')
                 if not l.strip().startswith(('from ', 'import ', '#')))
print('NameToRemove' in body)  # must be False before removing
```

Common false positives: name appears in docstrings, comments, or string literals. The check above excludes comment lines but not inline string uses - do a final manual scan.

---

## Testing Patterns Learned

### Timing-sensitive tests
Avoid asserting exact elapsed time or computed values that depend on `time.time()` called at different moments. Use ranges or relative assertions.

```python
# Fragile
self.assertIn("3 day", warning)

# Robust
self.assertIn("day", warning)
```

### Thread isolation in registry/singleton tests
Always `setUp`/`tearDown` clearing shared state:

```python
def setUp(self):
    registry.clear()  # or SomeClass.reset_singleton()

def tearDown(self):
    registry.clear()
```

Without this, tests become order-dependent and hide regressions.

### Windows file cleanup
```python
def tearDown(self):
    pool.close_thread_connection()  # close SQLite handles FIRST
    shutil.rmtree(self.tmpdir, ignore_errors=True)
```

SQLite on Windows holds file locks until connection is explicitly closed. `ignore_errors=True` masks this - close connections before cleanup.

### Concurrent test reliability
Use `threading.Barrier` to ensure threads are genuinely concurrent, not sequential:

```python
barrier = threading.Barrier(2, timeout=5)
def worker():
    barrier.wait()  # both threads reach here before either proceeds
    do_concurrent_work()
```

---

## Code Review Response Quality

**Weak:** "Fixed - moved import to module level"

**Strong:** "Original design kept `shutil` local because it's only used in the failure path of one method - keeping the import at point of use makes the dependency visible. Convention in this codebase is module-level imports, and the minor overhead of a local import isn't justified here. Moved to module level."

Structure: original intent -> what was wrong or suboptimal -> what changed -> open question if trade-off exists.

This opens productive discussion rather than just logging what changed.

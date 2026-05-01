# Instructions for Gemini — Push This Folder to GitHub

**Copy everything below the line into Gemini. That's the entire prompt.**

---

You are operating on a folder named `Azalyst Propfirm/` on the user's local machine. Your job is to publish it as a GitHub repository with two automated workflows running.

## Context

- This folder is a self-contained Python trading system + static dashboard.
- It is NOT yet a git repository. You will initialize one.
- It contains pre-written GitHub Actions workflows in `.github/workflows/`:
  - `scan.yml` — runs every hour on cron, executes the scanner, commits results to `data/`.
  - `pages.yml` — deploys the static dashboard to GitHub Pages on every push.
- The user has the GitHub CLI (`gh`) authenticated and `git` installed.

## Goal

Push the folder as a new GitHub repo, configure two settings in the GitHub UI, and trigger the first scan. After that, the system runs autonomously.

## Steps — do these in order

### 1. Initialize the git repository

```bash
cd "Azalyst Propfirm"
git init
git branch -M main
git add .
git status
```

Show the user the `git status` output and confirm the file count matches expectations (~25–30 files including the `.github/workflows/` directory). Do NOT commit yet — wait for the user to confirm the staged file list looks right.

### 2. Make the initial commit

```bash
git commit -m "Initial commit: Azalyst Propfirm scanner + dashboard + workflows"
```

### 3. Create the GitHub repo and push

The user wants a **PUBLIC** repository (so GitHub Actions minutes are unlimited and the dashboard is reachable on Pages).

Ask the user only for the **repo name** (suggest: `azalyst-propfirm`).

Then run:

```bash
gh repo create <repo-name> --public --source=. --push
```

If `gh repo create` fails, fall back to:

```bash
gh repo create <username>/<repo-name> --public
git remote add origin https://github.com/<username>/<repo-name>.git
git push -u origin main
```

Capture and show the user the resulting repo URL (e.g. `https://github.com/<user>/azalyst-propfirm`).

### 4. Configure repo settings via the GitHub API

Two settings must be changed before the workflows can run correctly. Use `gh api` so the user doesn't have to click around:

#### 4a. Allow workflows to write to the repo
The hourly scanner needs to commit `data/*.json` back. Without this, the commit step in `scan.yml` will fail with a 403.

```bash
gh api -X PUT repos/<owner>/<repo>/actions/permissions/workflow \
  -f default_workflow_permissions=write \
  -f can_approve_pull_request_reviews=false
```

#### 4b. Enable GitHub Pages with "GitHub Actions" as the source
This lets `pages.yml` actually publish.

```bash
gh api -X POST repos/<owner>/<repo>/pages \
  -f "build_type=workflow" \
  -f "source[branch]=main" \
  -f "source[path]=/" \
  || gh api -X PUT repos/<owner>/<repo>/pages \
       -f "build_type=workflow"
```

(The first call creates the Pages site; the fallback PUT updates an existing one. One of the two will succeed.)

#### 4c. Add the Discord webhook secret

Ask the user to paste their Discord webhook URL. It will look like:

```
https://discord.com/api/webhooks/1234567890/aBcDeFgHiJkLmNoPqRsTuVwXyZ...
```

If the user **does not have one yet**, instruct them:
> 1. Open Discord → pick a channel → click the gear icon (Edit Channel)
> 2. Integrations → Webhooks → New Webhook
> 3. Copy the Webhook URL and paste it back to me.

Once you have the URL, store it as a repo secret named **`DISCORD_WEBHOOK_URL`**:

```bash
gh secret set DISCORD_WEBHOOK_URL --body "<paste-url-here>" --repo <owner>/<repo>
```

#### 4d. Add the Discord user-ID secret (ping ON NEW SIGNALS ONLY)

The user wants to be **@-mentioned only when a new trade signal is detected**, NOT on routine hourly updates, closed trades, or breach status. The scanner already implements this: the @-ping is conditional on the `NEW SIGNALS THIS SCAN` section being non-empty.

The user's Discord user-snowflake ID is:

```
63959528194052118
```

Store it as a repo secret named **`DISCORD_USER_ID`**:

```bash
gh secret set DISCORD_USER_ID --body "63959528194052118" --repo <owner>/<repo>
```

Verify both secrets landed:

```bash
gh secret list --repo <owner>/<repo>
```

You should see both `DISCORD_WEBHOOK_URL` and `DISCORD_USER_ID` in the list.

If the user opts out of Discord entirely, skip 4c and 4d — the workflow checks for `DISCORD_WEBHOOK_URL` and silently no-ops if it's missing.

### 5. Trigger the first scan manually

Workflows on a fresh repo don't fire on the first push (cron only). Kick the first scan by hand:

```bash
gh workflow run "Scan markets (hourly)" --ref main
```

Wait ~10 seconds, then poll status:

```bash
gh run list --workflow="Scan markets (hourly)" --limit 1
```

Show the user the run ID and link them to the live log:

```bash
gh run watch
```

The first scan takes 4–6 minutes (77 symbols). When it completes, it will commit `data/scan_results.json`, `data/paper_trader_state.json`, and `data/scan_history.json` back to the repo. That commit triggers the `pages.yml` workflow automatically, which publishes the dashboard.

### 6. Report the dashboard URL

Once both workflows complete green, the dashboard is live at:

```
https://<username>.github.io/<repo-name>/
```

Print that URL to the user as the final output.

## Verification checklist (run at the end and report each as PASS/FAIL)

- [ ] `git remote get-url origin` returns the GitHub URL
- [ ] `gh repo view --json visibility -q '.visibility'` returns `"PUBLIC"`
- [ ] `gh api repos/<owner>/<repo>/actions/permissions/workflow -q '.default_workflow_permissions'` returns `"write"`
- [ ] `gh api repos/<owner>/<repo>/pages -q '.build_type'` returns `"workflow"`
- [ ] `gh secret list --repo <owner>/<repo>` includes BOTH `DISCORD_WEBHOOK_URL` and `DISCORD_USER_ID` (skip if user opted out of Discord)
- [ ] `gh run list --limit 2` shows two completed runs (one Scan, one Deploy)
- [ ] `curl -sI https://<username>.github.io/<repo-name>/` returns `HTTP/2 200`
- [ ] (If Discord configured) the user confirms a message arrived in their Discord channel

## Things to NOT do

- Do NOT modify any file inside `Azalyst Propfirm/` — it's already configured.
- Do NOT use `--force` on any git command.
- Do NOT amend the initial commit — make new commits if changes are needed.
- Do NOT commit anything inside `__pycache__/` or `scanner.log` — `.gitignore` handles this.
- Do NOT skip step 4 — without write permissions and Pages enabled, the workflows fail silently.

## If something fails

- **403 on `git push`**: the user's GitHub auth is missing or expired. Run `gh auth login` and retry.
- **`gh repo create` says "name already exists"**: ask the user for a different name.
- **`pages.yml` fails with "Pages must be enabled"**: re-run step 4b.
- **`scan.yml` fails on the commit step**: re-run step 4a, then re-trigger via `gh workflow run`.
- **Dashboard shows "Loading…" forever**: the first scan hasn't committed yet. Wait for the second workflow run to publish.

End by giving the user the live dashboard URL and a one-line summary of what's now running.

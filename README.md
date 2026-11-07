# Maseno First-Year Guide (PythonAnywhere edition)

Flask + SQLite app for new Maseno University students: documents, campus map, events, WhatsApp groups, hotels, revision papers, freshers' checklist, and an admin desk.

## What is different in this edition
- **No secrets in the code.** Keys and passwords live in a private `.env` file that is never uploaded or shared.
- **Safe forms.** Every form has a CSRF token, cookies are HttpOnly, SameSite and (in production) Secure, and the login redirect can't be abused.
- **Email verification actually works.** Students must verify before logging in, can ask for a new link, and a slow or broken mail server can no longer crash or freeze registration. If you leave the email settings empty, verification is skipped so nobody gets locked out.
- **Safe first run.** The admin password comes from `.env`; if you forget, a random one is created and printed once in the error log. The app also creates its own secret key.
- **Friendly error pages** (404, 403, file too large, expired form) instead of raw errors.
- **Flat folder.** The zip contains one `maseno-guide` folder, so there's no more nesting.

## Deploy on PythonAnywhere
Replace `mitchellsidhs` with your username everywhere if different.

### 1. Upload and unzip
1. **Files** tab: upload `maseno-guide-pythonanywhere.zip` to `/home/mitchellsidhs`.
2. Open a **Bash** console and run:
```bash
cd ~
mv maseno-guide maseno-guide-old     # keep the old copy for now (skip if you have none)
unzip maseno-guide-pythonanywhere.zip
cd maseno-guide
ls
```
`ls` must show `app.py`, `config.py`, `requirements.txt`, `templates`, `static`.

### 2. Install packages
```bash
workon maseno-env
pip install -r requirements.txt
```
(Create it first if needed: `mkvirtualenv --python=/usr/bin/python3.10 maseno-env`.)

### 3. Create your private .env file
```bash
cp .env.example .env
nano .env
```
Fill in `ADMIN_PASSWORD`, `GEOAPIFY_API_KEY`, and the email lines (`MAIL_USERNAME`, `MAIL_PASSWORD` as a Gmail **App Password**, `MAIL_DEFAULT_SENDER`). Leave `PRODUCTION=1`. Save with Ctrl+O, Enter, Ctrl+X.
(You can also edit it in the **Files** tab. Hidden files show when you tick "Show hidden files".)

### 4. Web tab settings
- **Source code:** `/home/mitchellsidhs/maseno-guide`
- **Working directory:** `/home/mitchellsidhs/maseno-guide`
- **Virtualenv:** `/home/mitchellsidhs/.virtualenvs/maseno-env`
- **WSGI file:** open it, delete everything, paste the contents of `pythonanywhere_wsgi.py` and change `YOURUSERNAME` to `mitchellsidhs`.
- **Static files:** add one row. URL `/static/`, Directory `/home/mitchellsidhs/maseno-guide/static`
  **Do not** add `uploads` or `papers` here, they hold private student documents.

### 5. Reload and check
1. Click the green **Reload** button, then open `https://mitchellsidhs.pythonanywhere.com`.
2. Log in as `admin@maseno.ac.ke` with your `ADMIN_PASSWORD`.
3. If a random password was generated instead, find it in the **Error log** (search for `FIRST RUN`).
4. Click **Run until 1 month from today** on the Web tab. Do this monthly, or the free site is disabled.

## Keeping your old data (optional)
Only if real students already registered. Otherwise start fresh.
```bash
OLD=~/maseno-guide-old/maseno-first-year-guide-updated/maseno-guide
cp $OLD/maseno.db ~/maseno-guide/
cp -r $OLD/uploads/. ~/maseno-guide/uploads/
cp -r $OLD/papers/. ~/maseno-guide/papers/
```
An old database keeps its old admin password. Reset it:
```bash
cd ~/maseno-guide && workon maseno-env && python - <<'PY'
import sqlite3
from werkzeug.security import generate_password_hash
db = sqlite3.connect("maseno.db")
db.execute("UPDATE users SET password=? WHERE role='admin'", (generate_password_hash("NEW-STRONG-PASSWORD"),))
db.commit()
PY
```

## Updating later
Upload changed files in the **Files** tab (or unzip over the folder), then press **Reload**. Never overwrite `.env`, `maseno.db`, `uploads/` or `papers/`.

## Backups
Once a week, download `maseno.db` and the `uploads` folder from the Files tab. They contain student data, so store them safely.

## Troubleshooting
| Symptom | Fix |
|---|---|
| "Something went wrong" page | Open the Web tab **Error log**, read the last lines (check their time). |
| `No module named ...` | `workon maseno-env && pip install -r requirements.txt`, then Reload. |
| `No module named 'app'` | WSGI `PROJECT` path is wrong. Run `pwd` in the folder that has `app.py`. |
| No styling | Add the `/static/` row in Static files. |
| Registration email never arrives | Check spam. Check the Error log for "Could not send verification email". Use a Gmail App Password. Students can use "Resend verification email" on the login page. |
| "Please try again" page | The form was open too long. Refresh the page and submit again. |
| Map is plain or hotels list is only the built-in examples | Check `GEOAPIFY_API_KEY` in `.env`, then Reload. |

## Before real students use it
- Edit the sample events in Admin > Events and add real WhatsApp groups in Admin > WhatsApp groups.
- The built-in hotel examples in `static/js/hotels.js` (`staticFallback`) are placeholders shown only when Geoapify returns nothing. Check or replace them.
- Check the documents list, checklist and tips (top of `app.py`) against the current official new-student notice at maseno.ac.ke.
- In Geoapify's dashboard, restrict your API key to `mitchellsidhs.pythonanywhere.com` if the option is offered, because map keys are visible in the browser.
- Free accounts limit outgoing connections to a whitelist. Gmail SMTP and the Geoapify calls made from students' browsers work this way, but check PythonAnywhere's current whitelist if email fails.
- The app has no login rate limit. Use strong passwords, and consider a paid plan or a rate limiter if it grows.

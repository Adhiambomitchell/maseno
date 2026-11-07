# Maseno First-Year Guide on Render's FREE plan

Render's free web service has a wiped filesystem, no persistent disk, and blocks SMTP email ports. This edition works around all three:

| Free-plan limit | What this edition does |
|---|---|
| Files and SQLite are wiped on restart or redeploy | Data lives in an external **Postgres** database (`DATABASE_URL`) |
| Uploaded documents can't be saved to disk | Uploads are stored **inside the database** (capped at 3 MB each) |
| SMTP ports 25/465/587 are blocked | Verification emails go over HTTPS through **Brevo** |
| Service sleeps after 15 minutes idle | An uptime monitor pings `/healthz` to keep it awake |

**Do not use Render's own free Postgres.** It expires 30 days after creation and is then deleted. Use a database that doesn't expire (for example Neon). Check each provider's current free limits before you pick.

## 1. Free database (Neon)
1. Sign up at neon.tech and create a project.
2. Copy the **connection string**. It looks like `postgresql://user:password@host/dbname?sslmode=require`.
3. Keep it secret. It is your `DATABASE_URL`.

The app creates all its tables on first start, so there is nothing to set up inside the database.

## 2. Free email (Brevo)
1. Sign up at brevo.com and **verify a sender address** (the email students will see the message come from).
2. Create an **API key** (SMTP & API > API keys).
3. You will use the key as `BREVO_API_KEY` and the verified address as `MAIL_DEFAULT_SENDER`.

Skip this and leave both empty if you don't want email verification. Students can then log in right after registering.

## 3. Put the code on GitHub
```bash
cd maseno-guide
git init && git add . && git commit -m "Maseno guide"
```
Create a **private** repository and push. `.env`, databases and uploads are in `.gitignore`.

## 4. Create the Render web service
Render Dashboard > New > Web Service > connect your repository.
- **Runtime:** Python
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn app:app --workers 1 --threads 4 --timeout 60`
- **Instance type:** Free

## 5. Environment variables (Environment tab)
| Key | Value |
|---|---|
| `PRODUCTION` | `1` |
| `SECRET_KEY` | long random string (`python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_URL` | your Neon connection string |
| `ADMIN_EMAIL` | your admin email |
| `ADMIN_PASSWORD` | a strong password |
| `GEOAPIFY_API_KEY` | your **new** Geoapify key |
| `BREVO_API_KEY` | your Brevo key (or leave empty) |
| `MAIL_DEFAULT_SENDER` | your verified Brevo sender (or leave empty) |

`SECRET_KEY` is required here: without it, every restart logs everyone out.

## 6. Deploy and test
1. Deploy. When it says Live, open your `onrender.com` address.
2. Log in as admin, register a test student, upload a document, restart the service from the dashboard, and confirm the data is still there.
3. If the admin password isn't what you set, search the service Logs for `FIRST RUN`.

## 7. Keep it awake
Sleeping apps take about a minute to wake up. To avoid it, create a free monitor at uptimerobot.com that requests `https://YOUR-APP.onrender.com/healthz` every 5 minutes. That endpoint doesn't touch the database. Free instance hours are limited per month, so check Render's current limits; one always-on service uses most of a month.

## Limits you should know about
- **Storage is small.** Free databases are small (check your provider's current number). With 3 MB per file, a free database holds on the order of a few hundred documents, far fewer than a full intake. Ask students to upload compressed scans, or move to a bigger or paid database.
- **No data guarantees.** Free tiers can change or disappear. Back up weekly:
  ```bash
  pg_dump "YOUR_DATABASE_URL" > backup.sql
  ```
- **Student ID documents are sensitive.** Use strong admin passwords, and don't share the database URL.
- **Cold starts** still happen if the monitor misses a ping.

## Troubleshooting
| Symptom | Fix |
|---|---|
| Build fails installing `psycopg2-binary` | Add env var `PYTHON_VERSION` set to a full 3.12 version (e.g. `3.12.3`) and redeploy. |
| `OperationalError` / can't connect | Check `DATABASE_URL` is complete and includes `?sslmode=require`. |
| Everyone logged out after a while | `SECRET_KEY` is missing. Set it. |
| No verification email | Check spam, confirm the Brevo sender is verified, read the Logs for "Could not send verification email". |
| "Please try again" page | Form was open too long. Refresh and resubmit. |

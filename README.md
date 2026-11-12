# Bennett Verse — Email Authentication Edition

Bennett Verse is an independent, student-led campus newsroom concept. It is **not an official Bennett University publication**.

## Features in this phase
- Student registration with university email address
- Email OTP verification before first sign-in
- Password hashing using Argon2
- JWT-based sign-in sessions
- Only verified, signed-in users can submit stories
- Submissions remain pending until editorial approval
- Public can read approved stories without signing in
- Configurable email domain, SMTP service, database and frontend CORS origins

## 1. Confirm the university email domain
The starter defaults to `bennett.edu.in` in `.env.example`. **Confirm the exact student email domain with Bennett University IT before launch.** Change `ALLOWED_EMAIL_DOMAIN` if necessary. The code checks the domain suffix exactly.

## 2. Local setup on macOS
Unzip the project. Open Terminal in the `backend` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set the environment variables in your terminal (or use a local environment loader of your choice). For quick local testing without sending email, use:

```bash
export ALLOWED_EMAIL_DOMAIN="bennett.edu.in"
export JWT_SECRET="replace-with-a-long-random-secret"
export ADMIN_TOKEN="replace-with-a-different-long-random-secret"
export DEV_SHOW_OTP=true
uvicorn main:app --reload
```

In development mode, the verification code is printed in the backend terminal. This is **for local testing only**. Enter that code in the Verify email form.

In a second Terminal window, serve the frontend over HTTP (rather than opening the HTML file directly):

```bash
cd bennett_verse/frontend
python3 -m http.server 5500
```

Open `http://127.0.0.1:5500` for the public website. Open `http://127.0.0.1:5500/admin.html` for the editorial dashboard. The backend CORS defaults allow this local origin.

## 3. Configure real email delivery
For actual email verification, configure SMTP environment variables:
- `SMTP_HOST`
- `SMTP_PORT` (usually 587 with STARTTLS)
- `SMTP_USERNAME`
- `SMTP_PASSWORD` (use a provider-issued app password or SMTP credential)
- `SMTP_FROM`

Then set `DEV_SHOW_OTP=false`. Never expose SMTP credentials in frontend JavaScript or commit them to Git.

## 4. Configure admin moderation
Set a strong `ADMIN_TOKEN` on the backend. Open Editorial desk in the frontend and enter this token to review pending stories. This shared-token moderation is a temporary starter mechanism, not a final multi-editor account system.

## 5. Database
SQLite is used by default for local development. To use PostgreSQL in a deployed environment, set `DATABASE_URL` to your managed PostgreSQL connection string and install the appropriate PostgreSQL driver (for example `psycopg[binary]`). Back up the database and test migrations before changing schemas in production.

## 6. Production checklist — required before public launch
- Confirm the exact student email domain with university IT.
- Use a reputable transactional email provider and verify sender domain / SPF / DKIM / DMARC.
- Set strong, unique `JWT_SECRET` and `ADMIN_TOKEN` values; keep all secrets server-side.
- Set `DEV_SHOW_OTP=false`.
- Restrict `CORS_ORIGINS` to the exact HTTPS frontend domain.
- Deploy behind HTTPS; use managed PostgreSQL and backups.
- Add rate limiting for registration, OTP resend/verify and login; add CAPTCHA or abuse controls.
- Add a proper admin/editor user system with roles, audit logs and account recovery instead of a shared admin token.
- Consider secure refresh-token/session revocation, email-change workflow, password reset and account deletion.
- Add moderation guidelines, correction/takedown process, source checks, photo permissions and privacy policy.
- Ensure the publication is clearly labelled independent and does not imply university endorsement.

This is a development starter, not a security-audited production service.


## Editorial dashboard (new)
Open `frontend/admin.html` in your browser after starting the backend. Enter the `ADMIN_TOKEN` configured on the backend.

Dashboard features:
- Overview metrics: total, pending, published, featured and registered contributors
- Pending queue with approve, edit and reject actions
- Published story management with edit, delete and feature/unfeature actions
- Contributor directory with verification status and submission counts
- Featured stories are sorted to the top of the public news feed

New admin API routes:
- `GET /api/admin/stats`
- `GET /api/admin/stories?status=all|pending|published`
- `GET /api/admin/contributors`
- `PATCH /api/admin/stories/{id}`
- `POST /api/admin/stories/{id}/feature`

The admin dashboard currently uses the shared `ADMIN_TOKEN` configured in the backend. This is a development-stage control mechanism. Before a public launch, replace it with individual editor accounts, role-based access control, audit logging, rate limiting and secure session management.

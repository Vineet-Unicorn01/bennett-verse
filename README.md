# Bennett Verse — deployment-ready starter

Independent student-led campus newsroom. Not an official Bennett University publication.

## Project structure
- `frontend/index.html`: public website
- `frontend/admin.html`: editorial dashboard
- `frontend/config.js`: backend API URL; edit after deployment
- `backend/main.py`: FastAPI, email OTP, JWT auth, editorial APIs
- `render.yaml`: Render Blueprint for free static site + API

## Before deployment
1. Confirm the exact Bennett student email domain with university IT. `bennett.edu.in` is only a default placeholder until confirmed.
2. Create a Neon PostgreSQL project and copy its connection string.
3. Create a Resend account, verify a sender domain, and create an API key. Set `EMAIL_FROM` to the verified sender. The app uses Resend over HTTPS because Render free services block SMTP ports.
4. Push the complete project to GitHub.

## Deploy with Render
1. Sign in at https://render.com and choose **New → Blueprint**.
2. Connect the GitHub repository containing `render.yaml`.
3. Render should detect `bennett-verse-api` and `bennett-verse-site`.
4. Set `DATABASE_URL`, `RESEND_API_KEY`, `EMAIL_FROM`, and confirm `ALLOWED_EMAIL_DOMAIN`.
5. Copy the frontend and API service URLs after deployment.
6. Edit `frontend/config.js`: replace `http://127.0.0.1:8000` with the API URL, then commit and push.
7. Set API service `CORS_ORIGINS` to the exact frontend URL and redeploy.
8. Test `/api/health`, the public website and `/admin.html`.

## Free-tier limitations
- Render free web services sleep after 15 minutes idle; waking can take around a minute.
- Render free filesystems are ephemeral. Use Neon PostgreSQL, not SQLite, for deployed data.
- Render free services cannot send SMTP on ports 25, 465 or 587. Verification uses Resend HTTPS API.
- Neon Free has usage quotas and compute scales to zero; check current limits.
- Custom domains require separate paid registration. Use the free `onrender.com` address initially.
- Free hosting is suitable for a prototype/early pilot, not a production uptime guarantee.

## Custom domain
After the Render URL works, purchase the domain, add it under the Render static site's Custom Domains settings, configure the DNS records provided by Render, wait for HTTPS, then update `CORS_ORIGINS` and Resend sender-domain verification as appropriate.

## Production checklist
- Replace shared admin token with individual editor accounts and role-based permissions.
- Add rate limits for registration, OTP, login and moderation.
- Add account recovery, session revocation, audit logs, backups and correction/takedown process.
- Keep API keys and secrets in Render environment variables, never in frontend files or GitHub.
- Restrict CORS to exact trusted domains.
- Confirm student email domain with university IT.
- Clearly identify Bennett Verse as independent and avoid implying university endorsement.

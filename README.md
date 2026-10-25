# Halloween Night Market Vendor Voting

Mobile-friendly Flask app with vendor-specific QR codes, server-side SQLite vote storage, organizer dashboard, private-by-default results, and printable QR signs.

## Deploy quickly

1. Upload these files to a private Git repository.
2. Create a Web Service at https://render.com/ and connect the repository.
3. Build command: `pip install -r requirements.txt`; start command: `gunicorn app:app`.
4. Set environment variables:
   - `ADMIN_PASSWORD`: strong unique organizer password
   - `APP_SECRET`: long random secret
   - `BASE_URL`: final public HTTPS URL with no trailing slash
   - `COOKIE_SECURE`: `1`
   - `DATABASE_PATH`: persistent disk path, if your host requires one
5. Deploy, visit `/admin`, sign in, and rename the 15 placeholder vendors/add any others.
6. Open **Open printable QR sheet** from the dashboard and print. Do this only after `BASE_URL` is the final public URL.
7. Test a code on a phone using cellular data. Then delete the test vote from the dashboard before the event.
8. Keep voting open during the market. At the end, choose **Close voting now**, then **Reveal public results**.

## Persistence warning

SQLite needs persistent storage. Some free hosting plans erase local files on restarts or redeploys. Configure a persistent disk and set `DATABASE_PATH` to a file on that disk, or use a managed database. Do not run the live event on ephemeral storage.

## Fairness limitations

This version allows one vote per browser token and stores a unique token hash server-side. It is a deterrent, **not verified one-person-one-vote**: clearing cookies or switching devices/browsers can bypass it. IP-only blocking is avoided because customers may share Wi-Fi. Stronger identity checks (SMS/email verification) would be needed for stronger assurance.

## Local test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export APP_SECRET='a-long-random-secret'
export ADMIN_PASSWORD='choose-a-strong-password'
python app.py
```

Open `http://localhost:5000`. QR codes printed for localhost will not work on customers' phones; deploy first.

## Routes
- `/` landing page
- `/vendors` vendor directory
- `/vote?vendor=vendor-01` vendor ballot
- `/admin` organizer login
- `/admin/dashboard` controls, tally, vendor management
- `/admin/qr-sheet` printable QR signs (admin only)
- `/results` hidden until revealed
- `/health` health check

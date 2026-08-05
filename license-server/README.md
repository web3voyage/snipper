# StealthOverlay license service

This service generates 12-character activation codes and redeems each code for
exactly one installation. It stores only an HMAC digest of the visible code.
The app receives an Ed25519-signed, installation-bound activation token and can
verify it offline on later launches.

## Production setup

1. Create a private PostgreSQL database and set `LICENSE_DATABASE_URL`.
2. Run `python generate_signing_keys.py` once on a secure machine.
3. Keep `private_key.pem` only in your server's secret manager. Copy
   `public_key.pem` to `backend/license_public_key.pem` before building the app.
4. Set a random admin token and independent code pepper of at least 24
   characters. Do not commit either value.
5. Put the service behind HTTPS and a rate-limiting reverse proxy.
6. Change `backend/license_config.json` to the public HTTPS service URL.

Run locally with:

```powershell
pip install -r requirements.txt
$env:LICENSE_DATABASE_URL='sqlite:///./licenses.db'
$env:LICENSE_ADMIN_TOKEN='<long-random-admin-secret>'
$env:LICENSE_CODE_PEPPER='<different-long-random-secret>'
$env:LICENSE_PRIVATE_KEY_FILE='private_key.pem'
uvicorn app:app --host 127.0.0.1 --port 8787
```

Generate codes with an authenticated request to `POST /admin/keys`. Codes are
returned only in that response and should be delivered through a separate,
authenticated channel.

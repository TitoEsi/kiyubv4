Deploy with `supabase functions deploy architect-rejection`.

Set function secrets (same SMTP as Authentication → SMTP, plus the shared secret):

```
REJECTION_MAIL_SECRET
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASS
SMTP_FROM
```

Set `REJECTION_MAIL_SECRET` on the FastAPI host as well. The browser never calls this function.

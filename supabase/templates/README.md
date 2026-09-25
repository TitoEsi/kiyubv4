Paste these into Supabase Dashboard → Authentication → Emails.

- `invite.html` — Invite user template (client and approved-architect completion).
- `architect-approved.html` — optional copy variant for the same Invite user template.
- `architect-rejected.html` — rejection notice. Auth cannot send this unless a Send Email hook / Edge Function is configured.

Also set Authentication → URL Configuration:

- Site URL = `PUBLIC_APP_URL`
- Redirect URLs = `{PUBLIC_APP_URL}/**` and `http://localhost:5173/**`

import nodemailer from "npm:nodemailer@6.9.16";

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function rejectionHtml(fullName: string, reason: string | null): string {
  const name = escapeHtml(fullName || "there");
  const reasonBlock = reason
    ? `<p>Reason:</p><p>${escapeHtml(reason)}</p>`
    : "";
  return `<h2>KIYUB</h2>
<p>Your architect registration request was not approved.</p>
<p>Hello ${name},</p>
<p>Your request to join KIYUB as an architect was not approved.</p>
${reasonBlock}
<p>If you believe this is a mistake, contact the studio that referred you.</p>`;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }
  const expected = Deno.env.get("REJECTION_MAIL_SECRET") || "";
  const provided = req.headers.get("x-rejection-secret") || "";
  if (!expected || provided !== expected) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401 });
  }
  let body: {
    email?: string;
    full_name?: string;
    rejection_reason?: string | null;
    status?: string;
  };
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid body" }), { status: 400 });
  }
  const email = String(body.email || "").trim().toLowerCase();
  if (body.status !== "REJECTED" || !email.includes("@")) {
    return new Response(JSON.stringify({ error: "Invalid rejection payload" }), { status: 400 });
  }
  const reason = String(body.rejection_reason || "").trim() || null;
  const host = Deno.env.get("SMTP_HOST") || "";
  const user = Deno.env.get("SMTP_USER") || "";
  const pass = Deno.env.get("SMTP_PASS") || "";
  const from = Deno.env.get("SMTP_FROM") || user;
  const port = Number(Deno.env.get("SMTP_PORT") || "587");
  if (!host || !user || !pass || !from) {
    return new Response(JSON.stringify({ error: "SMTP is not configured" }), { status: 503 });
  }
  const transporter = nodemailer.createTransport({
    host,
    port,
    secure: port === 465,
    auth: { user, pass },
  });
  await transporter.sendMail({
    from,
    to: email,
    subject: "Your KIYUB architect registration request",
    html: rejectionHtml(String(body.full_name || ""), reason),
  });
  return new Response(JSON.stringify({ sent: true }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
});

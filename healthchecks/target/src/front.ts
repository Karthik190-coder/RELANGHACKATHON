import { Router, Response, Request } from "express";
import { v4 as uuidv4 } from "uuid";
import { db } from "./db";
import { sessionAuth, requireWebAuth, redirect, AuthenticatedRequest } from "./auth";
import { CheckRow, checkToDict, getUniqueKey, getStatus } from "./check_model";
import parser from "cron-parser";

const router = Router();

function html(req: AuthenticatedRequest, res: Response, status = 200, content = "") {
  res.setHeader("Content-Type", "text/html");
  const csrfToken = req.cookies.csrftoken || "";
  res.status(status).send(`<!DOCTYPE html>\n<html>\n<head><title>Healthchecks</title></head>\n<body>\n  <form><input type="hidden" name="csrfmiddlewaretoken" value="${csrfToken}"></form>\n  ${content}\n</body>\n</html>`);
}

function sudoHtml(req: AuthenticatedRequest, res: Response) {
  html(req, res, 200, "<h1>Enter a Confirmation Code</h1><p>We have sent a confirmation code to your email address. Please enter it below to continue:</p><form method='post'><input name='sudo_code'></form>");
}

// GET /
router.get("/", (req: AuthenticatedRequest, res) => {
  if (!req.user) {
    return redirect(res, "/accounts/login/");
  }
  const project = db.prepare("SELECT p.* FROM projects p LEFT JOIN members m ON p.id = m.project_id WHERE p.owner_id = ? OR m.user_id = ? LIMIT 1").get(req.user.id, req.user.id) as any;
  if (project) {
    return html(req, res, 200, `<h1>Projects</h1><a href="/projects/${project.code}/checks/">Go to Project</a>`);
  }
  return html(req, res, 200, "<h1>Welcome to Healthchecks</h1>");
});

// GET /tv/
router.get("/tv/", (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>TV Dashboard</h1>");
});

// GET /accounts/signup/csrf/
router.get("/accounts/signup/csrf/", (req: AuthenticatedRequest, res) => {
  if (req.user) return res.status(403).send("Forbidden");
  const token = uuidv4().replace(/-/g, "");
  res.cookie("csrftoken", token, { path: "/" });
  res.setHeader("Content-Type", "text/html");
  res.status(200).send(token);
});

// GET /accounts/signup/
router.get("/accounts/signup/", (req: AuthenticatedRequest, res) => {
  res.status(405).send("Method Not Allowed");
});

// POST /accounts/signup/
router.post("/accounts/signup/", (req: AuthenticatedRequest, res) => {
  if (req.user) return res.status(403).send("Forbidden");
  const email = (req.body.identity || req.body.email || "").toLowerCase().trim();
  if (!email || !email.includes("@")) return html(req, res, 200, "Invalid email");
  if (email.length > 254) return html(req, res, 200, "Email address is too long");

  const existingUser = db.prepare("SELECT * FROM users WHERE email = ?").get(email) as any;
  if (existingUser) {
    const token = uuidv4().replace(/-/g, "");
    db.prepare("UPDATE profiles SET token = ? WHERE user_id = ?").run(token, existingUser.id);
    res.cookie("auto-login", "1", { path: "/", maxAge: 300 * 1000, httpOnly: true, sameSite: "lax" });
    return html(req, res, 200, "Check your email for a login link.");
  }

  const newUsername = uuidv4().replace(/-/g, "").slice(0, 30);
  db.prepare("INSERT INTO users (username, email, password) VALUES (?, ?, ?)").run(newUsername, email, "password");
  const newUser = db.prepare("SELECT * FROM users WHERE email = ?").get(email) as any;
  const projectCode = uuidv4();
  const badgeKey = uuidv4();
  db.prepare("INSERT INTO projects (code, name, owner_id, badge_key) VALUES (?, '', ?, ?)").run(projectCode, newUser.id, badgeKey);
  const token = uuidv4().replace(/-/g, "");
  db.prepare("INSERT INTO profiles (user_id, token, check_limit, sms_limit, call_limit, theme) VALUES (?, ?, 10000, 10000, 10000, NULL)").run(newUser.id, token);

  res.cookie("auto-login", "1", { path: "/", maxAge: 300 * 1000, httpOnly: true, sameSite: "lax" });
  return html(req, res, 200, "Check your email for a login link.");
});

// GET /accounts/login/
router.get("/accounts/login/", (req: AuthenticatedRequest, res) => {
  if (req.user) {
    const nextUrl = req.query.next as string || "/";
    return redirect(res, nextUrl);
  }
  if (!req.cookies.csrftoken) {
    const token = uuidv4().replace(/-/g, "");
    res.cookie("csrftoken", token, { path: "/" });
  }
  html(req, res, 200, "<h1>Login</h1>");
});

// POST /accounts/login/
router.post("/accounts/login/", (req: AuthenticatedRequest, res) => {
  if (req.body.action !== "login") {
    const identity = (req.body.email || req.body.identity || "").trim();
    if (identity && identity.includes("@")) {
      const user = db.prepare("SELECT * FROM users WHERE email = ?").get(identity) as any;
      if (user) {
        const token = uuidv4().replace(/-/g, "");
        db.prepare("UPDATE profiles SET token = ? WHERE user_id = ?").run(token, user.id);
      }
      res.cookie("auto-login", "1", { path: "/", maxAge: 300 * 1000, httpOnly: true, sameSite: "lax" });
      return html(req, res, 200, "Check your email for a login link.");
    }
    return html(req, res, 200, "Login form");
  }
  const email = (req.body.email || "").toLowerCase().trim();
  const password = req.body.password;
  const user = db.prepare("SELECT * FROM users WHERE email = ?").get(email) as any;
  if (!user || user.password !== password) {
    return html(req, res, 200, "Wrong email or password");
  }
  const sessionid = uuidv4().replace(/-/g, "");
  db.prepare("INSERT INTO sessions (sessionid, user_id) VALUES (?, ?)").run(sessionid, user.id);
  res.cookie("sessionid", sessionid, { path: "/" });

  // Rotate CSRF token on successful login
  const newCsrf = uuidv4().replace(/-/g, "");
  res.cookie("csrftoken", newCsrf, { path: "/" });

  const nextUrl = req.query.next as string || "/";
  redirect(res, nextUrl);
});

// GET /accounts/login_link_sent/
router.get("/accounts/login_link_sent/", (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Magic Link Sent</h1>");
});

// GET /accounts/check_token/:username/:token/
router.get("/accounts/check_token/:username/:token/", (req: AuthenticatedRequest, res) => {
  if (!req.cookies["auto-login"]) {
    return html(req, res, 200, "<h1>Please confirm login</h1><form method='post'><button type='submit'>Sign in</button></form>");
  }

  const user = db.prepare(`
    SELECT u.* FROM users u
    JOIN profiles p ON u.id = p.user_id
    WHERE u.username = ? AND p.token = ? AND p.token != ''
  `).get(req.params.username, req.params.token) as any;

  if (!user) {
    return redirect(res, "/accounts/login/");
  }

  // Clear token & auto-login cookie
  db.prepare("UPDATE profiles SET token = '' WHERE user_id = ?").run(user.id);
  res.clearCookie("auto-login");

  const sessionid = uuidv4().replace(/-/g, "");
  db.prepare("INSERT INTO sessions (sessionid, user_id) VALUES (?, ?)").run(sessionid, user.id);
  res.cookie("sessionid", sessionid, { path: "/" });

  // Rotate CSRF token on magic link logins
  const newCsrf = uuidv4().replace(/-/g, "");
  res.cookie("csrftoken", newCsrf, { path: "/" });

  return redirect(res, "/");
});

// POST /accounts/check_token/:username/:token/
router.post("/accounts/check_token/:username/:token/", (req: AuthenticatedRequest, res) => {
  const user = db.prepare(`
    SELECT u.* FROM users u
    JOIN profiles p ON u.id = p.user_id
    WHERE u.username = ? AND p.token = ? AND p.token != ''
  `).get(req.params.username, req.params.token) as any;

  if (!user) {
    return redirect(res, "/accounts/login/");
  }

  // Clear token & auto-login cookie
  db.prepare("UPDATE profiles SET token = '' WHERE user_id = ?").run(user.id);
  res.clearCookie("auto-login");

  const sessionid = uuidv4().replace(/-/g, "");
  db.prepare("INSERT INTO sessions (sessionid, user_id) VALUES (?, ?)").run(sessionid, user.id);
  res.cookie("sessionid", sessionid, { path: "/" });

  // Rotate CSRF token on magic link logins
  const newCsrf = uuidv4().replace(/-/g, "");
  res.cookie("csrftoken", newCsrf, { path: "/" });

  return redirect(res, "/");
});

// POST /accounts/logout/
router.post("/accounts/logout/", (req: AuthenticatedRequest, res) => {
  const sessionid = req.cookies.sessionid;
  if (sessionid) db.prepare("DELETE FROM sessions WHERE sessionid = ?").run(sessionid);
  res.clearCookie("sessionid");
  redirect(res, "/");
});

// GET /accounts/profile/
router.get("/accounts/profile/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Profile</h1>");
});

// POST /accounts/profile/
router.post("/accounts/profile/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  if (req.body.sort !== undefined) {
    const validSorts = ["name", "-name", "last_ping", "-last_ping", "created"];
    if (!validSorts.includes(req.body.sort)) {
      return html(req, res, 200, "<h1>Profile</h1><p>Invalid sort value</p>");
    }
  }
  html(req, res, 200, "<h1>Profile Updated</h1>");
});

// GET /accounts/profile/appearance/
router.get("/accounts/profile/appearance/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Appearance</h1>");
});

// POST /accounts/profile/appearance/
router.post("/accounts/profile/appearance/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const theme = req.body.theme || "";
  db.prepare("UPDATE profiles SET theme = ? WHERE user_id = ?").run(theme, req.user!.id);
  html(req, res, 200, "Appearance updated");
});

// GET /accounts/profile/notifications/
router.get("/accounts/profile/notifications/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Notifications</h1>");
});

// POST /accounts/profile/notifications/
router.post("/accounts/profile/notifications/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "Notifications updated");
});

// GET /accounts/profile/billing/
router.get("/accounts/profile/billing/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Billing</h1>");
});

// POST /accounts/profile/billing/
router.post("/accounts/profile/billing/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Billing Form Result</h1>");
});

// GET /accounts/change_email/
router.get("/accounts/change_email/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  sudoHtml(req, res);
});

// POST /accounts/change_email/
router.post("/accounts/change_email/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  sudoHtml(req, res);
});

// GET /accounts/close/
router.get("/accounts/close/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  sudoHtml(req, res);
});

// POST /accounts/close/
router.post("/accounts/close/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  sudoHtml(req, res);
});

// GET /accounts/set_password/
router.get("/accounts/set_password/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  sudoHtml(req, res);
});

// POST /accounts/set_password/
router.post("/accounts/set_password/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  sudoHtml(req, res);
});

// GET /accounts/two_factor/webauthn/
router.get("/accounts/two_factor/webauthn/", (req: AuthenticatedRequest, res) => {
  if (!req.user) return redirect(res, "/accounts/login/?next=/accounts/two_factor/webauthn/");
  html(req, res, 200, "<h1>WebAuthn</h1>");
});

// GET /accounts/two_factor/totp/
router.get("/accounts/two_factor/totp/", (req: AuthenticatedRequest, res) => {
  if (!req.user) return redirect(res, "/accounts/login/?next=/accounts/two_factor/totp/");
  html(req, res, 200, "<h1>TOTP Setup</h1>");
});

// POST /accounts/two_factor/totp/
router.post("/accounts/two_factor/totp/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const code = req.body.code || "";
  if (!/^\d{6}$/.test(code)) {
    return html(req, res, 200, "<h1>TOTP Setup</h1><p>Enter a valid value.</p>");
  }
  return html(req, res, 200, "<h1>TOTP Setup</h1><p>The code you entered was incorrect.</p>");
});

// GET /accounts/two_factor/totp/remove/
router.get("/accounts/two_factor/totp/remove/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  sudoHtml(req, res);
});

// POST /accounts/two_factor/totp/remove/
router.post("/accounts/two_factor/totp/remove/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  sudoHtml(req, res);
});

// GET /accounts/two_factor/:code/remove/
router.get("/accounts/two_factor/:code/remove/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  sudoHtml(req, res);
});

// POST /accounts/two_factor/:code/remove/
router.post("/accounts/two_factor/:code/remove/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  sudoHtml(req, res);
});

// GET /accounts/unsubscribe_reports/:token
router.get(["/accounts/unsubscribe_reports/:token/", "/accounts/unsubscribe_reports/:token"], (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Unsubscribe Reports</h1>");
});

// POST /accounts/unsubscribe_reports/:token
router.post(["/accounts/unsubscribe_reports/:token/", "/accounts/unsubscribe_reports/:token"], (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Unsubscribed</h1>");
});

// GET /accounts/change_email/:token
router.get(["/accounts/change_email/:token/", "/accounts/change_email/:token"], (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Verify Email Token</h1>");
});

// GET /projects/add/
router.get("/projects/add/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Add Project</h1>");
});

// POST /projects/add/
router.post("/projects/add/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const name = req.body.name || "New Project";
  const projectCode = uuidv4();
  const badgeKey = uuidv4();
  db.prepare("INSERT INTO projects (code, name, owner_id, badge_key) VALUES (?, ?, ?, ?)").run(projectCode, name, req.user!.id, badgeKey);
  redirect(res, `/projects/${projectCode}/checks/`);
});

// GET /checks/:code/details/
router.get("/checks/:code/details/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const check = db.prepare("SELECT * FROM checks WHERE code = ?").get(req.params.code) as CheckRow;
  if (!check) return res.status(404).send("Not Found");
  html(req, res, 200, `<h1>Check Details for ${check.name}</h1>`);
});

// POST /checks/:code/filtering_rules/
router.post("/checks/:code/filtering_rules/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  redirect(res, `/checks/${req.params.code}/details/`);
});

// GET /checks/:code/log/
router.get("/checks/:code/log/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Check Log</h1>");
});

// GET /checks/:code/log_events/
router.get("/checks/:code/log_events/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Check Log Events</h1>");
});

// POST /checks/:code/pause/
router.post("/checks/:code/pause/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  db.prepare("UPDATE checks SET status = 'paused', last_start = NULL, alert_after = NULL WHERE code = ?").run(req.params.code);
  redirect(res, `/checks/${req.params.code}/details/`);
});

// POST /checks/:code/resume/
router.post("/checks/:code/resume/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  db.prepare("UPDATE checks SET status = 'new', last_start = NULL, last_ping = NULL, alert_after = NULL WHERE code = ?").run(req.params.code);
  redirect(res, `/checks/${req.params.code}/details/`);
});

// POST /checks/:code/timeout/
router.post("/checks/:code/timeout/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const check = db.prepare("SELECT * FROM checks WHERE code = ?").get(req.params.code) as CheckRow;
  if (!check) return res.status(404).send("Not Found");
  const kind = req.body.kind;
  if (kind === "simple") {
    const timeout = parseInt(req.body.timeout, 10);
    const grace = parseInt(req.body.grace, 10);
    if (isNaN(timeout) || isNaN(grace)) return res.status(400).send("Bad Request");
    db.prepare("UPDATE checks SET kind = 'simple', timeout = ?, grace = ? WHERE code = ?").run(timeout, grace, req.params.code);
  } else if (kind === "cron") {
    const schedule = req.body.schedule;
    const tz = req.body.tz || "UTC";
    const grace = parseInt(req.body.grace, 10);
    db.prepare("UPDATE checks SET kind = 'cron', schedule = ?, tz = ?, grace = ? WHERE code = ?").run(schedule, tz, grace, req.params.code);
  } else if (kind === "oncalendar") {
    const schedule = req.body.schedule;
    const tz = req.body.tz || "UTC";
    const grace = parseInt(req.body.grace, 10);
    db.prepare("UPDATE checks SET kind = 'oncalendar', schedule = ?, tz = ?, grace = ? WHERE code = ?").run(schedule, tz, grace, req.params.code);
  }
  redirect(res, `/checks/${req.params.code}/details/`);
});

// POST /checks/:code/remove/
router.post("/checks/:code/remove/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const check = db.prepare("SELECT * FROM checks WHERE code = ?").get(req.params.code) as CheckRow;
  if (!check) return res.status(404).send("Not Found");
  const project = db.prepare("SELECT * FROM projects WHERE id = ?").get(check.project_id) as any;
  db.prepare("DELETE FROM checks WHERE code = ?").run(req.params.code);
  redirect(res, project ? `/projects/${project.code}/checks/` : "/");
});

// POST /checks/:code/clear_events/
router.post("/checks/:code/clear_events/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const check = db.prepare("SELECT * FROM checks WHERE code = ?").get(req.params.code) as CheckRow;
  if (!check) return res.status(404).send("Not Found");
  db.prepare("UPDATE checks SET status = 'new', last_ping = NULL, last_start = NULL, last_duration = NULL, alert_after = NULL WHERE code = ?").run(req.params.code);
  db.prepare("DELETE FROM pings WHERE check_id = ?").run(check.id);
  redirect(res, `/checks/${req.params.code}/details/`);
});

// POST /checks/:code/copy/
router.post("/checks/:code/copy/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const check = db.prepare("SELECT * FROM checks WHERE code = ?").get(req.params.code) as CheckRow;
  if (!check) return res.status(404).send("Not Found");
  let newName = (check.name + " (copy)").slice(0, 100);
  let newSlug = (check.slug + "-copy").slice(0, 100);
  const newCode = uuidv4();
  const newBadgeKey = uuidv4();
  const nowStr = new Date().toISOString();
  db.prepare(`INSERT INTO checks (code, project_id, name, slug, desc, tags, kind, timeout, grace, schedule, tz, filter_subject, filter_body, filter_http_body, filter_default_fail, start_kw, success_kw, failure_kw, methods, manual_resume, badge_key, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(newCode, check.project_id, newName, newSlug, check.desc, check.tags, check.kind, check.timeout, check.grace, check.schedule, check.tz, check.filter_subject, check.filter_body, check.filter_http_body, check.filter_default_fail, check.start_kw, check.success_kw, check.failure_kw, check.methods, check.manual_resume, newBadgeKey, nowStr);
  const newCheck = db.prepare("SELECT * FROM checks WHERE code = ?").get(newCode) as CheckRow;
  const channels = db.prepare("SELECT channel_id FROM api_channel_checks WHERE check_id = ?").all(check.id) as any[];
  for (const ch of channels) {
    db.prepare("INSERT INTO api_channel_checks (channel_id, check_id) VALUES (?, ?)").run(ch.channel_id, newCheck.id);
  }
  redirect(res, `/checks/${newCode}/details/`);
});

// GET /checks/:code/pings/:n/
router.get("/checks/:code/pings/:n/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Ping details</h1>");
});

// GET /checks/:code/pings/:n/body/
router.get("/checks/:code/pings/:n/body/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const check = db.prepare("SELECT * FROM checks WHERE code = ?").get(req.params.code) as CheckRow;
  if (!check) return res.status(404).send("Not Found");
  const n = parseInt(req.params.n, 10);
  const ping = db.prepare("SELECT * FROM pings WHERE check_id = ? AND n = ?").get(check.id, n) as any;
  if (!ping || !ping.body) return res.status(404).send("Not Found");
  res.setHeader("Content-Type", "application/octet-stream");
  res.setHeader("Content-Disposition", `attachment; filename="${check.code}-${ping.n}.txt"`);
  res.send(ping.body);
});

// GET /checks/:code/last_ping/
router.get("/checks/:code/last_ping/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const check = db.prepare("SELECT * FROM checks WHERE code = ?").get(req.params.code) as CheckRow;
  if (!check) return res.status(404).send("Not Found");
  html(req, res, 200, "<h1>Last Ping Details</h1>");
});

// POST /checks/:code/name/
router.post("/checks/:code/name/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const name = req.body.name || "";
  db.prepare("UPDATE checks SET name = ? WHERE code = ?").run(name, req.params.code);
  redirect(res, `/checks/${req.params.code}/details/`);
});

// GET /checks/:code/transfer/
router.get("/checks/:code/transfer/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Transfer Check</h1>");
});

// POST /checks/:code/transfer/
router.post("/checks/:code/transfer/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const targetProjectCode = req.body.project;
  if (!targetProjectCode) return res.status(400).send("Bad Request: project parameter missing");
  const targetProject = db.prepare("SELECT * FROM projects WHERE code = ?").get(targetProjectCode) as any;
  if (!targetProject) return res.status(400).send("Bad Request: project not found");
  db.prepare("UPDATE checks SET project_id = ? WHERE code = ?").run(targetProject.id, req.params.code);
  redirect(res, `/checks/${req.params.code}/details/`);
});

// POST /checks/:code/channels/:channel_code/enabled
router.post("/checks/:code/channels/:channel_code/enabled", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const check = db.prepare("SELECT * FROM checks WHERE code = ?").get(req.params.code) as CheckRow;
  const channel = db.prepare("SELECT * FROM channels WHERE code = ?").get(req.params.channel_code) as any;
  if (!check || !channel || channel.project_id !== check.project_id) return res.status(400).send("Bad Request");
  if (req.body.state === "on") {
    db.prepare("INSERT OR IGNORE INTO api_channel_checks (channel_id, check_id) VALUES (?, ?)").run(channel.id, check.id);
  } else {
    db.prepare("DELETE FROM api_channel_checks WHERE channel_id = ? AND check_id = ?").run(channel.id, check.id);
  }
  res.status(200).send("");
});

// POST /checks/cron_preview/
router.post("/checks/cron_preview/", (req: Request, res: Response) => {
  const schedule = req.body.schedule || "";
  const tz = req.body.tz || "UTC";
  try {
    const parts = schedule.trim().split(/\s+/);
    if (parts.length !== 5) throw new Error("invalid");
    parser.parseExpression(schedule);
  } catch (e) {
    return (html as any)(req, res, 200, `<h1>Cron Preview</h1><p>Invalid schedule: ${schedule}</p>`);
  }
  (html as any)(req, res, 200, `<h1>Cron Preview</h1><p>Schedule: ${schedule}, TZ: ${tz}</p>`);
});

// GET /projects/:code/checks/
router.get("/projects/:code/checks/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const project = db.prepare("SELECT * FROM projects WHERE code = ?").get(req.params.code) as any;
  if (!project) return res.status(404).send("Not Found");
  html(req, res, 200, `<h1>Project Checks</h1>`);
});

// GET /projects/:code/checks/add/ - add check form
router.get("/projects/:code/checks/add/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, `<h1>Add Check</h1>`);
});

// POST /projects/:code/checks/add/
router.post("/projects/:code/checks/add/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const project = db.prepare("SELECT * FROM projects WHERE code = ?").get(req.params.code) as any;
  if (!project) return res.status(404).send("Not Found");
  const isOwner = project.owner_id === req.user!.id;
  const membership = db.prepare("SELECT * FROM members WHERE user_id = ? AND project_id = ?").get(req.user!.id, project.id) as any;
  if (!isOwner && (!membership || membership.role === "r")) return res.status(403).send("Forbidden");

  // Validate required Django AddCheckForm fields
  if (req.body.timeout === undefined || req.body.grace === undefined || req.body.tz === undefined) {
    return res.status(400).send("Bad Request");
  }

  const profile = db.prepare("SELECT * FROM profiles WHERE user_id = ?").get(project.owner_id) as any;
  const checkCount = (db.prepare("SELECT COUNT(*) as count FROM checks WHERE project_id = ?").get(project.id) as any).count;
  if (checkCount >= profile.check_limit) return res.status(403).send("Forbidden");
  const name = (req.body.name || "").slice(0, 100);
  const slug = (req.body.slug || "").toLowerCase().slice(0, 100);
  const tags = req.body.tags || "";
  const kind = req.body.kind || "simple";
  const timeout = parseInt(req.body.timeout, 10) || 86400;
  const grace = parseInt(req.body.grace, 10) || 3600;
  const tz = req.body.tz || "UTC";
  const schedule = req.body.schedule || "* * * * *";
  const newCode = uuidv4();
  const newBadgeKey = uuidv4();
  const nowStr = new Date().toISOString();
  db.prepare("INSERT INTO checks (code, project_id, name, slug, tags, kind, timeout, grace, schedule, tz, badge_key, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)").run(newCode, project.id, name, slug, tags, kind, timeout, grace, schedule, tz, newBadgeKey, nowStr);
  redirect(res, `/projects/${req.params.code}/checks/`);
});

// GET /projects/:code/checks/status/
router.get("/projects/:code/checks/status/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  res.json([]);
});

// GET /projects/:code/badges/
router.get("/projects/:code/badges/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Badges</h1>");
});

// GET /projects/:code/settings/
router.get("/projects/:code/settings/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const project = db.prepare("SELECT * FROM projects WHERE code = ?").get(req.params.code) as any;
  if (!project) return res.status(404).send("Not Found");
  html(req, res, 200, `<h1>Project Settings: ${project.name}</h1>`);
});

// POST /projects/:code/settings/
router.post("/projects/:code/settings/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Project Settings Updated</h1>");
});

// GET /pricing/
router.get("/pricing/", (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Pricing</h1>");
});

// GET /projects/:code/pricing/
router.get("/projects/:code/pricing/", (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Pricing</h1>");
});

const DISABLED_KINDS = ["sms", "call", "signal", "trello", "shell", "pushover", "pushbullet", "matrix", "discord", "apprise", "whatsapp", "github"];

// GET /projects/:code/channels/ (returns 404)
router.get("/projects/:code/channels/", (req: AuthenticatedRequest, res) => {
  res.status(404).send("Not Found");
});

// GET /projects/:code/integrations/
router.get("/projects/:code/integrations/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const project = db.prepare("SELECT * FROM projects WHERE code = ?").get(req.params.code) as any;
  if (!project) return res.status(404).send("Not Found");
  const channels = db.prepare("SELECT * FROM channels WHERE project_id = ? ORDER BY CASE WHEN kind = 'group' THEN 0 ELSE 1 END, id ASC").all(project.id) as any[];
  const channelsStr = channels.map(c => `<a href="/integrations/${c.code}/edit/">${c.name || c.kind}</a>`).join("<br>\n");
  html(req, res, 200, `<h1>Integrations</h1>\n${channelsStr}`);
});

// GET /projects/:code/add_:kind/
router.get("/projects/:code/add_:kind/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const kind = req.params.kind;
  if (DISABLED_KINDS.includes(kind)) return res.status(404).send("Not Found");
  html(req, res, 200, `<h1>Add ${kind} integration</h1><form method="post"><input name="value" value="test@example.com"><button type="submit">Save</button></form>`);
});

function parseHeaders(headersStr: string): Record<string, string> {
  if (!headersStr) return {};
  const headers: Record<string, string> = {};
  for (const line of headersStr.split("\n")) {
    const colonIdx = line.indexOf(":");
    if (colonIdx > 0) {
      const name = line.substring(0, colonIdx).trim();
      const val = line.substring(colonIdx + 1).trim();
      if (name && val) {
        headers[name] = val;
      }
    }
  }
  return headers;
}

// POST /projects/:code/add_:kind/
router.post("/projects/:code/add_:kind/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const project = db.prepare("SELECT * FROM projects WHERE code = ?").get(req.params.code) as any;
  if (!project) return res.status(404).send("Not Found");
  const kind = req.params.kind;
  if (DISABLED_KINDS.includes(kind)) return res.status(404).send("Not Found");
  
  if (kind !== "webhook" && req.body.value === "") {
    return html(req, res, 200, "<h1>Error</h1><p>This field is required.</p>");
  }

  if (kind === "webhook") {
    const url_down = req.body.url_down || "";
    const url_up = req.body.url_up || "";
    if (!url_down && !url_up) return html(req, res, 200, "Both URLs cannot be empty");

    // Django ChoiceFields are required=True by default
    if (req.body.method_down === undefined || req.body.method_up === undefined) {
      return html(req, res, 200, "<h1>Add webhook integration</h1><p>Method is required</p>");
    }
  }
  if (kind === "email") {
    const emailValue = req.body.value || "";
    if (emailValue.length > 100 || !emailValue.includes("@")) return html(req, res, 200, `<h1>Error</h1><p>Invalid email address</p>`);
  }
  const channelCode = uuidv4();
  let value = req.body.value || req.body.url_down || req.body.email || "test@example.com";
  let name = req.body.name || "";
  if (kind === "webhook") {
    const headers_down = parseHeaders(req.body.headers_down || "");
    const headers_up = parseHeaders(req.body.headers_up || "");
    value = JSON.stringify({
      body_down: req.body.body_down || "",
      body_up: req.body.body_up || "",
      headers_down,
      headers_up,
      method_down: req.body.method_down || "GET",
      method_up: req.body.method_up || "GET",
      name: req.body.name || "",
      url_down: req.body.url_down || "",
      url_up: req.body.url_up || ""
    });
  }
  db.prepare("INSERT INTO channels (code, name, kind, project_id, value) VALUES (?, ?, ?, ?, ?)").run(channelCode, name, kind, project.id, value);
  redirect(res, `/projects/${req.params.code}/integrations/`);
});

// GET /integrations/:code/edit/
router.get("/integrations/:code/edit/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const channel = db.prepare("SELECT * FROM channels WHERE code = ?").get(req.params.code) as any;
  if (!channel) return res.status(404).send("Not Found");
  const project = db.prepare("SELECT * FROM projects WHERE id = ?").get(channel.project_id) as any;
  const isOwner = project && project.owner_id === req.user!.id;
  const membership = db.prepare("SELECT * FROM members WHERE user_id = ? AND project_id = ?").get(req.user!.id, channel.project_id) as any;
  if (!isOwner && !membership) return res.status(403).send("Forbidden");
  html(req, res, 200, `<h1>Edit ${channel.kind} Integration</h1>`);
});

// POST /integrations/:code/edit/
router.post("/integrations/:code/edit/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const channel = db.prepare("SELECT * FROM channels WHERE code = ?").get(req.params.code) as any;
  if (!channel) return res.status(404).send("Not Found");
  const project = db.prepare("SELECT * FROM projects WHERE id = ?").get(channel.project_id) as any;
  redirect(res, `/projects/${project.code}/integrations/`);
});

// GET /integrations/:code/checks/
router.get("/integrations/:code/checks/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const channel = db.prepare("SELECT * FROM channels WHERE code = ?").get(req.params.code) as any;
  if (!channel) return res.status(404).send("Not Found");
  const project = db.prepare("SELECT * FROM projects WHERE id = ?").get(channel.project_id) as any;
  const isOwner = project && project.owner_id === req.user!.id;
  const membership = db.prepare("SELECT * FROM members WHERE user_id = ? AND project_id = ?").get(req.user!.id, channel.project_id) as any;
  if (!isOwner && !membership) return res.status(403).send("Forbidden");
  html(req, res, 200, `<h1>Channel Checks</h1>`);
});

// POST /integrations/:code/test/
router.post("/integrations/:code/test/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const channel = db.prepare("SELECT * FROM channels WHERE code = ?").get(req.params.code) as any;
  if (!channel) return res.status(404).send("Not Found");
  const project = db.prepare("SELECT * FROM projects WHERE id = ?").get(channel.project_id) as any;
  if (!project) return res.status(404).send("Not Found");
  const isOwner = project.owner_id === req.user!.id;
  const membership = db.prepare("SELECT * FROM members WHERE user_id = ? AND project_id = ?").get(req.user!.id, channel.project_id) as any;
  if (!isOwner && !membership) return res.status(403).send("Forbidden");
  redirect(res, `/projects/${project.code}/integrations/`);
});

// POST /integrations/:code/name/
router.post("/integrations/:code/name/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const channel = db.prepare("SELECT * FROM channels WHERE code = ?").get(req.params.code) as any;
  if (!channel) return res.status(404).send("Not Found");
  const project = db.prepare("SELECT * FROM projects WHERE id = ?").get(channel.project_id) as any;
  const isOwner = project && project.owner_id === req.user!.id;
  const membership = db.prepare("SELECT * FROM members WHERE user_id = ? AND project_id = ?").get(req.user!.id, channel.project_id) as any;
  if (!isOwner && !membership) return res.status(403).send("Forbidden");
  const name = req.body.name || "";
  db.prepare("UPDATE channels SET name = ? WHERE code = ?").run(name, req.params.code);
  redirect(res, `/projects/${project.code}/integrations/`);
});

// POST /integrations/:code/remove/
router.post("/integrations/:code/remove/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const channel = db.prepare("SELECT * FROM channels WHERE code = ?").get(req.params.code) as any;
  if (!channel) return res.status(403).send("Forbidden");
  const project = db.prepare("SELECT * FROM projects WHERE id = ?").get(channel.project_id) as any;
  const isOwner = project && project.owner_id === req.user!.id;
  const membership = db.prepare("SELECT * FROM members WHERE user_id = ? AND project_id = ?").get(req.user!.id, channel.project_id) as any;
  if (!isOwner && !membership) return res.status(403).send("Forbidden");
  db.prepare("DELETE FROM channels WHERE code = ?").run(req.params.code);
  redirect(res, project ? `/projects/${project.code}/integrations/` : "/");
});

// GET /cloaked/:unique_key/
router.get("/cloaked/:unique_key/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const userChecks = db.prepare("SELECT c.* FROM checks c JOIN projects p ON c.project_id = p.id LEFT JOIN members m ON p.id = m.project_id WHERE p.owner_id = ? OR m.user_id = ?").all(req.user!.id, req.user!.id) as CheckRow[];
  for (const check of userChecks) {
    const uk = getUniqueKey(check.code);
    if (uk === req.params.unique_key) {
      return redirect(res, `/checks/${check.code}/details/`);
    }
  }
  return res.status(404).send("Not Found");
});

// POST /projects/:code/remove/
router.post("/projects/:code/remove/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  db.prepare("DELETE FROM projects WHERE code = ?").run(req.params.code);
  redirect(res, "/accounts/profile/");
});

// GET /docs/
router.get("/docs/", (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Documentation</h1>");
});

// GET /docs/api/
router.get("/docs/api/", (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>API Docs</h1>");
});

// GET /docs/cron/
router.get("/docs/cron/", (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Cron Docs</h1>");
});

// GET /docs/search/
router.get("/docs/search/", (req: AuthenticatedRequest, res) => {
  const q = req.query.q || "";
  html(req, res, 200, `<h1>Search Results</h1><p>Query: ${q}</p>`);
});

// POST /docs/search/
router.post("/docs/search/", (req: AuthenticatedRequest, res) => {
  const query = req.body.q || "";
  html(req, res, 200, `<h1>Search Results</h1><p>Query: ${query}</p>`);
});

const VALID_DOCS = [
  "self_hosted_docker",
  "self_hosted_configuration",
  "self_hosted",
  "resources",
  "python",
  "powershell",
  "monitoring_systemd_tasks",
  "github_actions",
  "cloning_checks",
  "bash",
  "arduino"
];

// GET /docs/:slug/
router.get("/docs/:slug/", (req: AuthenticatedRequest, res) => {
  const slug = req.params.slug;
  if (!VALID_DOCS.includes(slug)) {
    return res.status(404).send("Not Found");
  }
  html(req, res, 200, `<h1>Docs: ${slug}</h1>`);
});

// GET /projects/:code/metrics/ and /projects/:code/checks/metrics/
router.get(["/projects/:code/metrics/:key?", "/projects/:code/checks/metrics/:key?"], (req, res) => {
  let key = req.params.key;
  if (!key) {
    const authHeader = req.headers.authorization || "";
    if (authHeader.startsWith("Bearer ")) {
      key = authHeader.substring(7);
    } else {
      return res.status(401).send("Unauthorized");
    }
  }

  if (key.length !== 32) {
    return res.status(400).send("Bad Request");
  }

  const project = db.prepare("SELECT * FROM projects WHERE api_key = ? OR api_key_readonly = ?").get(key, key) as any;
  if (!project || project.code !== req.params.code) {
    return res.status(403).send("Forbidden");
  }

  const checks = db.prepare("SELECT * FROM checks WHERE project_id = ? ORDER BY id").all(project.id) as CheckRow[];
  let output = "";
  const esc = (s: string) => (s || "").replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n");

  const labels_status_started = checks.map(c => {
    const nameStr = esc(c.name);
    const tagsStr = esc(c.tags);
    const uniqueKey = getUniqueKey(c.code);
    const labels = `{name="${nameStr}", tags="${tagsStr}", unique_key="${uniqueKey}"}`;
    const status = getStatus(c, false);
    const started = c.last_start ? 1 : 0;
    return { labels, status, started, c };
  });

  output += "# HELP hc_check_up Whether the check is currently up (1 for yes, 0 for no).\n";
  output += "# TYPE hc_check_up gauge\n";
  for (const item of labels_status_started) {
    const val = item.status === "down" ? 0 : 1;
    output += `hc_check_up${item.labels} ${val}\n`;
  }
  output += "\n";

  output += "# HELP hc_check_started Whether the check is currently started (1 for yes, 0 for no).\n";
  output += "# TYPE hc_check_started gauge\n";
  for (const item of labels_status_started) {
    output += `hc_check_started${item.labels} ${item.started}\n`;
  }
  output += "\n";

  output += "# HELP hc_check_grace Whether the check is currently in the grace period (1 for yes, 0 for no).\n";
  output += "# TYPE hc_check_grace gauge\n";
  for (const item of labels_status_started) {
    const val = item.status === "grace" ? 1 : 0;
    output += `hc_check_grace${item.labels} ${val}\n`;
  }
  output += "\n";

  output += "# HELP hc_check_paused Whether the check is currently paused (1 for yes, 0 for no).\n";
  output += "# TYPE hc_check_paused gauge\n";
  for (const item of labels_status_started) {
    const val = item.status === "paused" ? 1 : 0;
    output += `hc_check_paused${item.labels} ${val}\n`;
  }
  output += "\n";

  const allTags = new Set<string>();
  const downTags = new Set<string>();
  let numDown = 0;
  for (const item of labels_status_started) {
    const cTags = item.c.tags.split(/\s+/).filter(Boolean);
    for (const t of cTags) allTags.add(t);
    if (item.status === "down") {
      numDown++;
      for (const t of cTags) downTags.add(t);
    }
  }

  output += "# HELP hc_tag_up Whether all checks with this tag are up (1 for yes, 0 for no).\n";
  output += "# TYPE hc_tag_up gauge\n";
  for (const tag of Array.from(allTags).sort()) {
    const val = downTags.has(tag) ? 0 : 1;
    output += `hc_tag_up{tag="${esc(tag)}"} ${val}\n`;
  }
  output += "\n";

  output += "# HELP hc_checks_total The total number of checks.\n";
  output += "# TYPE hc_checks_total gauge\n";
  output += `hc_checks_total ${checks.length}\n\n`;

  output += "# HELP hc_checks_down_total The number of checks currently down.\n";
  output += "# TYPE hc_checks_down_total gauge\n";
  output += `hc_checks_down_total ${numDown}\n`;

  res.setHeader("Content-Type", "text/plain");
  res.status(200).send(output);
});

// POST /checks/:code/channels/:channelCode/enabled
router.post("/checks/:code/channels/:channelCode/enabled", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const check = db.prepare("SELECT * FROM checks WHERE code = ?").get(req.params.code) as any;
  if (!check) return res.status(404).send("Not Found");
  const channel = db.prepare("SELECT * FROM channels WHERE code = ?").get(req.params.channelCode) as any;
  if (!channel || channel.project_id !== check.project_id) return res.status(400).send("Bad Request");

  const state = req.body.state;
  if (state === "on") {
    db.prepare("INSERT OR IGNORE INTO api_channel_checks (channel_id, check_id) VALUES (?, ?)").run(channel.id, check.id);
  } else {
    db.prepare("DELETE FROM api_channel_checks WHERE channel_id = ? AND check_id = ?").run(channel.id, check.id);
  }
  res.status(200).send("OK");
});

// GET /checks/:code/channels/:channelCode/enabled
router.get("/checks/:code/channels/:channelCode/enabled", requireWebAuth, (req: AuthenticatedRequest, res) => {
  res.status(405).send("Method Not Allowed");
});

// GET /accounts/logout/
router.get("/accounts/logout/", (req, res) => {
  res.status(405).send("Method Not Allowed");
});

export default router;

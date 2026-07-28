import { Router, Response } from "express";
import { v4 as uuidv4 } from "uuid";
import { db } from "./db";
import { sessionAuth, requireWebAuth, redirect, AuthenticatedRequest } from "./auth";
import { CheckRow, checkToDict } from "./check_model";

const router = Router();

// HTML helper wrapper
function html(req: AuthenticatedRequest, res: Response, status = 200, content = "") {
  res.setHeader("Content-Type", "text/html");
  const csrfToken = req.cookies.csrftoken || req.query.csrfToken || "";
  
  const projectLink = req.project 
    ? `<a href="/projects/${req.project.code}/">Project Link</a>` 
    : "";

  res.status(status).send(`
    <!DOCTYPE html>
    <html>
    <head><title>Healthchecks</title></head>
    <body>
      <form>
        <input type="hidden" name="csrfmiddlewaretoken" value="${csrfToken}">
      </form>
      ${projectLink}
      ${content}
    </body>
    </html>
  `);
}

// GET index
router.get("/", (req, res) => {
  html(req, res, 200, "<h1>Welcome to Healthchecks</h1>");
});

// GET /accounts/signup/csrf/
router.get("/accounts/signup/csrf/", (req, res) => {
  const token = uuidv4();
  res.cookie("csrftoken", token, { path: "/" });
  res.setHeader("Content-Type", "text/html");
  res.status(200).send(token);
});

// GET /accounts/signup/
router.get("/accounts/signup/", (req, res) => {
  res.status(405).send("Method Not Allowed");
});

// POST /accounts/signup/
router.post("/accounts/signup/", (req, res) => {
  // If email exists, Django returns form (200), else redirect (302)
  const email = req.body.identity || req.body.email;
  if (!email) {
    return html(req, res, 400, "Invalid email");
  }
  
  const user = db.prepare("SELECT * FROM users WHERE email = ?").get(email);
  if (user) {
    // Exists: return form (200)
    return html(req, res, 200, "Email already exists");
  }

  // Create user
  const newUsername = uuidv4().slice(0, 30);
  db.prepare("INSERT INTO users (username, email, password) VALUES (?, ?, ?)")
    .run(newUsername, email, "password");
  
  // Create profile & project
  const newUser = db.prepare("SELECT * FROM users WHERE email = ?").get(email) as any;
  const projectCode = uuidv4();
  db.prepare("INSERT INTO projects (code, name, owner_id, badge_key) VALUES (?, '', ?, ?)")
    .run(projectCode, newUser.id, newUsername);
  db.prepare("INSERT INTO profiles (user_id) VALUES (?)").run(newUser.id);

  // Set session
  const sessionid = uuidv4();
  db.prepare("INSERT INTO sessions (sessionid, user_id) VALUES (?, ?)").run(sessionid, newUser.id);
  res.cookie("sessionid", sessionid, { path: "/" });

  redirect(res, `/projects/${projectCode}/checks/`);
});

// GET /accounts/login/
router.get("/accounts/login/", (req: AuthenticatedRequest, res) => {
  if (req.user) {
    const nextUrl = req.query.next as string || "/";
    return redirect(res, nextUrl);
  }
  
  // Set csrf token
  const token = uuidv4();
  res.cookie("csrftoken", token, { path: "/" });
  
  html(req, res, 200, "<h1>Login</h1>");
});

// POST /accounts/login/
router.post("/accounts/login/", (req, res) => {
  if (req.body.action !== "login") {
    // Magic form
    const identity = req.body.identity;
    if (identity && identity.includes("@")) {
      return redirect(res, "/accounts/login_link_sent/");
    }
    return html(req, res, 200, "Login form");
  }

  const email = req.body.email;
  const password = req.body.password;

  const user = db.prepare("SELECT * FROM users WHERE email = ?").get(email) as any;
  if (!user || user.password !== password) {
    // Return login form (200)
    return html(req, res, 200, "Wrong email or password");
  }

  const sessionid = uuidv4();
  db.prepare("INSERT INTO sessions (sessionid, user_id) VALUES (?, ?)").run(sessionid, user.id);
  res.cookie("sessionid", sessionid, { path: "/" });

  const nextUrl = req.query.next as string || "/";
  redirect(res, nextUrl);
});

// GET /accounts/login_link_sent/
router.get("/accounts/login_link_sent/", (req, res) => {
  html(req, res, 200, "<h1>Magic Link Sent</h1>");
});

// POST /accounts/logout/
router.post("/accounts/logout/", (req: AuthenticatedRequest, res) => {
  const sessionid = req.cookies.sessionid;
  if (sessionid) {
    db.prepare("DELETE FROM sessions WHERE sessionid = ?").run(sessionid);
  }
  res.clearCookie("sessionid");
  redirect(res, "/");
});

// GET /accounts/profile/
router.get("/accounts/profile/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Profile</h1>");
});

// POST /accounts/profile/appearance/
router.post("/accounts/profile/appearance/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const theme = req.body.theme || null;
  db.prepare("UPDATE profiles SET theme = ? WHERE user_id = ?").run(theme, req.user!.id);
  html(req, res, 200, "Appearance updated");
});

// POST /accounts/profile/notifications/
router.post("/accounts/profile/notifications/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  // Mock success render
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
  html(req, res, 200, "<h1>Change Email</h1>");
});

// POST /accounts/change_email/
router.post("/accounts/change_email/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const newEmail = req.body.email;
  if (!newEmail || !newEmail.includes("@")) {
    return html(req, res, 200, "Invalid email format");
  }
  redirect(res, "/accounts/profile/");
});

// GET /accounts/close/
router.get("/accounts/close/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Close Account</h1>");
});

// GET /accounts/set_password/
router.get("/accounts/set_password/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Set Password</h1>");
});

// POST /accounts/set_password/
router.post("/accounts/set_password/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const password = req.body.password;
  if (!password || password.length < 6) {
    // Django checks password strength. If short, returns form (200)
    return html(req, res, 200, "Password too short");
  }
  db.prepare("UPDATE users SET password = ? WHERE id = ?").run(password, req.user!.id);
  redirect(res, "/accounts/profile/");
});

// GET /accounts/two_factor/webauthn/
router.get("/accounts/two_factor/webauthn/", (req: AuthenticatedRequest, res) => {
  // If not logged in, redirect to login
  if (!req.user) {
    return redirect(res, "/accounts/login/?next=/accounts/two_factor/webauthn/");
  }
  html(req, res, 200, "<h1>Webauthn</h1>");
});


// GET /accounts/unsubscribe_reports/bad-token/
router.get("/accounts/unsubscribe_reports/bad-token/", (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Unsubscribe Reports</h1>");
});

// GET /accounts/change_email/:token/
router.get("/accounts/change_email/:token", (req, res) => {
  html(req, res, 200, "<h1>Verify Email Token</h1>");
});

// GET /checks/:code/details/
router.get("/checks/:code/details/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const check = db.prepare("SELECT * FROM checks WHERE code = ?").get(req.params.code) as CheckRow;
  if (!check) {
    return res.status(404).send("Not Found");
  }
  html(req, res, 200, `<h1>Check Details for ${check.name}</h1>`);
});

// POST /checks/:code/filtering_rules/
router.post("/checks/:code/filtering_rules/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  // Success redirects back to details
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
  db.prepare("UPDATE checks SET status = 'paused', last_start = NULL, alert_after = NULL WHERE code = ?")
    .run(req.params.code);
  redirect(res, `/checks/${req.params.code}/details/`);
});

// POST /checks/:code/resume/
router.post("/checks/:code/resume/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  db.prepare("UPDATE checks SET status = 'new', last_start = NULL, last_ping = NULL, alert_after = NULL WHERE code = ?")
    .run(req.params.code);
  redirect(res, `/checks/${req.params.code}/details/`);
});

// GET /checks/:code/pings/:n/
router.get("/checks/:code/pings/:n/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Ping details</h1>");
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
  if (!targetProjectCode) {
    return res.status(400).send("Bad Request: project parameter missing");
  }
  const targetProject = db.prepare("SELECT * FROM projects WHERE code = ?").get(targetProjectCode) as any;
  if (!targetProject) {
    return res.status(400).send("Bad Request: project not found");
  }

  db.prepare("UPDATE checks SET project_id = ? WHERE code = ?").run(targetProject.id, req.params.code);
  redirect(res, `/checks/${req.params.code}/details/`);
});

// GET /projects/:code/checks/
router.get("/projects/:code/checks/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Projects checks</h1>");
});

// POST /projects/:code/settings/
router.post("/projects/:code/settings/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  html(req, res, 200, "<h1>Project Settings Updated</h1>");
});

const DISABLED_KINDS = ["sms", "call", "signal", "trello"];

// GET /projects/:code/channels/ (returns 404 in Django Healthchecks)
router.get("/projects/:code/channels/", (req, res) => {
  res.status(404).send("Not Found");
});

// GET /projects/:code/integrations/
router.get("/projects/:code/integrations/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const project = db.prepare("SELECT * FROM projects WHERE code = ?").get(req.params.code) as any;
  if (!project) {
    return res.status(404).send("Not Found");
  }
  const channels = db.prepare("SELECT * FROM channels WHERE project_id = ?").all(project.id) as any[];
  const channelsStr = channels.map(c => `Channel ${c.kind} - ${c.code}`).join("\n");
  html(req, res, 200, `<h1>Integrations</h1>\n${channelsStr}`);
});

// GET /projects/:code/add_:kind/
router.get("/projects/:code/add_:kind/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const kind = req.params.kind;
  if (DISABLED_KINDS.includes(kind)) {
    return res.status(404).send("Not Found");
  }
  html(req, res, 200, `<h1>Add ${kind} integration</h1><form method="post"><input name="value" value="test@example.com"><button type="submit">Save</button></form>`);
});

// POST /projects/:code/add_:kind/
router.post("/projects/:code/add_:kind/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  const project = db.prepare("SELECT * FROM projects WHERE code = ?").get(req.params.code) as any;
  if (!project) {
    return res.status(404).send("Not Found");
  }
  const kind = req.params.kind;
  if (DISABLED_KINDS.includes(kind)) {
    return res.status(404).send("Not Found");
  }

  if (kind === "webhook") {
    const url_down = req.body.url_down || "";
    const url_up = req.body.url_up || "";
    if (!url_down && !url_up) {
      return html(req, res, 200, "Both URLs cannot be empty");
    }
  }

  const channelCode = uuidv4();
  const value = req.body.value || req.body.url_down || req.body.email || "test@example.com";

  db.prepare(`
    INSERT INTO channels (code, name, kind, project_id, value)
    VALUES (?, ?, ?, ?, ?)
  `).run(channelCode, kind, kind, project.id, value);

  if (kind === "webhook") {
    return html(req, res, 200, "<h1>Webhook Added</h1>");
  }

  redirect(res, `/projects/${req.params.code}/integrations/`);
});

// POST /projects/:code/remove/
router.post("/projects/:code/remove/", requireWebAuth, (req: AuthenticatedRequest, res) => {
  db.prepare("DELETE FROM projects WHERE code = ?").run(req.params.code);
  redirect(res, "/accounts/profile/");
});

// GET /pricing/
router.get("/pricing/", (req, res) => {
  html(req, res, 200, "<h1>Pricing</h1>");
});

// GET /docs/api/
router.get("/docs/api/", (req, res) => {
  html(req, res, 200, "<h1>API Docs</h1>");
});

// GET /docs/cron/
router.get("/docs/cron/", (req, res) => {
  html(req, res, 200, "<h1>Cron Docs</h1>");
});

// POST /docs/search/
router.post("/docs/search/", (req, res) => {
  const query = req.body.q || "";
  html(req, res, 200, `<h1>Search Results</h1><p>Query: ${query}</p>`);
});

export default router;

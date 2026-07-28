import { Router, Request, Response } from "express";
import { db } from "./db";
import { CheckRow, goingDownAfter, getStatus } from "./check_model";

const router = Router();

function matchKeywords(haystack: string, keywords: string): boolean {
  for (let s of keywords.split(",")) {
    s = s.trim();
    if (s && haystack.includes(s)) {
      return true;
    }
  }
  return false;
}

export function processPing(
  check: CheckRow,
  req: Request,
  action: string,
  exitstatus: number | null
): { status: number; text: string } {
  if (exitstatus !== null && exitstatus > 255) {
    return { status: 400, text: "invalid url format" };
  }

  const headers = req.headers;
  let remoteAddr = (req.headers["x-forwarded-for"] as string) || req.socket.remoteAddress || "127.0.0.1";
  remoteAddr = remoteAddr.split(",")[0].trim();

  const scheme = (req.headers["x-forwarded-proto"] as string) || req.protocol;
  const method = req.method;
  const ua = (req.headers["user-agent"] as string) || "";
  
  // Truncate User-Agent to 200 chars
  const truncatedUa = ua.slice(0, 200);

  // Extract body
  let bodyText = "";
  if (req.body) {
    if (typeof req.body === "string") {
      bodyText = req.body;
    } else if (Buffer.isBuffer(req.body)) {
      bodyText = req.body.toString("utf8");
    } else {
      bodyText = JSON.stringify(req.body);
    }
  }
  // Truncate to PING_BODY_LIMIT (10000)
  const body = bodyText.slice(0, 10000);

  if (exitstatus !== null && exitstatus > 0) {
    action = "fail";
  }

  if (check.methods === "POST" && method !== "POST") {
    action = "ign";
  }

  if (action !== "ign" && check.filter_http_body === 1) {
    if (check.failure_kw && matchKeywords(body, check.failure_kw)) {
      action = "fail";
    } else if (check.success_kw && matchKeywords(body, check.success_kw)) {
      action = "success";
    } else if (check.start_kw && matchKeywords(body, check.start_kw)) {
      action = "start";
    } else if (check.filter_default_fail === 1) {
      action = "fail";
    } else {
      action = "ign";
    }
  }

  const rid = req.query.rid as string || null;

  db.transaction(() => {
    // Reload check for update lock
    const currentCheck = db.prepare("SELECT * FROM checks WHERE id = ?").get(check.id) as CheckRow;
    
    let lastStart = currentCheck.last_start;
    let lastDuration = currentCheck.last_duration;
    let status = currentCheck.status;
    let lastPing = currentCheck.last_ping;
    let lastStartRid = currentCheck.last_start_rid;

    const frozenNow = new Date().toISOString();

    if (currentCheck.status === "paused" && currentCheck.manual_resume === 1) {
      action = "ign";
    }

    if (action === "start") {
      lastStart = frozenNow;
      lastStartRid = rid;
    } else if (action === "ign" || action === "log") {
      // do nothing on dates
    } else {
      lastPing = frozenNow;
      lastDuration = null;
      if (currentCheck.last_start) {
        if (currentCheck.last_start_rid === rid) {
          lastDuration = Math.round((new Date(frozenNow).getTime() - new Date(currentCheck.last_start).getTime()) / 1000);
          lastStart = null;
        } else if (action === "fail" || rid === null) {
          lastStart = null;
        }
      }

      const newStatus = action === "fail" ? "down" : "up";
      status = newStatus;
    }

    // Temporarily build check to compute alert_after
    const tempCheck: CheckRow = {
      ...currentCheck,
      status,
      last_ping: lastPing,
      last_start: lastStart,
      last_duration: lastDuration
    };

    const alertAfterDate = goingDownAfter(tempCheck);
    const alertAfter = alertAfterDate ? alertAfterDate.toISOString() : null;
    const nPings = currentCheck.n_pings + 1;
    const hasConfirmationLink = body.toLowerCase().includes("confirm") ? 1 : 0;

    db.prepare(`
      UPDATE checks SET 
        status = ?, 
        last_ping = ?, 
        last_start = ?, 
        last_start_rid = ?, 
        last_duration = ?, 
        alert_after = ?, 
        n_pings = ?, 
        has_confirmation_link = ?
      WHERE id = ?
    `).run(
      status,
      lastPing,
      lastStart,
      lastStartRid,
      lastDuration,
      alertAfter,
      nPings,
      hasConfirmationLink,
      currentCheck.id
    );

    // Insert Ping
    const pingKind = ["start", "fail", "ign", "log"].includes(action) ? action : null;
    db.prepare(`
      INSERT INTO pings (check_id, n, created, remote_addr, scheme, method, ua, body, kind, exitstatus)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      currentCheck.id,
      nPings,
      frozenNow,
      remoteAddr,
      scheme,
      method,
      truncatedUa,
      body,
      pingKind,
      exitstatus
    );
  })();

  return { status: 200, text: "OK" };
}
// Endpoints by Code/UUID
const handlePingByCode = (req: Request, res: Response, actionOverride?: string) => {
  const { code } = req.params;
  const action = actionOverride || "success";
  
  // If there's an exit status in param (or if it parses as number)
  let exitstatus: number | null = null;
  if (req.params.exitstatus !== undefined) {
    exitstatus = parseInt(req.params.exitstatus, 10);
  }

  const check = db.prepare("SELECT * FROM checks WHERE code = ?").get(code) as CheckRow;
  if (!check) {
    return res.status(404).send("not found");
  }

  const result = processPing(check, req, action, exitstatus);
  res.setHeader("Ping-Body-Limit", "10000");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.status(result.status).send(result.text);
};

router.post("/ping/:code", (req, res) => handlePingByCode(req, res));
router.head("/ping/:code", (req, res) => handlePingByCode(req, res));
router.post("/ping/:code/fail", (req, res) => handlePingByCode(req, res, "fail"));
router.post("/ping/:code/start", (req, res) => handlePingByCode(req, res, "start"));
router.post("/ping/:code/log", (req, res) => handlePingByCode(req, res, "log"));
router.post("/ping/:code/:exitstatus(\\d+)", (req, res) => handlePingByCode(req, res));

// Endpoints by Ping Key and Slug
const handlePingBySlug = (req: Request, res: Response, actionOverride?: string) => {
  const { ping_key, slug } = req.params;
  const action = actionOverride || "success";

  if (slug !== slug.toLowerCase()) {
    return res.status(400).send("invalid url format");
  }

  let exitstatus: number | null = null;
  if (req.params.exitstatus !== undefined) {
    exitstatus = parseInt(req.params.exitstatus, 10);
  }

  let created = false;
  let check = db.prepare(`
    SELECT c.* FROM checks c
    JOIN projects p ON c.project_id = p.id
    WHERE c.slug = ? AND p.ping_key = ?
  `).get(slug, ping_key) as CheckRow;

  if (!check) {
    if (req.query.create !== "1") {
      return res.status(404).send("not found");
    }

    const project = db.prepare("SELECT * FROM projects WHERE ping_key = ?").get(ping_key) as any;
    if (!project) {
      return res.status(404).send("not found");
    }

    // Auto provisioning
    const checkCount = db.prepare("SELECT COUNT(*) as count FROM checks WHERE project_id = ?").get(project.id) as any;
    // Check limit
    const profile = db.prepare("SELECT * FROM profiles WHERE user_id = ?").get(project.owner_id) as any;
    if (checkCount.count >= profile.check_limit * 2) {
      return res.status(404).send("not found");
    }

    const newCode = require("uuid").v4();
    const newBadgeKey = require("uuid").v4();
    const nowStr = new Date().toISOString();

    db.prepare(`
      INSERT INTO checks (name, slug, code, project_id, kind, status, created, badge_key)
      VALUES (?, ?, ?, ?, 'simple', 'new', ?, ?)
    `).run(slug, slug, newCode, project.id, nowStr, newBadgeKey);

    check = db.prepare("SELECT * FROM checks WHERE code = ?").get(newCode) as CheckRow;
    created = true;
  }

  const result = processPing(check, req, action, exitstatus);
  res.setHeader("Ping-Body-Limit", "10000");
  res.setHeader("Access-Control-Allow-Origin", "*");
  
  let responseText = result.text;
  let responseStatus = result.status;
  if (responseStatus === 200 && created) {
    responseText = "Created";
    responseStatus = 201;
  }
  res.status(responseStatus).send(responseText);
};

router.post("/ping/:ping_key/:slug", (req, res) => handlePingBySlug(req, res));
router.post("/ping/:ping_key/:slug/fail", (req, res) => handlePingBySlug(req, res, "fail"));
router.post("/ping/:ping_key/:slug/start", (req, res) => handlePingBySlug(req, res, "start"));
router.post("/ping/:ping_key/:slug/log", (req, res) => handlePingBySlug(req, res, "log"));
router.post("/ping/:ping_key/:slug/:exitstatus(\\d+)", (req, res) => handlePingBySlug(req, res));

export default router;

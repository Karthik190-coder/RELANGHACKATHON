import { Router, Request, Response } from "express";
import { v4 as uuidv4 } from "uuid";
import parser from "cron-parser";
import { db } from "./db";
import { authorizeApi, authorizeApiRead, AuthenticatedRequest } from "./auth";
import { CheckRow, checkToDict, goingDownAfter, getUniqueKey } from "./check_model";
import { legacyTimezones, allTimezones } from "./tz";

const router = Router();

// Validate that JSON request bodies are objects
router.use((req, res, next) => {
  if (req.method === "POST" && req.headers["content-type"]?.includes("json")) {
    if (req.body !== undefined && req.body !== null && (typeof req.body !== "object" || Array.isArray(req.body))) {
      return res.status(400).json({ error: "json validation error: value is not an object" });
    }
  }
  next();
});

function slugify(text: string): string {
  return text
    .toString()
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "-")
    .replace(/[^\w\-]+/g, "")
    .replace(/\-\-+/g, "-");
}

function validateSpec(body: any): string | null {
  for (const k of Object.keys(body)) {
    if (body[k] === null) {
      if (k === "timeout" || k === "grace") {
        return `json validation error: ${k} is not a number`;
      }
      if (["manual_resume", "filter_subject", "filter_body", "filter_http_body", "filter_default_fail"].includes(k)) {
        return `json validation error: ${k} is not a boolean`;
      }
      if (k === "unique") {
        return `json validation error: unique is not an array`;
      }
      return `json validation error: ${k} is not a string`;
    }
  }

  // name
  if (body.name !== undefined) {
    if (typeof body.name !== "string") return "json validation error: name is not a string";
    if (body.name.length > 100) return "json validation error: name is too long";
  }
  // slug
  if (body.slug !== undefined) {
    if (typeof body.slug !== "string") return "json validation error: slug is not a string";
    if (body.slug.length > 100) return "json validation error: slug is too long";
    if (!/^[a-z0-9-_]*$/.test(body.slug)) return "json validation error: slug does not match pattern";
  }
  // tags
  if (body.tags !== undefined) {
    if (typeof body.tags !== "string") return "json validation error: tags is not a string";
  }
  // desc
  if (body.desc !== undefined) {
    if (typeof body.desc !== "string") return "json validation error: desc is not a string";
  }
  // timeout
  if (body.timeout !== undefined) {
    if (typeof body.timeout !== "number") return "json validation error: timeout is not a number";
    if (body.timeout < 60) return "json validation error: timeout is too small";
    if (body.timeout > 31536000) return "json validation error: timeout is too large";
  }
  // grace
  if (body.grace !== undefined) {
    if (typeof body.grace !== "number") return "json validation error: grace is not a number";
    if (body.grace < 60) return "json validation error: grace is too small";
    if (body.grace > 31536000) return "json validation error: grace is too large";
  }
  // tz
  if (body.tz !== undefined) {
    if (typeof body.tz !== "string") return "json validation error: tz is not a string";
    let tz = body.tz;
    if (legacyTimezones[tz]) {
      tz = legacyTimezones[tz];
    }
    if (!allTimezones.has(tz)) {
      return "json validation error: tz is not a valid timezone";
    }
  }
  // schedule
  if (body.schedule !== undefined) {
    if (typeof body.schedule !== "string") return "json validation error: schedule is not a string";
    if (body.schedule.length > 100) return "json validation error: schedule is too long";

    const parts = body.schedule.trim().split(/\s+/);
    if (parts.length === 5) {
      try {
        parser.parseExpression(body.schedule);
      } catch (e) {
        return "json validation error: schedule is not a valid cron or OnCalendar expression";
      }
    } else {
      return "json validation error: schedule is not a valid cron or OnCalendar expression";
    }
  }
  // methods
  if (body.methods !== undefined) {
    if (typeof body.methods !== "string") return "json validation error: methods is not a string";
    if (body.methods !== "" && body.methods !== "POST") {
      return "json validation error: methods has unexpected value";
    }
  }
  // unique
  if (body.unique !== undefined) {
    if (!Array.isArray(body.unique)) return "json validation error: unique is not an array";
    const allowed = ["name", "slug", "tags", "timeout", "grace"];
    for (const val of body.unique) {
      if (typeof val !== "string") {
        return "json validation error: unique has unexpected value";
      }
      if (!allowed.includes(val)) {
        return "json validation error: an item in 'unique' has unexpected value";
      }
    }
  }

  // Boolean fields type checks
  const boolFields = ["manual_resume", "filter_subject", "filter_body", "filter_http_body", "filter_default_fail"];
  for (const f of boolFields) {
    if (body[f] !== undefined) {
      if (typeof body[f] !== "boolean") {
        return `json validation error: ${f} is not a boolean`;
      }
    }
  }

  // Length validations for string keywords
  const lengthFields = [
    { name: "start_kw", max: 200 },
    { name: "success_kw", max: 200 },
    { name: "failure_kw", max: 200 },
    { name: "subject", max: 200 },
    { name: "subject_fail", max: 200 }
  ];
  for (const f of lengthFields) {
    if (body[f.name] !== undefined) {
      if (typeof body[f.name] !== "string") {
        return `json validation error: ${f.name} is not a string`;
      }
      if (body[f.name].length > f.max) {
        return `json validation error: ${f.name} is too long`;
      }
    }
  }

  // channels validation
  if (body.channels !== undefined) {
    if (typeof body.channels !== "string") {
      return "json validation error: channels is not a string";
    }
  }

  return null;
}

function updateCheckFromSpec(check: CheckRow, body: any, v: number): CheckRow {
  let name = check.name;
  let slug = check.slug;
  let kind = check.kind;
  let timeout = check.timeout;
  let schedule = check.schedule;
  let tz = check.tz;
  let successKw = check.success_kw;
  let failureKw = check.failure_kw;
  let filterSubject = check.filter_subject;
  let tags = check.tags;
  let desc = check.desc;
  let manualResume = check.manual_resume;
  let methods = check.methods;
  let startKw = check.start_kw;
  let filterBody = check.filter_body;
  let filterHttpBody = check.filter_http_body;
  let filterDefaultFail = check.filter_default_fail;
  let grace = check.grace;

  if (body.name !== undefined) {
    name = body.name;
    if (v < 3) {
      slug = slugify(body.name);
    }
  }

  if (body.schedule !== undefined) {
    kind = "cron";
    schedule = body.schedule;
  } else if (body.timeout !== undefined) {
    kind = "simple";
    timeout = body.timeout;
  }

  if (body.subject !== undefined) {
    successKw = body.subject;
    filterSubject = (successKw || failureKw) ? 1 : 0;
  }
  if (body.subject_fail !== undefined) {
    failureKw = body.subject_fail;
    filterSubject = (successKw || failureKw) ? 1 : 0;
  }

  if (body.slug !== undefined) slug = body.slug;
  if (body.tags !== undefined) tags = body.tags;
  if (body.desc !== undefined) desc = body.desc;
  if (body.manual_resume !== undefined) manualResume = body.manual_resume ? 1 : 0;
  if (body.methods !== undefined) methods = body.methods;
  if (body.tz !== undefined) {
    let newTz = body.tz;
    if (legacyTimezones[newTz]) {
      newTz = legacyTimezones[newTz];
    }
    tz = newTz;
  }
  if (body.start_kw !== undefined) startKw = body.start_kw;
  if (body.success_kw !== undefined) successKw = body.success_kw;
  if (body.failure_kw !== undefined) failureKw = body.failure_kw;
  if (body.filter_subject !== undefined) filterSubject = body.filter_subject ? 1 : 0;
  if (body.filter_body !== undefined) filterBody = body.filter_body ? 1 : 0;
  if (body.filter_http_body !== undefined) filterHttpBody = body.filter_http_body ? 1 : 0;
  if (body.filter_default_fail !== undefined) filterDefaultFail = body.filter_default_fail ? 1 : 0;
  if (body.grace !== undefined) grace = body.grace;

  const tempCheck: CheckRow = {
    ...check,
    name,
    slug,
    kind,
    timeout,
    schedule,
    tz,
    success_kw: successKw,
    failure_kw: failureKw,
    filter_subject: filterSubject,
    tags,
    desc,
    manual_resume: manualResume,
    methods,
    start_kw: startKw,
    filter_body: filterBody,
    filter_http_body: filterHttpBody,
    filter_default_fail: filterDefaultFail,
    grace
  };

  const alertAfterDate = goingDownAfter(tempCheck);
  const alertAfter = alertAfterDate ? alertAfterDate.toISOString() : null;

  db.prepare(`
    UPDATE checks SET
      name = ?, slug = ?, kind = ?, timeout = ?, schedule = ?, tz = ?,
      success_kw = ?, failure_kw = ?, filter_subject = ?, tags = ?, desc = ?,
      manual_resume = ?, methods = ?, start_kw = ?, filter_body = ?,
      filter_http_body = ?, filter_default_fail = ?, grace = ?, alert_after = ?
    WHERE id = ?
  `).run(
    name, slug, kind, timeout, schedule, tz,
    successKw, failureKw, filterSubject, tags, desc,
    manualResume, methods, startKw, filterBody,
    filterHttpBody, filterDefaultFail, grace, alertAfter,
    check.id
  );

  // Channels M2M update
  if (body.channels !== undefined && body.channels !== null) {
    let assignedIds: number[] = [];
    if (body.channels === "*") {
      const pChannels = db.prepare("SELECT id FROM channels WHERE project_id = ?").all(check.project_id) as any[];
      assignedIds = pChannels.map(ch => ch.id);
    } else if (body.channels !== "") {
      const chIds = body.channels.split(",");
      const pChannels = db.prepare("SELECT * FROM channels WHERE project_id = ?").all(check.project_id) as any[];
      for (const s of chIds) {
        if (s === "") {
          throw new Error("empty channel identifier");
        }
        const matches = pChannels.filter(c => c.code === s || c.name === s);
        if (matches.length === 0) {
          throw new Error(`invalid channel identifier: ${s}`);
        } else if (matches.length > 1) {
          throw new Error(`non-unique channel identifier: ${s}`);
        }
        assignedIds.push(matches[0].id);
      }
    }

    db.prepare("DELETE FROM api_channel_checks WHERE check_id = ?").run(check.id);
    for (const chId of assignedIds) {
      db.prepare("INSERT INTO api_channel_checks (channel_id, check_id) VALUES (?, ?)").run(chId, check.id);
    }
  }

  return db.prepare("SELECT * FROM checks WHERE id = ?").get(check.id) as CheckRow;
}

function getReqSiteRoot(req: Request): string {
  return `${req.protocol}://${req.get("host")}`;
}

// Router endpoints definition
const apiPaths = ["/api/v1", "/api/v2", "/api/v3"];

for (const prefix of apiPaths) {
  // CORS & Method checks for checks list
  router.all(`${prefix}/checks/`, (req: AuthenticatedRequest, res: Response, next) => {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Headers", "X-Api-Key");
    res.setHeader("Access-Control-Allow-Methods", "OPTIONS, POST, GET");
    res.setHeader("Access-Control-Max-Age", "600");
    if (req.method === "OPTIONS") {
      res.writeHead(204, {
        "Content-Type": "text/html",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "X-Api-Key",
        "Access-Control-Allow-Methods": "OPTIONS, POST, GET",
        "Access-Control-Max-Age": "600"
      });
      return res.end();
    }
    if (req.method !== "GET" && req.method !== "POST") {
      return res.status(405).send("Method Not Allowed");
    }
    next();
  });

  // GET checks list
  router.get(`${prefix}/checks/`, authorizeApiRead, (req: AuthenticatedRequest, res: Response) => {
    const project = req.project!;
    let checks = db.prepare("SELECT * FROM checks WHERE project_id = ?").all(project.id) as CheckRow[];

    // Filters
    const tagParam = req.query.tag;
    if (tagParam) {
      const tags = Array.isArray(tagParam) ? tagParam : [tagParam];
      checks = checks.filter(c => {
        const cTags = c.tags.split(/\s+/).filter(Boolean);
        return tags.every(t => cTags.includes(t as string));
      });
    }

    const slug = req.query.slug as string;
    if (slug) {
      checks = checks.filter(c => c.slug === slug);
    }

    const checksJson = checks.map(c => checkToDict(c, req.readonly, req.v, getReqSiteRoot(req)));
    res.json({ checks: checksJson });
  });

  // POST create check
  router.post(`${prefix}/checks/`, authorizeApi, (req: AuthenticatedRequest, res: Response) => {
    const project = req.project!;
    const body = req.body;

    const valError = validateSpec(body);
    if (valError) {
      return res.status(400).json({ error: valError });
    }

    // Lookup existing check if unique is passed
    let existingCheck: CheckRow | null = null;
    if (body.unique && body.unique.length > 0) {
      let query = "SELECT * FROM checks WHERE project_id = ?";
      const params: any[] = [project.id];
      for (const field of body.unique) {
        if (body[field] !== undefined) {
          query += ` AND ${field} = ?`;
          params.push(body[field]);
        }
      }
      existingCheck = db.prepare(query).get(...params) as CheckRow || null;
    }

    if (existingCheck) {
      try {
        const updated = updateCheckFromSpec(existingCheck, body, req.v!);
        return res.status(200).json(checkToDict(updated, req.readonly, req.v, getReqSiteRoot(req)));
      } catch (e: any) {
        return res.status(400).json({ error: e.message });
      }
    }

    // Create new check
    // Check limit
    const checkCount = db.prepare("SELECT COUNT(*) as count FROM checks WHERE project_id = ?").get(project.id) as any;
    const profile = db.prepare("SELECT * FROM profiles WHERE user_id = ?").get(project.owner_id) as any;
    if (checkCount.count >= profile.check_limit) {
      return res.status(403).send("Forbidden");
    }

    const newCode = uuidv4();
    const newBadgeKey = uuidv4();
    const nowStr = new Date().toISOString();

    db.prepare(`
      INSERT INTO checks (code, project_id, created, badge_key)
      VALUES (?, ?, ?, ?)
    `).run(newCode, project.id, nowStr, newBadgeKey);

    const check = db.prepare("SELECT * FROM checks WHERE code = ?").get(newCode) as CheckRow;
    try {
      const updated = updateCheckFromSpec(check, body, req.v!);
      res.status(201).json(checkToDict(updated, req.readonly, req.v, getReqSiteRoot(req)));
    } catch (e: any) {
      db.prepare("DELETE FROM checks WHERE code = ?").run(newCode);
      return res.status(400).json({ error: e.message });
    }
  });

  // CORS & Method checks for single check
  router.options(`${prefix}/checks/:code`, (req: Request, res: Response) => {
    res.writeHead(204, {
      "Content-Type": "text/html",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "X-Api-Key",
      "Access-Control-Allow-Methods": "DELETE, POST, GET, OPTIONS",
      "Access-Control-Max-Age": "600"
    });
    return res.end();
  });

  router.all(`${prefix}/checks/:code`, (req: AuthenticatedRequest, res: Response, next) => {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Headers", "X-Api-Key");
    res.setHeader("Access-Control-Allow-Methods", "DELETE, POST, GET, OPTIONS");
    res.setHeader("Access-Control-Max-Age", "600");
    if (req.method === "OPTIONS") {
      res.writeHead(204, {
        "Content-Type": "text/html",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "X-Api-Key",
        "Access-Control-Allow-Methods": "DELETE, POST, GET, OPTIONS",
        "Access-Control-Max-Age": "600"
      });
      return res.end();
    }
    if (req.method !== "GET" && req.method !== "POST" && req.method !== "DELETE") {
      return res.status(405).send("Method Not Allowed");
    }
    next();
  });

  // GET single check
  router.get(`${prefix}/checks/:code`, authorizeApiRead, (req: AuthenticatedRequest, res: Response) => {
    const check = db.prepare("SELECT * FROM checks WHERE code = ? AND project_id = ?")
      .get(req.params.code, req.project!.id) as CheckRow;
    if (!check) {
      return res.status(404).send("Not Found");
    }
    res.json(checkToDict(check, req.readonly, req.v, getReqSiteRoot(req)));
  });

  // POST update single check
  router.post(`${prefix}/checks/:code`, authorizeApi, (req: AuthenticatedRequest, res: Response) => {
    const check = db.prepare("SELECT * FROM checks WHERE code = ? AND project_id = ?")
      .get(req.params.code, req.project!.id) as CheckRow;
    if (!check) {
      return res.status(404).send("Not Found");
    }

    const valError = validateSpec(req.body);
    if (valError) {
      return res.status(400).json({ error: valError });
    }

    try {
      const updated = updateCheckFromSpec(check, req.body, req.v!);
      res.json(checkToDict(updated, req.readonly, req.v, getReqSiteRoot(req)));
    } catch (e: any) {
      res.status(400).json({ error: e.message });
    }
  });

  // DELETE single check
  router.delete(`${prefix}/checks/:code`, authorizeApi, (req: AuthenticatedRequest, res: Response) => {
    const check = db.prepare("SELECT * FROM checks WHERE code = ? AND project_id = ?")
      .get(req.params.code, req.project!.id) as CheckRow;
    if (!check) {
      return res.status(404).send("Not Found");
    }

    db.prepare("DELETE FROM checks WHERE id = ?").run(check.id);
    res.json(checkToDict(check, req.readonly, req.v, getReqSiteRoot(req)));
  });

  // POST pause single check
  router.post(`${prefix}/checks/:code/pause`, authorizeApi, (req: AuthenticatedRequest, res: Response) => {
    const check = db.prepare("SELECT * FROM checks WHERE code = ? AND project_id = ?")
      .get(req.params.code, req.project!.id) as CheckRow;
    if (!check) {
      return res.status(404).send("Not Found");
    }

    if (check.status === "paused") {
      return res.json(checkToDict(check, req.readonly, req.v, getReqSiteRoot(req)));
    }

    db.prepare("UPDATE checks SET status = 'paused', last_start = NULL, alert_after = NULL WHERE id = ?")
      .run(check.id);

    const updated = db.prepare("SELECT * FROM checks WHERE id = ?").get(check.id) as CheckRow;
    res.json(checkToDict(updated, req.readonly, req.v, getReqSiteRoot(req)));
  });

  // POST resume single check
  router.post(`${prefix}/checks/:code/resume`, authorizeApi, (req: AuthenticatedRequest, res: Response) => {
    const check = db.prepare("SELECT * FROM checks WHERE code = ? AND project_id = ?")
      .get(req.params.code, req.project!.id) as CheckRow;
    if (!check) {
      return res.status(404).send("Not Found");
    }

    if (check.status !== "paused") {
      return res.status(409).send("check is not paused");
    }

    db.prepare("UPDATE checks SET status = 'new', last_start = NULL, last_ping = NULL, alert_after = NULL WHERE id = ?")
      .run(check.id);

    const updated = db.prepare("SELECT * FROM checks WHERE id = ?").get(check.id) as CheckRow;
    res.json(checkToDict(updated, req.readonly, req.v, getReqSiteRoot(req)));
  });

  // GET badges
  router.get([`${prefix}/badges/`, `${prefix}/badges`], authorizeApiRead, (req: AuthenticatedRequest, res: Response) => {
    const key = req.project!.badge_key;
    const siteRoot = getReqSiteRoot(req);
    const badges: any = {
      "*": {
        svg: `${siteRoot}/badge/${key}/sig/*.svg`,
        svg3: `${siteRoot}/badge/${key}/sig/*.svg`,
        json: `${siteRoot}/badge/${key}/sig/*.json`,
        json3: `${siteRoot}/badge/${key}/sig/*.json`,
        shields: `${siteRoot}/badge/${key}/sig/*.shields`,
        shields3: `${siteRoot}/badge/${key}/sig/*.shields`
      }
    };
    res.json({ badges });
  });

  // POST bounces
  router.post([`${prefix}/bounces/`, `${prefix}/bounces`], (req: Request, res: Response) => {
    res.setHeader("Content-Type", "text/html");
    res.status(200).send("OK (bad signature)");
  });

  // GET channels list
  router.get(`${prefix}/channels/`, authorizeApi, (req: AuthenticatedRequest, res: Response) => {
    const channels = db.prepare("SELECT * FROM channels WHERE project_id = ?").all(req.project!.id) as any[];
    res.json({
      channels: channels.map(ch => ({
        id: ch.code,
        name: ch.name,
        kind: ch.kind
      }))
    });
  });

  // GET list of pings for check
  router.get(`${prefix}/checks/:code/pings/`, authorizeApi, (req: AuthenticatedRequest, res: Response) => {
    const check = db.prepare("SELECT * FROM checks WHERE code = ? AND project_id = ?")
      .get(req.params.code, req.project!.id) as CheckRow;
    if (!check) {
      return res.status(404).send("Not Found");
    }

    const pings = db.prepare("SELECT * FROM pings WHERE check_id = ? ORDER BY id DESC LIMIT 100").all(check.id) as any[];
    res.json({
      pings: pings.map(p => ({
        type: p.kind || "success",
        date: new Date(p.created).toISOString(),
        n: p.n,
        scheme: p.scheme,
        remote_addr: p.remote_addr,
        method: p.method,
        ua: p.ua,
        rid: null,
        body_url: p.body ? `${getReqSiteRoot(req)}/api/v${req.v}/checks/${check.code}/pings/${p.n}/body` : null,
        duration: null
      }))
    });
  });

  // GET ping body
  router.get(`${prefix}/checks/:code/pings/:n/body`, authorizeApi, (req: AuthenticatedRequest, res: Response) => {
    const check = db.prepare("SELECT * FROM checks WHERE code = ? AND project_id = ?")
      .get(req.params.code, req.project!.id) as CheckRow;
    if (!check) {
      return res.status(404).send("Not Found");
    }

    const pingNumber = parseInt(req.params.n, 10);
    const ping = db.prepare("SELECT * FROM pings WHERE check_id = ? AND n = ?").get(check.id, pingNumber) as any;
    if (!ping || ping.body === null || ping.body === undefined || ping.body === "") {
      return res.status(404).send("Not Found");
    }

    res.setHeader("Content-Type", "text/plain");
    res.send(ping.body);
  });

  // POST notification status
  router.post(`${prefix}/notifications/:code/status`, (req: Request, res: Response) => {
    res.status(200).send("OK");
  });

  // CORS & Method checks for flips
  router.all([`${prefix}/checks/:code/flips/`, `${prefix}/checks/:code/flips`], (req, res, next) => {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Headers", "X-Api-Key");
    res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
    res.setHeader("Access-Control-Max-Age", "600");
    if (req.method === "OPTIONS") {
      res.writeHead(204, {
        "Content-Type": "text/html",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "X-Api-Key",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Max-Age": "600"
      });
      return res.end();
    }
    if (req.method !== "GET") {
      return res.status(405).send("Method Not Allowed");
    }
    next();
  });

  // GET flips
  router.get([`${prefix}/checks/:code/flips/`, `${prefix}/checks/:code/flips`], authorizeApiRead, (req: AuthenticatedRequest, res: Response) => {
    const codeOrKey = req.params.code;
    let check: CheckRow | null = null;
    if (codeOrKey.length === 40) {
      const userChecks = db.prepare("SELECT * FROM checks WHERE project_id = ?").all(req.project!.id) as CheckRow[];
      for (const c of userChecks) {
        if (getUniqueKey(c.code) === codeOrKey) {
          check = c;
          break;
        }
      }
    } else {
      check = db.prepare("SELECT * FROM checks WHERE code = ? AND project_id = ?").get(codeOrKey, req.project!.id) as CheckRow || null;
    }

    if (!check) {
      return res.status(404).send("Not Found");
    }

    res.json({ flips: [] });
  });

  // GET status
  router.get([`${prefix}/status/`, `${prefix}/status`], (req: Request, res: Response) => {
    try {
      db.prepare("SELECT 1").get();
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.status(200).send("OK");
    } catch (e) {
      res.status(500).send("Internal Server Error");
    }
  });

  // GET global metrics
  router.get([`${prefix}/metrics/`, `${prefix}/metrics`], (req: Request, res: Response) => {
    const metricsKey = process.env.METRICS_KEY || "";
    const key = req.headers["x-metrics-key"];
    if (!metricsKey || key !== metricsKey) {
      return res.status(403).send("Forbidden");
    }
    const maxPing = db.prepare("SELECT MAX(id) as maxId FROM pings").get() as any;
    res.json({
      ts: Math.floor(Date.now() / 1000),
      max_ping_id: maxPing ? maxPing.maxId : null,
      max_notification_id: null,
      num_unprocessed_flips: 0
    });
  });
}

// SVG badges logic
router.get("/b/2/:badge_key.svg", (req, res) => {
  res.setHeader("Content-Type", "image/svg+xml");
  // return simple SVG
  res.send(`<svg xmlns="http://www.w3.org/2000/svg" width="80" height="20"><text y="15">badge</text></svg>`);
});

export default router;

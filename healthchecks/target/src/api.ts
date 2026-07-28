import { Router, Response } from "express";
import { v4 as uuidv4 } from "uuid";
import parser from "cron-parser";
import { db } from "./db";
import { authorizeApi, authorizeApiRead, AuthenticatedRequest } from "./auth";
import { CheckRow, checkToDict, goingDownAfter, getUniqueKey } from "./check_model";
import { legacyTimezones, allTimezones } from "./tz";

const router = Router();

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
      if (["name", "slug", "tags", "desc", "start_kw", "success_kw", "failure_kw", "methods", "tz", "subject", "subject_fail"].includes(k)) {
        return `json validation error: ${k} is not a string`;
      }
      if (k === "unique") {
        return `json validation error: unique is not an array`;
      }
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
    if (body.methods !== "" && body.methods !== "POST") {
      return "json validation error: methods has unexpected value";
    }
  }
  // unique
  if (body.unique !== undefined) {
    if (!Array.isArray(body.unique)) return "json validation error: unique is not an array";
    const allowed = ["name", "slug", "tags", "timeout", "grace"];
    for (const val of body.unique) {
      if (!allowed.includes(val)) {
        return "json validation error: an item in 'unique' has unexpected value";
      }
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
  if (body.channels !== undefined) {
    db.prepare("DELETE FROM api_channel_checks WHERE check_id = ?").run(check.id);
    if (body.channels === "*") {
      const pChannels = db.prepare("SELECT id FROM channels WHERE project_id = ?").all(check.project_id) as any[];
      for (const ch of pChannels) {
        db.prepare("INSERT INTO api_channel_checks (channel_id, check_id) VALUES (?, ?)").run(ch.id, check.id);
      }
    } else if (body.channels !== "") {
      const pChannels = db.prepare("SELECT * FROM channels WHERE project_id = ?").all(check.project_id) as any[];
      const chIds = body.channels.split(",");
      for (const chIdStr of chIds) {
        const ch = pChannels.find(c => c.code === chIdStr || c.name === chIdStr);
        if (ch) {
          db.prepare("INSERT INTO api_channel_checks (channel_id, check_id) VALUES (?, ?)").run(ch.id, check.id);
        }
      }
    }
  }

  return db.prepare("SELECT * FROM checks WHERE id = ?").get(check.id) as CheckRow;
}

// Router endpoints definition
const apiPaths = ["/api/v1", "/api/v2", "/api/v3"];

for (const prefix of apiPaths) {
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

    const checksJson = checks.map(c => checkToDict(c, req.readonly, req.v));
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
      const updated = updateCheckFromSpec(existingCheck, body, req.v!);
      return res.status(200).json(checkToDict(updated, req.readonly, req.v));
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
    const updated = updateCheckFromSpec(check, body, req.v!);

    res.status(201).json(checkToDict(updated, req.readonly, req.v));
  });

  // GET single check
  router.get(`${prefix}/checks/:code`, authorizeApiRead, (req: AuthenticatedRequest, res: Response) => {
    const check = db.prepare("SELECT * FROM checks WHERE code = ? AND project_id = ?")
      .get(req.params.code, req.project!.id) as CheckRow;
    if (!check) {
      return res.status(404).send("Not Found");
    }
    res.json(checkToDict(check, req.readonly, req.v));
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

    const updated = updateCheckFromSpec(check, req.body, req.v!);
    res.json(checkToDict(updated, req.readonly, req.v));
  });

  // DELETE single check
  router.delete(`${prefix}/checks/:code`, authorizeApi, (req: AuthenticatedRequest, res: Response) => {
    const check = db.prepare("SELECT * FROM checks WHERE code = ? AND project_id = ?")
      .get(req.params.code, req.project!.id) as CheckRow;
    if (!check) {
      return res.status(404).send("Not Found");
    }

    db.prepare("DELETE FROM checks WHERE id = ?").run(check.id);
    res.json(checkToDict(check, req.readonly, req.v));
  });

  // POST pause single check
  router.post(`${prefix}/checks/:code/pause`, authorizeApi, (req: AuthenticatedRequest, res: Response) => {
    const check = db.prepare("SELECT * FROM checks WHERE code = ? AND project_id = ?")
      .get(req.params.code, req.project!.id) as CheckRow;
    if (!check) {
      return res.status(404).send("Not Found");
    }

    if (check.status === "paused") {
      return res.json(checkToDict(check, req.readonly, req.v));
    }

    db.prepare("UPDATE checks SET status = 'paused', last_start = NULL, alert_after = NULL WHERE id = ?")
      .run(check.id);

    const updated = db.prepare("SELECT * FROM checks WHERE id = ?").get(check.id) as CheckRow;
    res.json(checkToDict(updated, req.readonly, req.v));
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
    res.json(checkToDict(updated, req.readonly, req.v));
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
        body_url: p.body ? `${process.env.SITE_ROOT || "http://localhost:8000"}/api/v${req.v}/checks/${check.code}/pings/${p.n}/body` : null,
        duration: null // simple mock duration
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

    const ping = db.prepare("SELECT * FROM pings WHERE check_id = ? AND n = ?").get(check.id, req.params.n) as any;
    if (!ping || !ping.body) {
      return res.status(404).send("Not Found");
    }

    res.setHeader("Content-Type", "text/plain");
    res.send(ping.body);
  });
}

// SVG badges logic
router.get("/b/2/:badge_key.svg", (req, res) => {
  res.setHeader("Content-Type", "image/svg+xml");
  // return simple SVG
  res.send(`<svg xmlns="http://www.w3.org/2000/svg" width="80" height="20"><text y="15">badge</text></svg>`);
});

export default router;

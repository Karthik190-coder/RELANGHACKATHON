import crypto from "crypto";
import parser from "cron-parser";
import { db } from "./db";

export interface CheckRow {
  id: number;
  name: string;
  slug: string;
  tags: string;
  code: string;
  desc: string;
  project_id: number;
  kind: string;
  timeout: number;
  grace: number;
  schedule: string;
  tz: string;
  status: string;
  n_pings: number;
  last_ping: string | null;
  last_start: string | null;
  last_start_rid: string | null;
  last_duration: number | null;
  filter_subject: number;
  filter_body: number;
  filter_http_body: number;
  filter_default_fail: number;
  start_kw: string;
  success_kw: string;
  failure_kw: string;
  methods: string;
  manual_resume: number;
  badge_key: string;
  created: string;
  alert_after: string | null;
}

export const NEVER = new Date("3000-01-01T00:00:00Z");

export function getUniqueKey(code: string): string {
  const codeHalf = code.replace(/-/g, "").slice(0, 16);
  return crypto.createHash("sha1").update(codeHalf).digest("hex");
}

export function getGraceStart(check: CheckRow, withStarted: boolean = true): Date | null {
  let result = NEVER;
  const now = new Date();

  const status = check.status;

  if (check.kind === "simple" && status === "up") {
    if (check.last_ping) {
      result = new Date(new Date(check.last_ping).getTime() + check.timeout * 1000);
    }
  } else if (check.kind === "cron" && status === "up") {
    if (check.last_ping) {
      try {
        const lastPingDate = new Date(check.last_ping);
        const options = {
          currentDate: lastPingDate,
          tz: check.tz
        };
        const interval = parser.parseExpression(check.schedule, options);
        result = interval.next().toDate();
      } catch (e) {
        result = NEVER;
      }
    }
  }

  if (withStarted && check.last_start && status !== "down") {
    const lastStart = new Date(check.last_start);
    if (lastStart < result) {
      result = lastStart;
    }
  }

  return result.getTime() !== NEVER.getTime() ? result : null;
}

export function goingDownAfter(check: CheckRow): Date | null {
  const graceStart = getGraceStart(check);
  if (graceStart) {
    return new Date(graceStart.getTime() + check.grace * 1000);
  }
  return null;
}

export function getStatus(check: CheckRow, withStarted: boolean = false): string {
  const now = new Date();

  if (check.last_start) {
    const lastStart = new Date(check.last_start);
    if (now.getTime() >= lastStart.getTime() + check.grace * 1000) {
      return "down";
    } else if (withStarted) {
      return "started";
    }
  }

  if (["new", "paused", "down"].includes(check.status)) {
    return check.status;
  }

  const graceStart = getGraceStart(check, false);
  if (!graceStart) {
    return "up";
  }

  const graceEnd = new Date(graceStart.getTime() + check.grace * 1000);
  if (now.getTime() >= graceEnd.getTime()) {
    return "down";
  }

  if (now.getTime() >= graceStart.getTime()) {
    return "grace";
  }

  return "up";
}

export function getChannelsStr(checkId: number): string {
  const rows = db.prepare(`
    SELECT code FROM channels c
    JOIN api_channel_checks acc ON c.id = acc.channel_id
    WHERE acc.check_id = ?
  `).all(checkId) as any[];
  
  return rows.map(r => r.code).sort().join(",");
}

export function checkToDict(check: CheckRow, readonly: boolean = false, v: number = 3): any {
  const withStarted = v === 1;
  const siteRoot = process.env.SITE_ROOT || "http://localhost:8000";

  const result: any = {
    name: check.name,
    slug: check.slug,
    tags: check.tags,
    desc: check.desc,
    grace: check.grace,
    n_pings: check.n_pings,
    status: getStatus(check, withStarted),
    started: check.last_start !== null,
    last_ping: check.last_ping ? new Date(check.last_ping).toISOString().replace(/\.\d+Z$/, "") : null,
    next_ping: null,
    manual_resume: check.manual_resume === 1,
    methods: check.methods,
    subject: check.filter_subject === 1 ? check.success_kw : "",
    subject_fail: check.filter_subject === 1 ? check.failure_kw : "",
    start_kw: check.start_kw,
    success_kw: check.success_kw,
    failure_kw: check.failure_kw,
    filter_subject: check.filter_subject === 1,
    filter_body: check.filter_body === 1,
    filter_http_body: check.filter_http_body === 1,
    filter_default_fail: check.filter_default_fail === 1,
    badge_url: `${siteRoot}/b/2/${check.badge_key}.svg`
  };

  const graceStart = getGraceStart(check);
  if (graceStart) {
    result.next_ping = graceStart.toISOString().replace(/\.\d+Z$/, "");
  }

  if (check.last_duration !== null && check.last_duration !== undefined) {
    result.last_duration = check.last_duration;
  }

  if (readonly) {
    result.unique_key = getUniqueKey(check.code);
  } else {
    result.uuid = check.code;
    result.ping_url = (process.env.PING_ENDPOINT || (siteRoot + "/ping/")) + check.code;
    
    const updateUrl = `${siteRoot}/api/v${v}/checks/${check.code}`;
    result.update_url = updateUrl;
    result.pause_url = updateUrl + "/pause";
    result.resume_url = updateUrl + "/resume";
    result.channels = getChannelsStr(check.id);
  }

  if (check.kind === "simple") {
    result.timeout = check.timeout;
  } else if (["cron", "oncalendar"].includes(check.kind)) {
    result.schedule = check.schedule;
    result.tz = check.tz;
  }

  return result;
}

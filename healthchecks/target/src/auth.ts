import { Request, Response, NextFunction } from "express";
import { db } from "./db";

export interface AuthenticatedRequest extends Request {
  user?: {
    id: number;
    username: string;
    email: string;
  };
  project?: {
    id: number;
    code: string;
    name: string;
    owner_id: number;
    api_key: string;
    api_key_readonly: string;
    ping_key: string;
    badge_key: string;
    show_slugs: number;
  };
  readonly?: boolean;
  v?: number;
}

// Middleware to parse and load current user from session
export function sessionAuth(req: AuthenticatedRequest, res: Response, next: NextFunction) {
  const sessionid = req.cookies.sessionid;
  if (sessionid) {
    const session = db.prepare("SELECT * FROM sessions WHERE sessionid = ?").get(sessionid) as any;
    if (session) {
      const user = db.prepare("SELECT * FROM users WHERE id = ?").get(session.user_id) as any;
      if (user) {
        req.user = {
          id: user.id,
          username: user.username,
          email: user.email
        };
        // Load default project for user (either owned or membership)
        const project = db.prepare(`
          SELECT p.* FROM projects p
          LEFT JOIN members m ON p.id = m.project_id
          WHERE p.owner_id = ? OR m.user_id = ?
          LIMIT 1
        `).get(user.id, user.id) as any;
        if (project) {
          req.project = project;
        }
      }
    }
  }
  next();
}

// CSRF checking middleware for HTML forms
export function csrfCheck(req: Request, res: Response, next: NextFunction) {
  const path = req.path;
  // Exempt API, ping, test, and docs endpoints from CSRF checks
  if (path.startsWith("/api/") || path.startsWith("/ping/") || path.startsWith("/__test/") || path.startsWith("/docs/")) {
    return next();
  }

  if (req.method === "POST") {
    const cookieCsrf = req.cookies.csrftoken;
    const bodyCsrf = req.body.csrfmiddlewaretoken || req.headers["x-csrftoken"];

    if (!cookieCsrf || !bodyCsrf || cookieCsrf !== bodyCsrf) {
      return res.status(403).send("CSRF verification failed. Request aborted.");
    }
  }
  next();
}

export function redirect(res: Response, url: string, status = 302) {
  res.setHeader("Content-Type", "text/html");
  res.setHeader("Location", url);
  res.status(status).send(`<!DOCTYPE html><html><body>Redirecting to <a href="${url}">${url}</a></body></html>`);
}

// Middleware to require web authentication
export function requireWebAuth(req: AuthenticatedRequest, res: Response, next: NextFunction) {
  if (!req.user) {
    const nextUrl = req.originalUrl;
    return redirect(res, `/accounts/login/?next=${encodeURIComponent(nextUrl)}`);
  }
  next();
}

// Middleware to authorize read-write API requests
export function authorizeApi(req: AuthenticatedRequest, res: Response, next: NextFunction) {
  let apiKey = req.headers["x-api-key"] || (req.body && typeof req.body === "object" ? req.body.api_key : undefined);
  if (Array.isArray(apiKey)) {
    apiKey = apiKey[0];
  }

  if (!apiKey || typeof apiKey !== "string" || apiKey.length !== 32) {
    return res.status(401).json({ error: "missing api key" });
  }

  const project = db.prepare("SELECT * FROM projects WHERE api_key = ?").get(apiKey) as any;
  if (!project) {
    return res.status(401).json({ error: "wrong api key" });
  }

  req.project = project;
  req.readonly = false;
  req.v = req.path.startsWith("/api/v3/") ? 3 : req.path.startsWith("/api/v2/") ? 2 : 1;
  next();
}

// Middleware to authorize read-only/read-write API requests
export function authorizeApiRead(req: AuthenticatedRequest, res: Response, next: NextFunction) {
  let apiKey = req.headers["x-api-key"];
  if (Array.isArray(apiKey)) {
    apiKey = apiKey[0];
  }

  if (!apiKey || typeof apiKey !== "string" || apiKey.length !== 32) {
    return res.status(401).json({ error: "missing api key" });
  }

  const project = db.prepare("SELECT * FROM projects WHERE api_key = ? OR api_key_readonly = ?").get(apiKey, apiKey) as any;
  if (!project) {
    return res.status(401).json({ error: "wrong api key" });
  }

  req.project = project;
  req.readonly = apiKey.startsWith("hcr_") || apiKey === project.api_key_readonly;
  req.v = req.path.startsWith("/api/v3/") ? 3 : req.path.startsWith("/api/v2/") ? 2 : 1;
  next();
}

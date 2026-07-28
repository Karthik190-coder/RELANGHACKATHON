import Database from "better-sqlite3";
import path from "path";
import { v4 as uuidv4 } from "uuid";

const dbPath = path.resolve(__dirname, "../hc.sqlite");
export const db = new Database(dbPath);

// Initialize DB schema
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    email TEXT UNIQUE,
    password TEXT,
    is_staff INTEGER DEFAULT 0
  );

  CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    token TEXT DEFAULT '',
    check_limit INTEGER DEFAULT 20,
    sms_limit INTEGER DEFAULT 0,
    sms_sent INTEGER DEFAULT 0,
    call_limit INTEGER DEFAULT 0,
    calls_sent INTEGER DEFAULT 0,
    theme TEXT,
    tz TEXT DEFAULT 'UTC',
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    name TEXT,
    owner_id INTEGER,
    api_key TEXT UNIQUE,
    api_key_readonly TEXT UNIQUE,
    badge_key TEXT UNIQUE,
    ping_key TEXT UNIQUE,
    show_slugs INTEGER DEFAULT 0,
    FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    project_id INTEGER,
    role TEXT DEFAULT 'w',
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(user_id, project_id)
  );

  CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT DEFAULT '',
    slug TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    code TEXT UNIQUE,
    desc TEXT DEFAULT '',
    project_id INTEGER,
    kind TEXT DEFAULT 'simple',
    timeout INTEGER DEFAULT 86400,
    grace INTEGER DEFAULT 3600,
    schedule TEXT DEFAULT '* * * * *',
    tz TEXT DEFAULT 'UTC',
    status TEXT DEFAULT 'new',
    n_pings INTEGER DEFAULT 0,
    last_ping TEXT,
    last_start TEXT,
    last_start_rid TEXT,
    last_duration INTEGER,
    filter_subject INTEGER DEFAULT 0,
    filter_body INTEGER DEFAULT 0,
    filter_http_body INTEGER DEFAULT 0,
    filter_default_fail INTEGER DEFAULT 0,
    start_kw TEXT DEFAULT '',
    success_kw TEXT DEFAULT '',
    failure_kw TEXT DEFAULT '',
    methods TEXT DEFAULT '',
    manual_resume INTEGER DEFAULT 0,
    badge_key TEXT UNIQUE,
    created TEXT,
    alert_after TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    name TEXT DEFAULT '',
    kind TEXT,
    project_id INTEGER,
    value TEXT DEFAULT '',
    email_verified INTEGER DEFAULT 0,
    disabled INTEGER DEFAULT 0,
    last_error TEXT DEFAULT '',
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS api_channel_checks (
    channel_id INTEGER,
    check_id INTEGER,
    PRIMARY KEY (channel_id, check_id),
    FOREIGN KEY(channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    FOREIGN KEY(check_id) REFERENCES checks(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS pings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id INTEGER,
    n INTEGER,
    created TEXT,
    remote_addr TEXT,
    scheme TEXT,
    method TEXT,
    ua TEXT,
    body TEXT,
    kind TEXT,
    exitstatus INTEGER,
    FOREIGN KEY(check_id) REFERENCES checks(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS token_buckets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    value REAL,
    updated TEXT
  );

  CREATE TABLE IF NOT EXISTS sessions (
    sessionid TEXT PRIMARY KEY,
    user_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
  );
`);

try { db.exec("ALTER TABLE checks ADD COLUMN last_start_rid TEXT"); } catch (e) {}
try { db.exec("ALTER TABLE checks ADD COLUMN has_confirmation_link INTEGER DEFAULT 0"); } catch (e) {}
try { db.exec("ALTER TABLE profiles ADD COLUMN token TEXT DEFAULT ''"); } catch (e) {}

export function resetDatabase() {
  db.transaction(() => {
    // Delete target data
    db.prepare("DELETE FROM token_buckets").run();
    db.prepare("DELETE FROM pings").run();
    db.prepare("DELETE FROM api_channel_checks").run();
    db.prepare("DELETE FROM channels").run();
    db.prepare("DELETE FROM checks").run();
    db.prepare("DELETE FROM sessions").run();

    // Remove all users to ensure fresh seeding on reset
    db.prepare("DELETE FROM users").run();

    // Ensure alice, bob, charlie exist
    const insertUser = db.prepare(`
      INSERT INTO users (username, email, password)
      VALUES (?, ?, ?)
    `);
    
    // We store simple hashed or even plain password. In Node side, we will just compare plaintext or simple hash
    // The test cases use password="password" for authentication
    insertUser.run("alice", "alice@example.org", "password");
    insertUser.run("bob", "bob@example.org", "password");
    insertUser.run("charlie", "charlie@example.org", "password");

    const users = db.prepare("SELECT * FROM users").all() as any[];
    const userMap = new Map(users.map(u => [u.username, u]));

    // Clean up projects for alice, bob, charlie
    db.prepare(`
      DELETE FROM projects 
      WHERE owner_id IN (SELECT id FROM users WHERE username IN ('alice', 'bob', 'charlie'))
    `).run();

    // Recreate projects
    const insertProject = db.prepare(`
      INSERT INTO projects (code, name, owner_id, api_key, api_key_readonly, badge_key, ping_key)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);

    let aliceProjId: number | bigint = 0;

    for (const username of ["alice", "bob", "charlie"]) {
      const user = userMap.get(username);
      const code = uuidv4();
      let name = "";
      let apiKey = null;
      let apiKeyRo = null;
      let pingKey = null;
      const badgeKey = username;

      if (username === "alice") {
        name = "Alices Project";
        apiKey = "X".repeat(32);
        apiKeyRo = "R".repeat(32);
        pingKey = "p".repeat(22);
      }

      const res = insertProject.run(code, name, user.id, apiKey, apiKeyRo, badgeKey, pingKey);
      if (username === "alice") {
        aliceProjId = res.lastInsertRowid;
      }
    }

    // Clean up members
    db.prepare("DELETE FROM members").run();

    // Create bob as member in alice's project
    const bobUser = userMap.get("bob");
    db.prepare(`
      INSERT OR IGNORE INTO members (user_id, project_id, role)
      VALUES (?, ?, 'w')
    `).run(bobUser.id, aliceProjId);

    // Setup profile theme = null
    const insertProfile = db.prepare(`
      INSERT INTO profiles (user_id, check_limit, sms_limit, call_limit, theme)
      VALUES (?, 10000, 10000, 10000, NULL)
      ON CONFLICT(user_id) DO UPDATE SET theme = NULL
    `);
    for (const username of ["alice", "bob", "charlie"]) {
      const user = userMap.get(username);
      insertProfile.run(user.id);
    }
  })();
}

package main

import (
	"crypto/sha256"
	"database/sql"
	"fmt"
	"log"
	"time"

	"github.com/google/uuid"
)

type User struct {
	ID       int64
	Username string
	Email    string
}

type Profile struct {
	ID           int64
	UserID       int64
	Reports      string
	NagPeriod    int
	PingLogLimit int
	CheckLimit   int
	Token        string
	TZ           string
	Theme        string
	Sort         string
}

type Project struct {
	ID           int64
	Code         string
	Name         string
	OwnerID      int64
	APIKey       string
	APIKeyReadonly string
	BadgeKey     string
	PingKey      string
	ShowSlugs    bool
}

type Member struct {
	ID        int64
	UserID    int64
	ProjectID int64
	Role      string
}

type Check struct {
	ID             int64
	Name           string
	Slug           string
	Tags           string
	Code           string
	Desc           string
	ProjectID      int64
	Created        string
	Kind           string
	Timeout        int64
	Grace          int64
	Schedule       string
	TZ             string
	FilterSubject  bool
	FilterBody     bool
	FilterHTTPBody bool
	FilterDefaultFail bool
	StartKW        string
	SuccessKW      string
	FailureKW      string
	Methods        string
	ManualResume   bool
	BadgeKey       string
	NPings         int64
	LastPing       *string
	LastStart      *string
	LastStartRid   *string
	LastDuration   *int64
	HasConfirmationLink bool
	AlertAfter     *string
	Status         string
}

type Channel struct {
	ID               int64
	Name             string
	Code             string
	ProjectID        int64
	Kind             string
	Value            string
	EmailVerified    bool
	Disabled         bool
	LastNotify       *string
	LastNotifyDuration *int64
	LastError        string
}

type Ping struct {
	ID         int64
	N          int64
	OwnerID    int64
	Created    string
	Kind       *string
	Scheme     string
	RemoteAddr string
	Method     string
	UA         string
	BodyRaw    []byte
	RID        *string
	ExitStatus *int64
}

type Flip struct {
	ID        int64
	OwnerID   int64
	Created   string
	Processed *string
	OldStatus string
	NewStatus string
	Reason    string
}

type Notification struct {
	ID          int64
	Code        string
	OwnerID     *int64
	CheckStatus string
	ChannelID   int64
	Created     string
	Error       string
}

func initDB() {
	schema := `
	CREATE TABLE IF NOT EXISTS users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		username TEXT UNIQUE NOT NULL,
		email TEXT UNIQUE NOT NULL,
		password_hash TEXT DEFAULT '',
		is_superuser INTEGER DEFAULT 0
	);
	CREATE TABLE IF NOT EXISTS profiles (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER UNIQUE NOT NULL,
		reports TEXT DEFAULT 'monthly',
		nag_period INTEGER DEFAULT 0,
		ping_log_limit INTEGER DEFAULT 100,
		check_limit INTEGER DEFAULT 20,
		token TEXT DEFAULT '',
		tz TEXT DEFAULT 'UTC',
		theme TEXT DEFAULT '',
		sort TEXT DEFAULT 'created',
		sms_limit INTEGER DEFAULT 10000,
		call_limit INTEGER DEFAULT 10000,
		FOREIGN KEY (user_id) REFERENCES users(id)
	);
	CREATE TABLE IF NOT EXISTS projects (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		code TEXT UNIQUE NOT NULL,
		name TEXT DEFAULT '',
		owner_id INTEGER NOT NULL,
		api_key TEXT DEFAULT '',
		api_key_readonly TEXT DEFAULT '',
		badge_key TEXT UNIQUE NOT NULL,
		ping_key TEXT,
		show_slugs INTEGER DEFAULT 0,
		FOREIGN KEY (owner_id) REFERENCES users(id)
	);
	CREATE TABLE IF NOT EXISTS members (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL,
		project_id INTEGER NOT NULL,
		role TEXT DEFAULT 'w',
		transfer_request_date TEXT,
		UNIQUE(user_id, project_id),
		FOREIGN KEY (user_id) REFERENCES users(id),
		FOREIGN KEY (project_id) REFERENCES projects(id)
	);
	CREATE TABLE IF NOT EXISTS checks (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		name TEXT DEFAULT '',
		slug TEXT DEFAULT '',
		tags TEXT DEFAULT '',
		code TEXT UNIQUE NOT NULL,
		kind TEXT DEFAULT 'simple',
		desc TEXT DEFAULT '',
		project_id INTEGER NOT NULL,
		created TEXT DEFAULT '',
		timeout INTEGER DEFAULT 86400,
		grace INTEGER DEFAULT 3600,
		schedule TEXT DEFAULT '* * * * *',
		tz TEXT DEFAULT 'UTC',
		filter_subject INTEGER DEFAULT 0,
		filter_body INTEGER DEFAULT 0,
		filter_http_body INTEGER DEFAULT 0,
		filter_default_fail INTEGER DEFAULT 0,
		start_kw TEXT DEFAULT '',
		success_kw TEXT DEFAULT '',
		failure_kw TEXT DEFAULT '',
		methods TEXT DEFAULT '',
		manual_resume INTEGER DEFAULT 0,
		badge_key TEXT UNIQUE NOT NULL,
		n_pings INTEGER DEFAULT 0,
		last_ping TEXT,
		last_start TEXT,
		last_start_rid TEXT,
		last_duration INTEGER,
		has_confirmation_link INTEGER DEFAULT 0,
		alert_after TEXT,
		status TEXT DEFAULT 'new',
		FOREIGN KEY (project_id) REFERENCES projects(id)
	);
	CREATE TABLE IF NOT EXISTS channels (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		name TEXT DEFAULT '',
		code TEXT UNIQUE NOT NULL,
		project_id INTEGER NOT NULL,
		created TEXT DEFAULT '',
		kind TEXT NOT NULL,
		value TEXT DEFAULT '',
		email_verified INTEGER DEFAULT 0,
		disabled INTEGER DEFAULT 0,
		last_notify TEXT,
		last_notify_duration INTEGER,
		last_error TEXT DEFAULT '',
		FOREIGN KEY (project_id) REFERENCES projects(id)
	);
	CREATE TABLE IF NOT EXISTS check_channels (
		check_id INTEGER NOT NULL,
		channel_id INTEGER NOT NULL,
		PRIMARY KEY (check_id, channel_id),
		FOREIGN KEY (check_id) REFERENCES checks(id),
		FOREIGN KEY (channel_id) REFERENCES channels(id)
	);
	CREATE TABLE IF NOT EXISTS pings (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		n INTEGER,
		owner_id INTEGER NOT NULL,
		created TEXT DEFAULT '',
		kind TEXT,
		scheme TEXT DEFAULT 'http',
		remote_addr TEXT,
		method TEXT DEFAULT '',
		ua TEXT DEFAULT '',
		body_raw BLOB,
		exitstatus INTEGER,
		rid TEXT,
		FOREIGN KEY (owner_id) REFERENCES checks(id)
	);
	CREATE TABLE IF NOT EXISTS flips (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		owner_id INTEGER NOT NULL,
		created TEXT NOT NULL,
		processed TEXT,
		old_status TEXT NOT NULL,
		new_status TEXT NOT NULL,
		reason TEXT DEFAULT '',
		FOREIGN KEY (owner_id) REFERENCES checks(id)
	);
	CREATE TABLE IF NOT EXISTS notifications (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		code TEXT UNIQUE NOT NULL,
		owner_id INTEGER,
		check_status TEXT NOT NULL,
		channel_id INTEGER NOT NULL,
		created TEXT DEFAULT '',
		error TEXT DEFAULT '',
		FOREIGN KEY (owner_id) REFERENCES checks(id),
		FOREIGN KEY (channel_id) REFERENCES channels(id)
	);
	CREATE TABLE IF NOT EXISTS sessions (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL,
		token TEXT UNIQUE NOT NULL,
		FOREIGN KEY (user_id) REFERENCES users(id)
	);
	`
	_, err := db.Exec(schema)
	if err != nil {
		log.Fatal("Failed to create schema:", err)
	}

	// Create users alice, bob, charlie with password "password"
	createTestUsers()
}

func createTestUsers() {
	users := []struct{ username, email string }{
		{"alice", "alice@example.org"},
		{"bob", "bob@example.org"},
		{"charlie", "charlie@example.org"},
	}
	for _, u := range users {
		var exists int
		db.QueryRow("SELECT COUNT(*) FROM users WHERE username=?", u.username).Scan(&exists)
		if exists == 0 {
			db.Exec("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", u.username, u.email, hashPassword("password"))
		}
	}
}

func hashPassword(password string) string {
	h := sha256.Sum256([]byte(password + "healthchecks_salt"))
	return fmt.Sprintf("%x", h)
}

func verifyPassword(hash, password string) bool {
	return hash == hashPassword(password)
}

func nowISO() string {
	return time.Now().UTC().Format("2006-01-02T15:04:05.000000+00:00")
}

func handleTestReset(w http.ResponseWriter, r *http.Request) {
	tx, err := db.Begin()
	if err != nil {
		http.Error(w, "db error", 500)
		return
	}
	defer tx.Rollback()

	tx.Exec("DELETE FROM token_buckets")
	tx.Exec("DELETE FROM notifications")
	tx.Exec("DELETE FROM flips")
	tx.Exec("DELETE FROM pings")
	tx.Exec("DELETE FROM check_channels")
	tx.Exec("DELETE FROM checks")
	tx.Exec("DELETE FROM channels")
	tx.Exec("DELETE FROM sessions")

	// Delete users not in (alice, bob, charlie)
	tx.Exec("DELETE FROM users WHERE username NOT IN ('alice','bob','charlie')")

	// Delete projects not owned by alice/bob/charlie
	tx.Exec("DELETE FROM projects WHERE owner_id NOT IN (SELECT id FROM users WHERE username IN ('alice','bob','charlie'))")

	// Delete existing projects for these users
	tx.Exec("DELETE FROM projects WHERE owner_id IN (SELECT id FROM users WHERE username IN ('alice','bob','charlie'))")

	// Create projects for each user
	type projInfo struct {
		username, name, badgeKey, apiKey, apiKeyRO, pingKey string
	}
	projs := []projInfo{
		{"alice", "Alices Project", "alice", "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX", "R" + repeatStr("R", 31), "p" + repeatStr("p", 21)},
		{"bob", "", "bob", "", "", ""},
		{"charlie", "", "charlie", "", "", ""},
	}

	for _, pi := range projs {
		var uid int64
		tx.QueryRow("SELECT id FROM users WHERE username=?", pi.username).Scan(&uid)
		projectCode := generateUUID()
		badgeKey := pi.badgeKey
		if badgeKey == "" {
			badgeKey = projectCode
		}
		_, err := tx.Exec("INSERT INTO projects (code, name, owner_id, api_key, api_key_readonly, badge_key, ping_key) VALUES (?,?,?,?,?,?,?)",
			projectCode, pi.name, uid, pi.apiKey, pi.apiKeyRO, badgeKey, pi.pingKey)
		if err != nil {
			log.Printf("Error creating project for %s: %v", pi.username, err)
			continue
		}

		// Ensure profile exists
		var profileExists int
		tx.QueryRow("SELECT COUNT(*) FROM profiles WHERE user_id=?", uid).Scan(&profileExists)
		if profileExists == 0 {
			tx.Exec("INSERT INTO profiles (user_id) VALUES (?)", uid)
		} else {
			tx.Exec("UPDATE profiles SET theme=NULL WHERE user_id=?", uid)
		}
	}

	// Add bob as member of alice's project
	var aliceUID int64
	tx.QueryRow("SELECT id FROM users WHERE username='alice'").Scan(&aliceUID)
	var bobUID int64
	tx.QueryRow("SELECT id FROM users WHERE username='bob'").Scan(&bobUID)
	var aliceProjID int64
	tx.QueryRow("SELECT id FROM projects WHERE owner_id=?", aliceUID).Scan(&aliceProjID)

	if aliceProjID > 0 {
		var memberExists int
		tx.QueryRow("SELECT COUNT(*) FROM members WHERE user_id=? AND project_id=?", bobUID, aliceProjID).Scan(&memberExists)
		if memberExists == 0 {
			tx.Exec("INSERT INTO members (user_id, project_id, role) VALUES (?, ?, 'w')", bobUID, aliceProjID)
		}
	}

	tx.Commit()
	w.Header().Set("Content-Type", "text/plain")
	fmt.Fprint(w, "ok")
}

func repeatStr(s string, n int) string {
	result := ""
	for i := 0; i < n; i++ {
		result += s
	}
	return result
}

func createCheck(projectID int64, name, slug, tags, desc, kind string, timeout, grace int64, schedule, tz string, methods string, manualResume bool, filterSubject, filterBody, filterHTTPBody, filterDefaultFail bool, startKW, successKW, failureKW string) (*Check, error) {
	code := generateUUID()
	badgeKey := generateUUID()
	nowStr := nowISO()

	if kind == "" {
		kind = "simple"
	}
	if timeout == 0 {
		timeout = 86400
	}
	if grace == 0 {
		grace = 3600
	}
	if schedule == "" {
		schedule = "* * * * *"
	}
	if tz == "" {
		tz = "UTC"
	}

	filterSubjectInt := 0
	if filterSubject {
		filterSubjectInt = 1
	}
	filterBodyInt := 0
	if filterBody {
		filterBodyInt = 1
	}
	filterHTTPBodyInt := 0
	if filterHTTPBody {
		filterHTTPBodyInt = 1
	}
	filterDefaultFailInt := 0
	if filterDefaultFail {
		filterDefaultFailInt = 1
	}
	manualResumeInt := 0
	if manualResume {
		manualResumeInt = 1
	}

	result, err := db.Exec(`INSERT INTO checks (name, slug, tags, code, kind, desc, project_id, created, timeout, grace, schedule, tz, filter_subject, filter_body, filter_http_body, filter_default_fail, start_kw, success_kw, failure_kw, methods, manual_resume, badge_key, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
		name, slug, tags, code, kind, desc, projectID, nowStr, timeout, grace, schedule, tz, filterSubjectInt, filterBodyInt, filterHTTPBodyInt, filterDefaultFailInt, startKW, successKW, failureKW, methods, manualResumeInt, badgeKey, "new")
	if err != nil {
		return nil, err
	}

	id, _ := result.LastInsertId()
	return &Check{
		ID: id, Name: name, Slug: slug, Tags: tags, Code: code, Kind: kind, Desc: desc,
		ProjectID: projectID, Timeout: timeout, Grace: grace, Schedule: schedule, TZ: tz,
		FilterSubject: filterSubject, FilterBody: filterBody, FilterHTTPBody: filterHTTPBody,
		FilterDefaultFail: filterDefaultFail, StartKW: startKW, SuccessKW: successKW, FailureKW: failureKW,
		Methods: methods, ManualResume: manualResume, BadgeKey: badgeKey, Status: "new",
		NPings: 0, Created: nowStr,
	}, nil
}

func getCheckByCode(code string) (*Check, error) {
	var c Check
	var lastPing, lastStart, lastStartRid, alertAfter sql.NullString
	var lastDuration sql.NullInt64
	var filterSubjectInt, filterBodyInt, filterHTTPBodyInt, filterDefaultFailInt, manualResumeInt int
	err := db.QueryRow(`SELECT id,name,slug,tags,code,kind,desc,project_id,created,timeout,grace,schedule,tz,filter_subject,filter_body,filter_http_body,filter_default_fail,start_kw,success_kw,failure_kw,methods,manual_resume,badge_key,n_pings,last_ping,last_start,last_start_rid,last_duration,has_confirmation_link,alert_after,status FROM checks WHERE code=?`, code).Scan(
		&c.ID, &c.Name, &c.Slug, &c.Tags, &c.Code, &c.Kind, &c.Desc, &c.ProjectID, &c.Created, &c.Timeout, &c.Grace, &c.Schedule, &c.TZ, &filterSubjectInt, &filterBodyInt, &filterHTTPBodyInt, &filterDefaultFailInt, &c.StartKW, &c.SuccessKW, &c.FailureKW, &c.Methods, &manualResumeInt, &c.BadgeKey, &c.NPings, &lastPing, &lastStart, &lastStartRid, &lastDuration, &c.HasConfirmationLink, &alertAfter, &c.Status)
	if err != nil {
		return nil, err
	}
	c.FilterSubject = filterSubjectInt != 0
	c.FilterBody = filterBodyInt != 0
	c.FilterHTTPBody = filterHTTPBodyInt != 0
	c.FilterDefaultFail = filterDefaultFailInt != 0
	c.ManualResume = manualResumeInt != 0
	if lastPing.Valid {
		c.LastPing = &lastPing.String
	}
	if lastStart.Valid {
		c.LastStart = &lastStart.String
	}
	if lastStartRid.Valid {
		c.LastStartRid = &lastStartRid.String
	}
	if lastDuration.Valid {
		c.LastDuration = &lastDuration.Int64
	}
	if alertAfter.Valid {
		c.AlertAfter = &alertAfter.String
	}
	return &c, nil
}

func getCheckByID(id int64) (*Check, error) {
	var c Check
	var lastPing, lastStart, lastStartRid, alertAfter sql.NullString
	var lastDuration sql.NullInt64
	var filterSubjectInt, filterBodyInt, filterHTTPBodyInt, filterDefaultFailInt, manualResumeInt int
	err := db.QueryRow(`SELECT id,name,slug,tags,code,kind,desc,project_id,created,timeout,grace,schedule,tz,filter_subject,filter_body,filter_http_body,filter_default_fail,start_kw,success_kw,failure_kw,methods,manual_resume,badge_key,n_pings,last_ping,last_start,last_start_rid,last_duration,has_confirmation_link,alert_after,status FROM checks WHERE id=?`, id).Scan(
		&c.ID, &c.Name, &c.Slug, &c.Tags, &c.Code, &c.Kind, &c.Desc, &c.ProjectID, &c.Created, &c.Timeout, &c.Grace, &c.Schedule, &c.TZ, &filterSubjectInt, &filterBodyInt, &filterHTTPBodyInt, &filterDefaultFailInt, &c.StartKW, &c.SuccessKW, &c.FailureKW, &c.Methods, &manualResumeInt, &c.BadgeKey, &c.NPings, &lastPing, &lastStart, &lastStartRid, &lastDuration, &c.HasConfirmationLink, &alertAfter, &c.Status)
	if err != nil {
		return nil, err
	}
	c.FilterSubject = filterSubjectInt != 0
	c.FilterBody = filterBodyInt != 0
	c.FilterHTTPBody = filterHTTPBodyInt != 0
	c.FilterDefaultFail = filterDefaultFailInt != 0
	c.ManualResume = manualResumeInt != 0
	if lastPing.Valid {
		c.LastPing = &lastPing.String
	}
	if lastStart.Valid {
		c.LastStart = &lastStart.String
	}
	if lastStartRid.Valid {
		c.LastStartRid = &lastStartRid.String
	}
	if lastDuration.Valid {
		c.LastDuration = &lastDuration.Int64
	}
	if alertAfter.Valid {
		c.AlertAfter = &alertAfter.String
	}
	return &c, nil
}

func (c *Check) toDict(v int, readonly bool) map[string]interface{} {
	status := c.Status
	if c.LastStart != nil && status != "paused" && status != "new" {
		// Check if started and grace has expired
	}

	dict := map[string]interface{}{
		"name":            c.Name,
		"slug":            c.Slug,
		"tags":            c.Tags,
		"desc":            c.Desc,
		"grace":           c.Grace,
		"n_pings":         c.NPings,
		"status":          status,
		"started":         c.LastStart != nil,
		"last_ping":       c.LastPing,
		"next_ping":       nil,
		"manual_resume":   c.ManualResume,
		"methods":         c.Methods,
		"subject":         "",
		"subject_fail":    "",
		"start_kw":        c.StartKW,
		"success_kw":      c.SuccessKW,
		"failure_kw":      c.FailureKW,
		"filter_subject":  c.FilterSubject,
		"filter_body":     c.FilterBody,
		"filter_http_body": c.FilterHTTPBody,
		"filter_default_fail": c.FilterDefaultFail,
		"badge_url":       fmt.Sprintf("%s/b/2/%s.svg", siteRoot, c.BadgeKey),
	}

	if c.FilterSubject {
		dict["subject"] = c.SuccessKW
		dict["subject_fail"] = c.FailureKW
	}

	if c.Kind == "simple" {
		dict["timeout"] = c.Timeout
	} else {
		dict["schedule"] = c.Schedule
		dict["tz"] = c.TZ
	}

	if readonly {
		dict["unique_key"] = c.uniqueKey()
	} else {
		dict["uuid"] = c.Code
		dict["ping_url"] = fmt.Sprintf("%s/ping/%s", siteRoot, c.Code)
		dict["update_url"] = fmt.Sprintf("%s/api/v%d/checks/%s", siteRoot, v, c.Code)
		dict["pause_url"] = fmt.Sprintf("%s/api/v%d/checks/%s/pause", siteRoot, v, c.Code)
		dict["resume_url"] = fmt.Sprintf("%s/api/v%d/checks/%s/resume", siteRoot, v, c.Code)
		dict["channels"] = c.getChannelsStr()
	}

	return dict
}

func (c *Check) uniqueKey() string {
	h := sha1.New()
	h.Write([]byte(c.Code[:16]))
	return fmt.Sprintf("%x", h.Sum(nil))
}

func (c *Check) getChannelsStr() string {
	rows, err := db.Query("SELECT code FROM channels INNER JOIN check_channels ON channels.id=check_channels.channel_id WHERE check_channels.check_id=?", c.ID)
	if err != nil {
		return ""
	}
	defer rows.Close()
	var codes []string
	for rows.Next() {
		var code string
		rows.Scan(&code)
		codes = append(codes, code)
	}
	result := ""
	for i, code := range codes {
		if i > 0 {
			result += ","
		}
		result += code
	}
	return result
}

func (c *Check) updateFromSpec(spec CheckSpec, v int) {
	needSave := false

	if spec.Name != nil && c.Name != *spec.Name {
		c.Name = *spec.Name
		if v < 3 {
			c.Slug = slugify(*spec.Name)
		}
		needSave = true
	}

	if spec.Timeout != nil && *spec.Timeout > 0 && (c.Kind != "simple" || c.Timeout != *spec.Timeout) {
		c.Kind = "simple"
		c.Timeout = *spec.Timeout
		needSave = true
	}

	if spec.Schedule != nil && *spec.Schedule != "" {
		kind := "cron"
		if len(splitWords(*spec.Schedule)) != 5 {
			kind = "oncalendar"
		}
		if c.Kind != kind || c.Schedule != *spec.Schedule {
			c.Kind = kind
			c.Schedule = *spec.Schedule
			needSave = true
		}
	}

	if spec.Grace != nil && *spec.Grace > 0 && c.Grace != *spec.Grace {
		c.Grace = *spec.Grace
		needSave = true
	}

	if spec.Tags != nil && c.Tags != *spec.Tags {
		c.Tags = *spec.Tags
		needSave = true
	}

	if spec.Desc != nil && c.Desc != *spec.Desc {
		c.Desc = *spec.Desc
		needSave = true
	}

	if spec.Slug != nil && c.Slug != *spec.Slug {
		c.Slug = *spec.Slug
		needSave = true
	}

	if spec.ManualResume != nil && c.ManualResume != *spec.ManualResume {
		c.ManualResume = *spec.ManualResume
		needSave = true
	}

	if spec.Methods != nil && c.Methods != *spec.Methods {
		c.Methods = *spec.Methods
		needSave = true
	}

	if spec.TZ != nil && c.TZ != *spec.TZ {
		c.TZ = *spec.TZ
		needSave = true
	}

	if spec.StartKW != nil && c.StartKW != *spec.StartKW {
		c.StartKW = *spec.StartKW
		needSave = true
	}

	if spec.SuccessKW != nil && c.SuccessKW != *spec.SuccessKW {
		c.SuccessKW = *spec.SuccessKW
		needSave = true
	}

	if spec.FailureKW != nil && c.FailureKW != *spec.FailureKW {
		c.FailureKW = *spec.FailureKW
		needSave = true
	}

	if spec.FilterSubject != nil && c.FilterSubject != *spec.FilterSubject {
		c.FilterSubject = *spec.FilterSubject
		needSave = true
	}

	if spec.FilterBody != nil && c.FilterBody != *spec.FilterBody {
		c.FilterBody = *spec.FilterBody
		needSave = true
	}

	if spec.FilterHTTPBody != nil && c.FilterHTTPBody != *spec.FilterHTTPBody {
		c.FilterHTTPBody = *spec.FilterHTTPBody
		needSave = true
	}

	if spec.FilterDefaultFail != nil && c.FilterDefaultFail != *spec.FilterDefaultFail {
		c.FilterDefaultFail = *spec.FilterDefaultFail
		needSave = true
	}

	if spec.Subject != nil {
		c.SuccessKW = *spec.Subject
		c.FilterSubject = c.SuccessKW != "" || c.FailureKW != ""
		needSave = true
	}

	if spec.SubjectFail != nil {
		c.FailureKW = *spec.SubjectFail
		c.FilterSubject = c.SuccessKW != "" || c.FailureKW != ""
		needSave = true
	}

	if needSave {
		db.Exec(`UPDATE checks SET name=?,slug=?,tags=?,kind=?,desc=?,timeout=?,grace=?,schedule=?,tz=?,filter_subject=?,filter_body=?,filter_http_body=?,filter_default_fail=?,start_kw=?,success_kw=?,failure_kw=?,methods=?,manual_resume=? WHERE id=?`,
			c.Name, c.Slug, c.Tags, c.Kind, c.Desc, c.Timeout, c.Grace, c.Schedule, c.TZ, boolToInt(c.FilterSubject), boolToInt(c.FilterBody), boolToInt(c.FilterHTTPBody), boolToInt(c.FilterDefaultFail), c.StartKW, c.SuccessKW, c.FailureKW, c.Methods, boolToInt(c.ManualResume), c.ID)
	}
}

func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

func splitWords(s string) []string {
	words := []string{}
	for _, w := range fmt.Sprintf("%s", s) {
		if w == ' ' || w == '\t' || w == '\n' {
			if len(words) > 0 && words[len(words)-1] != "" {
				words = append(words, "")
			}
		} else {
			if len(words) == 0 {
				words = append(words, "")
			}
			words[len(words)-1] += string(w)
		}
	}
	return words
}

type CheckSpec struct {
	Name            *string  `json:"name"`
	Slug            *string  `json:"slug"`
	Tags            *string  `json:"tags"`
	Desc            *string  `json:"desc"`
	Timeout         *int64   `json:"timeout"`
	Grace           *int64   `json:"grace"`
	Schedule        *string  `json:"schedule"`
	TZ              *string  `json:"tz"`
	ManualResume    *bool    `json:"manual_resume"`
	Methods         *string  `json:"methods"`
	FilterSubject   *bool    `json:"filter_subject"`
	FilterBody      *bool    `json:"filter_body"`
	FilterHTTPBody  *bool    `json:"filter_http_body"`
	FilterDefaultFail *bool  `json:"filter_default_fail"`
	StartKW         *string  `json:"start_kw"`
	SuccessKW       *string  `json:"success_kw"`
	FailureKW       *string  `json:"failure_kw"`
	Subject         *string  `json:"subject"`
	SubjectFail     *string  `json:"subject_fail"`
	Channels        *string  `json:"channels"`
	Unique          []string `json:"unique"`
}

func lookupCheckBySpec(projectID int64, spec CheckSpec) *Check {
	if len(spec.Unique) == 0 {
		return nil
	}
	for _, field := range spec.Unique {
		switch field {
		case "name":
			if spec.Name == nil {
				return nil
			}
		case "slug":
			if spec.Slug == nil {
				return nil
			}
		case "tags":
			if spec.Tags == nil {
				return nil
			}
		case "timeout":
			if spec.Timeout == nil {
				return nil
			}
		case "grace":
			if spec.Grace == nil {
				return nil
			}
		}
	}

	query := "SELECT id,name,slug,tags,code,kind,desc,project_id,created,timeout,grace,schedule,tz,filter_subject,filter_body,filter_http_body,filter_default_fail,start_kw,success_kw,failure_kw,methods,manual_resume,badge_key,n_pings,last_ping,last_start,last_start_rid,last_duration,has_confirmation_link,alert_after,status FROM checks WHERE project_id=?"
	args := []interface{}{projectID}

	for _, field := range spec.Unique {
		switch field {
		case "name":
			query += " AND name=?"
			args = append(args, *spec.Name)
		case "slug":
			query += " AND slug=?"
			args = append(args, *spec.Slug)
		case "tags":
			query += " AND tags=?"
			args = append(args, *spec.Tags)
		case "timeout":
			query += " AND timeout=?"
			args = append(args, *spec.Timeout)
		case "grace":
			query += " AND grace=?"
			args = append(args, *spec.Grace)
		}
	}

	var c Check
	var lastPing, lastStart, lastStartRid, alertAfter sql.NullString
	var lastDuration sql.NullInt64
	var fsInt, fbInt, fhbInt, fdfInt, mrInt int
	err := db.QueryRow(query, args...).Scan(
		&c.ID, &c.Name, &c.Slug, &c.Tags, &c.Code, &c.Kind, &c.Desc, &c.ProjectID, &c.Created, &c.Timeout, &c.Grace, &c.Schedule, &c.TZ, &fsInt, &fbInt, &fhbInt, &fdfInt, &c.StartKW, &c.SuccessKW, &c.FailureKW, &c.Methods, &mrInt, &c.BadgeKey, &c.NPings, &lastPing, &lastStart, &lastStartRid, &lastDuration, &c.HasConfirmationLink, &alertAfter, &c.Status)
	if err != nil {
		return nil
	}
	c.FilterSubject = fsInt != 0
	c.FilterBody = fbInt != 0
	c.FilterHTTPBody = fbInt != 0
	c.FilterDefaultFail = fdfInt != 0
	c.ManualResume = mrInt != 0
	if lastPing.Valid {
		c.LastPing = &lastPing.String
	}
	if lastStart.Valid {
		c.LastStart = &lastStart.String
	}
	if lastStartRid.Valid {
		c.LastStartRid = &lastStartRid.String
	}
	if lastDuration.Valid {
		c.LastDuration = &lastDuration.Int64
	}
	return &c
}

func countUserChecks(userID int64) int {
	var count int
	db.QueryRow("SELECT COUNT(*) FROM checks WHERE project_id IN (SELECT id FROM projects WHERE owner_id=?)", userID).Scan(&count)
	return count
}

func getProfile(userID int64) *Profile {
	var p Profile
	err := db.QueryRow("SELECT id,user_id,reports,nag_period,ping_log_limit,check_limit,token,tz,theme,sort FROM profiles WHERE user_id=?", userID).Scan(&p.ID, &p.UserID, &p.Reports, &p.NagPeriod, &p.PingLogLimit, &p.CheckLimit, &p.Token, &p.TZ, &p.Theme, &p.Sort)
	if err != nil {
		// Create profile
		limit := 10000
		db.Exec("INSERT INTO profiles (user_id, check_limit, sms_limit, call_limit) VALUES (?, ?, ?, ?)", userID, limit, limit, limit)
		db.QueryRow("SELECT id,user_id,reports,nag_period,ping_log_limit,check_limit,token,tz,theme,sort FROM profiles WHERE user_id=?", userID).Scan(&p.ID, &p.UserID, &p.Reports, &p.NagPeriod, &p.PingLogLimit, &p.CheckLimit, &p.Token, &p.TZ, &p.Theme, &p.Sort)
	}
	return &p
}

func getUserByUsername(username string) *User {
	var u User
	err := db.QueryRow("SELECT id,username,email FROM users WHERE username=?", username).Scan(&u.ID, &u.Username, &u.Email)
	if err != nil {
		return nil
	}
	return &u
}

func getUserByEmail(email string) *User {
	var u User
	err := db.QueryRow("SELECT id,username,email FROM users WHERE email=?", email).Scan(&u.ID, &u.Username, &u.Email)
	if err != nil {
		return nil
	}
	return &u
}

func getUserByID(id int64) *User {
	var u User
	err := db.QueryRow("SELECT id,username,email FROM users WHERE id=?", id).Scan(&u.ID, &u.Username, &u.Email)
	if err != nil {
		return nil
	}
	return &u
}

func getProjectByCode(code string) *Project {
	var p Project
	var pk sql.NullString
	err := db.QueryRow("SELECT id,code,name,owner_id,api_key,api_key_readonly,badge_key,ping_key,show_slugs FROM projects WHERE code=?", code).Scan(&p.ID, &p.Code, &p.Name, &p.OwnerID, &p.APIKey, &p.APIKeyReadonly, &p.BadgeKey, &pk, &p.ShowSlugs)
	if err != nil {
		return nil
	}
	if pk.Valid {
		p.PingKey = pk.String
	}
	return &p
}

func getProjectByID(id int64) *Project {
	var p Project
	var pk sql.NullString
	err := db.QueryRow("SELECT id,code,name,owner_id,api_key,api_key_readonly,badge_key,ping_key,show_slugs FROM projects WHERE id=?", id).Scan(&p.ID, &p.Code, &p.Name, &p.OwnerID, &p.APIKey, &p.APIKeyReadonly, &p.BadgeKey, &pk, &p.ShowSlugs)
	if err != nil {
		return nil
	}
	if pk.Valid {
		p.PingKey = pk.String
	}
	return &p
}

func getProjectByBadgeKey(badgeKey string) *Project {
	var p Project
	var pk sql.NullString
	err := db.QueryRow("SELECT id,code,name,owner_id,api_key,api_key_readonly,badge_key,ping_key,show_slugs FROM projects WHERE badge_key=?", badgeKey).Scan(&p.ID, &p.Code, &p.Name, &p.OwnerID, &p.APIKey, &p.APIKeyReadonly, &p.BadgeKey, &pk, &p.ShowSlugs)
	if err != nil {
		return nil
	}
	if pk.Valid {
		p.PingKey = pk.String
	}
	return &p
}

func getProjectByPingKey(pingKey string) *Project {
	var p Project
	var pk sql.NullString
	err := db.QueryRow("SELECT id,code,name,owner_id,api_key,api_key_readonly,badge_key,ping_key,show_slugs FROM projects WHERE ping_key=?", pingKey).Scan(&p.ID, &p.Code, &p.Name, &p.OwnerID, &p.APIKey, &p.APIKeyReadonly, &p.BadgeKey, &pk, &p.ShowSlugs)
	if err != nil {
		return nil
	}
	if pk.Valid {
		p.PingKey = pk.String
	}
	return &p
}

func (p *Project) compareAPIKey(key string) bool {
	expected := p.APIKey
	if key[:4] == "hcr_" {
		expected = p.APIKeyReadonly
	}
	if expected == "" {
		return false
	}
	parts := fmt.Sprintf("%s", expected)
	// Check if the key matches
	if parts == key {
		return true
	}
	// For hashed keys: check prefix match
	if len(parts) > 8 && parts[8] == '.' {
		prefix := parts[:8]
		digest := parts[9:]
		expectedDigest := hmacSHA256(secretKey, key)
		if prefix == key[4:12] && digest == expectedDigest {
			return true
		}
	}
	return false
}

func getChannelByCode(code string) *Channel {
	var ch Channel
	var ln sql.NullString
	var lnd sql.NullInt64
	err := db.QueryRow("SELECT id,name,code,project_id,kind,value,email_verified,disabled,last_notify,last_notify_duration,last_error FROM channels WHERE code=?", code).Scan(&ch.ID, &ch.Name, &ch.Code, &ch.ProjectID, &ch.Kind, &ch.Value, &ch.EmailVerified, &ch.Disabled, &ln, &lnd, &ch.LastError)
	if err != nil {
		return nil
	}
	if ln.Valid {
		ch.LastNotify = &ln.String
	}
	if lnd.Valid {
		ch.LastNotifyDuration = &lnd.Int64
	}
	return &ch
}

func getCheckByBadgeKey(badgeKey string) *Check {
	var c Check
	var lastPing, lastStart, lastStartRid, alertAfter sql.NullString
	var lastDuration sql.NullInt64
	var fsInt, fbInt, fhbInt, fdfInt, mrInt int
	err := db.QueryRow(`SELECT id,name,slug,tags,code,kind,desc,project_id,created,timeout,grace,schedule,tz,filter_subject,filter_body,filter_http_body,filter_default_fail,start_kw,success_kw,failure_kw,methods,manual_resume,badge_key,n_pings,last_ping,last_start,last_start_rid,last_duration,has_confirmation_link,alert_after,status FROM checks WHERE badge_key=?`, badgeKey).Scan(
		&c.ID, &c.Name, &c.Slug, &c.Tags, &c.Code, &c.Kind, &c.Desc, &c.ProjectID, &c.Created, &c.Timeout, &c.Grace, &c.Schedule, &c.TZ, &fsInt, &fbInt, &fhbInt, &fdfInt, &c.StartKW, &c.SuccessKW, &c.FailureKW, &c.Methods, &mrInt, &c.BadgeKey, &c.NPings, &lastPing, &lastStart, &lastStartRid, &lastDuration, &c.HasConfirmationLink, &alertAfter, &c.Status)
	if err != nil {
		return nil
	}
	c.FilterSubject = fsInt != 0
	c.FilterBody = fbInt != 0
	c.FilterHTTPBody = fhbInt != 0
	c.FilterDefaultFail = fdfInt != 0
	c.ManualResume = mrInt != 0
	if lastPing.Valid {
		c.LastPing = &lastPing.String
	}
	if lastStart.Valid {
		c.LastStart = &lastStart.String
	}
	return &c
}

var _ = uuid.UUID{} // ensure import

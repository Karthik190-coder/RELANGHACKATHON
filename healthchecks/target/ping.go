package main

import (
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
)

func handlePing(w http.ResponseWriter, r *http.Request) {
	code := r.PathValue("code")
	performPing(w, r, code, "success", nil)
}

func handlePingFail(w http.ResponseWriter, r *http.Request) {
	code := r.PathValue("code")
	performPing(w, r, code, "fail", nil)
}

func handlePingStart(w http.ResponseWriter, r *http.Request) {
	code := r.PathValue("code")
	performPing(w, r, code, "start", nil)
}

func handlePingLog(w http.ResponseWriter, r *http.Request) {
	code := r.PathValue("code")
	performPing(w, r, code, "log", nil)
}

func handlePingExitStatus(w http.ResponseWriter, r *http.Request) {
	code := r.PathValue("code")
	esStr := r.PathValue("exitstatus")
	es, err := strconv.Atoi(esStr)
	if err != nil || es > 255 {
		w.WriteHeader(400)
		fmt.Fprint(w, "invalid url format")
		return
	}
	if es > 0 {
		performPing(w, r, code, "fail", &es)
	} else {
		performPing(w, r, code, "success", &es)
	}
}

func handlePingBySlug(w http.ResponseWriter, r *http.Request) {
	pingKey := r.PathValue("pingkey")
	slug := r.PathValue("slug")
	performPingBySlug(w, r, pingKey, slug, "success", nil)
}

func handlePingBySlugAction(w http.ResponseWriter, r *http.Request) {
	pingKey := r.PathValue("pingkey")
	slug := r.PathValue("slug")
	action := "success"
	if strings.HasSuffix(r.URL.Path, "/fail") {
		action = "fail"
	} else if strings.HasSuffix(r.URL.Path, "/start") {
		action = "start"
	} else if strings.HasSuffix(r.URL.Path, "/log") {
		action = "log"
	}
	performPingBySlug(w, r, pingKey, slug, action, nil)
}

func handlePingBySlugExit(w http.ResponseWriter, r *http.Request) {
	pingKey := r.PathValue("pingkey")
	slug := r.PathValue("slug")
	esStr := r.PathValue("exitstatus")
	es, err := strconv.Atoi(esStr)
	if err != nil || es > 255 {
		w.WriteHeader(400)
		fmt.Fprint(w, "invalid url format")
		return
	}
	action := "success"
	if es > 0 {
		action = "fail"
	}
	performPingBySlug(w, r, pingKey, slug, action, &es)
}

func performPingBySlug(w http.ResponseWriter, r *http.Request, pingKey, slug, action string, exitStatus *int) {
	if slug != strings.ToLower(slug) {
		w.WriteHeader(400)
		fmt.Fprint(w, "invalid url format")
		return
	}

	// Find check by slug and ping_key
	var checkID int64
	err := db.QueryRow("SELECT checks.id FROM checks INNER JOIN projects ON checks.project_id=projects.id WHERE checks.slug=? AND projects.ping_key=?", slug, pingKey).Scan(&checkID)
	if err != nil {
		created := false
		if r.URL.Query().Get("create") == "1" {
			// Auto-provision
			var proj Project
			err := db.QueryRow("SELECT id,code,name,owner_id,api_key,api_key_readonly,badge_key,ping_key,show_slugs FROM projects WHERE ping_key=?", pingKey).Scan(&proj.ID, &proj.Code, &proj.Name, &proj.OwnerID, &proj.APIKey, &proj.APIKeyReadonly, &proj.BadgeKey, &proj.PingKey, &proj.ShowSlugs)
			if err == nil {
				check, err := createCheck(proj.ID, slug, slug, "", "", "simple", 86400, 3600, "* * * * *", "UTC", "", false, false, false, false, false, "", "", "")
				if err == nil {
					checkID = check.ID
					created = true
				}
			}
		}
		if !created {
			w.WriteHeader(404)
			fmt.Fprint(w, "not found")
			return
		}
	}

	performPingByID(w, r, checkID, action, exitStatus, created)
}

func performPing(w http.ResponseWriter, r *http.Request, code, action string, exitStatus *int) {
	var checkID int64
	err := db.QueryRow("SELECT id FROM checks WHERE code=?", code).Scan(&checkID)
	if err != nil {
		w.WriteHeader(404)
		fmt.Fprint(w, "not found")
		return
	}
	performPingByID(w, r, checkID, action, exitStatus, false)
}

func performPingByID(w http.ResponseWriter, r *http.Request, checkID int64, action string, exitStatus *int, created bool) {
	check, err := getCheckByID(checkID)
	if err != nil {
		w.WriteHeader(404)
		fmt.Fprint(w, "not found")
		return
	}

	if exitStatus != nil && *exitStatus > 0 {
		action = "fail"
	}

	if check.Methods == "POST" && r.Method != "POST" {
		action = "ign"
	}

	body, _ := io.ReadAll(r.Body)
	if len(body) > pingBodyLimit {
		body = body[:pingBodyLimit]
	}

	remoteAddr := r.Header.Get("X-Forwarded-For")
	if remoteAddr == "" {
		remoteAddr = r.RemoteAddr
	}
	remoteAddr = strings.Split(remoteAddr, ",")[0]
	scheme := r.Header.Get("X-Forwarded-Proto")
	if scheme == "" {
		scheme = "http"
	}
	ua := r.Header.Get("User-Agent")
	if len(ua) > 200 {
		ua = ua[:200]
	}

	var rid *string
	ridStr := r.URL.Query().Get("rid")
	if ridStr != "" {
		rid = &ridStr
	}

	nowStr := nowISO()

	// Update check status
	if check.Status == "paused" && check.ManualResume {
		action = "ign"
	}

	if action == "start" {
		db.Exec("UPDATE checks SET last_start=? WHERE id=?", nowStr, checkID)
	} else if action == "ign" || action == "log" {
		// Don't update last_ping
	} else {
		newStatus := "up"
		if action == "fail" {
			newStatus = "down"
		}

		if check.Status != newStatus {
			reason := ""
			if action == "fail" {
				reason = "fail"
			}
			db.Exec("INSERT INTO flips (owner_id, created, old_status, new_status, reason) VALUES (?,?,?,?,?)", checkID, nowStr, check.Status, newStatus, reason)
		}

		db.Exec("UPDATE checks SET last_ping=?, status=?, n_pings=n_pings+1 WHERE id=?", nowStr, newStatus, checkID)
	}

	// Insert ping
	var pingKind *string
	if action != "success" && action != "fail" {
		pingKind = &action
	}

	db.Exec("INSERT INTO pings (owner_id, created, kind, scheme, remote_addr, method, ua, body_raw, rid, exitstatus) VALUES (?,?,?,?,?,?,?,?,?,?)",
		checkID, nowStr, pingKind, scheme, remoteAddr, r.Method, ua, body, rid, exitStatus)

	if created {
		w.Header().Set("Content-Type", "text/html")
		w.WriteHeader(201)
		fmt.Fprint(w, "Created")
		return
	}

	w.Header().Set("Content-Type", "text/html")
	w.Header().Set("Ping-Body-Limit", strconv.Itoa(pingBodyLimit))
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.WriteHeader(200)
	fmt.Fprint(w, "OK")
}



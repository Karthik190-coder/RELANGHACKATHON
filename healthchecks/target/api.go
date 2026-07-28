package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
)

func handleAPIListChecks(w http.ResponseWriter, r *http.Request) {
	v := getAPIVersion(r)
	project := authorizeAPIKey(r, true, true)
	if project == nil {
		jsonError("missing api key", 401)(w, r)
		return
	}

	readonly := false
	apiKey := parseAPIKey(r)
	if strings.HasPrefix(apiKey, "hcr_") || apiKey == project.APIKeyReadonly {
		readonly = true
	}

	rows, err := db.Query("SELECT id,name,slug,tags,code,kind,desc,project_id,created,timeout,grace,schedule,tz,filter_subject,filter_body,filter_http_body,filter_default_fail,start_kw,success_kw,failure_kw,methods,manual_resume,badge_key,n_pings,last_ping,last_start,last_start_rid,last_duration,has_confirmation_link,alert_after,status FROM checks WHERE project_id=?", project.ID)
	if err != nil {
		jsonError("db error", 500)(w, r)
		return
	}
	defer rows.Close()

	checks := []map[string]interface{}{}
	for rows.Next() {
		var c Check
		var lastPing, lastStart, lastStartRid, alertAfter sqlNullStr()
		var lastDuration sqlNullInt()
		var fsInt, fbInt, fhbInt, fdfInt, mrInt int
		rows.Scan(&c.ID, &c.Name, &c.Slug, &c.Tags, &c.Code, &c.Kind, &c.Desc, &c.ProjectID, &c.Created, &c.Timeout, &c.Grace, &c.Schedule, &c.TZ, &fsInt, &fbInt, &fhbInt, &fdfInt, &c.StartKW, &c.SuccessKW, &c.FailureKW, &c.Methods, &mrInt, &c.BadgeKey, &c.NPings, &lastPing, &lastStart, &lastStartRid, &lastDuration, &c.HasConfirmationLink, &alertAfter, &c.Status)
		c.FilterSubject = fsInt != 0
		c.FilterBody = fbInt != 0
		c.FilterHTTPBody = fhbInt != 0
		c.FilterDefaultFail = fdfInt != 0
		c.ManualResume = mrInt != 0
		c.LastPing = nullStr(lastPing)
		c.LastStart = nullStr(lastStart)
		checks = append(checks, c.toDict(v, readonly))
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"checks": checks})
}

func handleAPICreateCheck(w http.ResponseWriter, r *http.Request) {
	v := getAPIVersion(r)
	project := authorizeAPIKey(r, true, false)
	if project == nil {
		jsonError("missing api key", 401)(w, r)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		jsonError("could not parse request body", 400)(w, r)
		return
	}

	var spec CheckSpec
	if err := json.Unmarshal(body, &spec); err != nil {
		jsonError("could not parse request body", 400)(w, r)
		return
	}

	// Check null values - the original replaces null with float
	var raw map[string]interface{}
	json.Unmarshal(body, &raw)
	for k, v := range raw {
		if v == nil {
			jsonError(fmt.Sprintf("json validation error: %s is not a number", k), 400)(w, r)
			return
		}
	}

	// Validate timeout
	if spec.Timeout != nil && *spec.Timeout < 60 {
		jsonError("json validation error: timeout is too small", 400)(w, r)
		return
	}

	// Validate methods
	if spec.Methods != nil && *spec.Methods != "" && *spec.Methods != "POST" {
		jsonError("json validation error: methods has unexpected value", 400)(w, r)
		return
	}

	// Look up existing check
	existing := lookupCheckBySpec(project.ID, spec)
	if existing != nil {
		existing.updateFromSpec(spec, v)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(200)
		json.NewEncoder(w).Encode(existing.toDict(v, false))
		return
	}

	// Create new check
	profile := getProfile(project.OwnerID)
	usedChecks := countUserChecks(project.OwnerID)
	if usedChecks >= profile.CheckLimit {
		w.WriteHeader(403)
		return
	}

	check, err := createCheck(
		project.ID,
		derefStr(spec.Name), derefStr(spec.Slug), derefStr(spec.Tags), derefStr(spec.Desc),
		"", derefInt(spec.Timeout), derefInt(spec.Grace), derefStr(spec.Schedule), derefStr(spec.TZ),
		derefStr(spec.Methods), derefBool(spec.ManualResume),
		derefBool(spec.FilterSubject), derefBool(spec.FilterBody), derefBool(spec.FilterHTTPBody), derefBool(spec.FilterDefaultFail),
		derefStr(spec.StartKW), derefStr(spec.SuccessKW), derefStr(spec.FailureKW),
	)
	if err != nil {
		jsonError("db error", 500)(w, r)
		return
	}

	check.updateFromSpec(spec, v)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(201)
	json.NewEncoder(w).Encode(check.toDict(v, false))
}

func handleAPISingleCheck(w http.ResponseWriter, r *http.Request) {
	v := getAPIVersion(r)
	code := r.PathValue("code")

	if r.Method == "POST" {
		handleAPIUpdateCheck(w, r)
		return
	}
	if r.Method == "DELETE" {
		handleAPIDeleteCheck(w, r)
		return
	}

	// GET
	project := authorizeAPIKey(r, true, true)
	if project == nil {
		jsonError("missing api key", 401)(w, r)
		return
	}

	check, err := getCheckByCode(code)
	if err != nil || check == nil {
		w.WriteHeader(404)
		return
	}
	if check.ProjectID != project.ID {
		w.WriteHeader(403)
		return
	}

	readonly := false
	apiKey := parseAPIKey(r)
	if strings.HasPrefix(apiKey, "hcr_") || apiKey == project.APIKeyReadonly {
		readonly = true
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(check.toDict(v, readonly))
}

func handleAPIUpdateCheck(w http.ResponseWriter, r *http.Request) {
	v := getAPIVersion(r)
	code := r.PathValue("code")

	project := authorizeAPIKey(r, true, false)
	if project == nil {
		jsonError("missing api key", 401)(w, r)
		return
	}

	check, err := getCheckByCode(code)
	if err != nil || check == nil {
		w.WriteHeader(404)
		return
	}
	if check.ProjectID != project.ID {
		w.WriteHeader(403)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		jsonError("could not parse request body", 400)(w, r)
		return
	}

	var spec CheckSpec
	if err := json.Unmarshal(body, &spec); err != nil {
		jsonError("could not parse request body", 400)(w, r)
		return
	}

	// Check null values
	var raw map[string]interface{}
	json.Unmarshal(body, &raw)
	for k, v := range raw {
		if v == nil {
			jsonError(fmt.Sprintf("json validation error: %s is not a number", k), 400)(w, r)
			return
		}
	}

	check.updateFromSpec(spec, v)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(check.toDict(v, false))
}

func handleAPIDeleteCheck(w http.ResponseWriter, r *http.Request) {
	v := getAPIVersion(r)
	code := r.PathValue("code")

	project := authorizeAPIKey(r, true, false)
	if project == nil {
		jsonError("missing api key", 401)(w, r)
		return
	}

	check, err := getCheckByCode(code)
	if err != nil || check == nil {
		w.WriteHeader(404)
		return
	}
	if check.ProjectID != project.ID {
		w.WriteHeader(403)
		return
	}

	// Delete check
	throwawayUUID := generateUUID()
	throwawaySlug := generateUUID()
	db.Exec("UPDATE checks SET code=?, slug=? WHERE id=?", throwawayUUID, throwawaySlug, check.ID)
	db.Exec("DELETE FROM check_channels WHERE check_id=?", check.ID)
	db.Exec("DELETE FROM pings WHERE owner_id=?", check.ID)
	db.Exec("DELETE FROM flips WHERE owner_id=?", check.ID)
	db.Exec("DELETE FROM checks WHERE id=?", check.ID)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(check.toDict(v, false))
}

func handleAPIPause(w http.ResponseWriter, r *http.Request) {
	v := getAPIVersion(r)
	code := r.PathValue("code")

	project := authorizeAPIKey(r, true, false)
	if project == nil {
		jsonError("missing api key", 401)(w, r)
		return
	}

	check, err := getCheckByCode(code)
	if err != nil || check == nil {
		w.WriteHeader(404)
		return
	}
	if check.ProjectID != project.ID {
		w.WriteHeader(403)
		return
	}

	if check.Status == "paused" {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(check.toDict(v, false))
		return
	}

	nowStr := nowISO()
	db.Exec("INSERT INTO flips (owner_id, created, old_status, new_status, processed) VALUES (?,?,?,?,?)", check.ID, nowStr, check.Status, "paused", nowStr)
	db.Exec("UPDATE checks SET status='paused', last_start=NULL, alert_after=NULL WHERE id=?", check.ID)

	check.Status = "paused"
	check.LastStart = nil
	check.AlertAfter = nil

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(check.toDict(v, false))
}

func handleAPIResume(w http.ResponseWriter, r *http.Request) {
	v := getAPIVersion(r)
	code := r.PathValue("code")

	project := authorizeAPIKey(r, true, false)
	if project == nil {
		jsonError("missing api key", 401)(w, r)
		return
	}

	check, err := getCheckByCode(code)
	if err != nil || check == nil {
		w.WriteHeader(404)
		return
	}
	if check.ProjectID != project.ID {
		w.WriteHeader(403)
		return
	}

	if check.Status != "paused" {
		w.WriteHeader(409)
		fmt.Fprint(w, "check is not paused")
		return
	}

	nowStr := nowISO()
	db.Exec("INSERT INTO flips (owner_id, created, old_status, new_status, processed) VALUES (?,?,?,?,?)", check.ID, nowStr, "paused", "new", nowStr)
	db.Exec("UPDATE checks SET status='new', last_start=NULL, last_ping=NULL, alert_after=NULL WHERE id=?", check.ID)

	check.Status = "new"
	check.LastStart = nil
	check.LastPing = nil
	check.AlertAfter = nil

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(check.toDict(v, false))
}

func handleAPIPings(w http.ResponseWriter, r *http.Request) {
	v := getAPIVersion(r)
	code := r.PathValue("code")

	project := authorizeAPIKey(r, true, false)
	if project == nil {
		jsonError("missing api key", 401)(w, r)
		return
	}

	check, err := getCheckByCode(code)
	if err != nil || check == nil {
		w.WriteHeader(404)
		return
	}
	if check.ProjectID != project.ID {
		w.WriteHeader(403)
		return
	}

	rows, err := db.Query("SELECT id,n,owner_id,created,kind,scheme,remote_addr,method,ua,body_raw,rid,exitstatus FROM pings WHERE owner_id=? ORDER BY id DESC LIMIT 100", check.ID)
	if err != nil {
		jsonError("db error", 500)(w, r)
		return
	}
	defer rows.Close()

	pings := []map[string]interface{}{}
	for rows.Next() {
		var p Ping
		var kind sqlNullStr()
		var rid sqlNullStr()
		var exitstatus sqlNullInt()
		rows.Scan(&p.ID, &p.N, &p.OwnerID, &p.Created, &kind, &p.Scheme, &p.RemoteAddr, &p.Method, &p.UA, &p.BodyRaw, &rid, &exitstatus)
		p.Kind = nullStr(kind)
		p.RID = nullStr(rid)
		p.ExitStatus = nullInt(exitstatus)

		pingDict := map[string]interface{}{
			"type":        "success",
			"date":        p.Created,
			"n":           p.N,
			"scheme":      p.Scheme,
			"remote_addr": p.RemoteAddr,
			"method":      p.Method,
			"ua":          p.UA,
			"rid":         p.RID,
			"body_url":    nil,
		}
		if p.Kind != nil && *p.Kind != "" {
			pingDict["type"] = *p.Kind
		}
		if len(p.BodyRaw) > 0 {
			pingDict["body_url"] = fmt.Sprintf("%s/api/v%d/checks/%s/pings/%d/body", siteRoot, v, check.Code, p.N)
		}
		pings = append(pings, pingDict)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"pings": pings})
}

func handleAPIPingBody(w http.ResponseWriter, r *http.Request) {
	code := r.PathValue("code")
	nStr := r.PathValue("n")
	n, _ := strconv.ParseInt(nStr, 10, 64)

	project := authorizeAPIKey(r, true, false)
	if project == nil {
		jsonError("missing api key", 401)(w, r)
		return
	}

	check, err := getCheckByCode(code)
	if err != nil || check == nil {
		w.WriteHeader(404)
		return
	}
	if check.ProjectID != project.ID {
		w.WriteHeader(403)
		return
	}

	var body []byte
	err = db.QueryRow("SELECT body_raw FROM pings WHERE owner_id=? AND n=?", check.ID, n).Scan(&body)
	if err != nil || len(body) == 0 {
		w.WriteHeader(404)
		return
	}

	w.Header().Set("Content-Type", "text/plain")
	w.Write(body)
}

func handleAPIChannels(w http.ResponseWriter, r *http.Request) {
	project := authorizeAPIKey(r, true, false)
	if project == nil {
		jsonError("missing api key", 401)(w, r)
		return
	}

	rows, err := db.Query("SELECT id,name,code,kind FROM channels WHERE project_id=?", project.ID)
	if err != nil {
		jsonError("db error", 500)(w, r)
		return
	}
	defer rows.Close()

	channels := []map[string]string{}
	for rows.Next() {
		var id int64
		var name, code, kind string
		rows.Scan(&id, &name, &code, &kind)
		channels = append(channels, map[string]string{"id": code, "name": name, "kind": kind})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"channels": channels})
}

func handleAPIBadges(w http.ResponseWriter, r *http.Request) {
	project := authorizeAPIKey(r, true, false)
	if project == nil {
		jsonError("missing api key", 401)(w, r)
		return
	}

	tags := map[string]bool{"*": true}
	rows, err := db.Query("SELECT tags FROM checks WHERE project_id=?", project.ID)
	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var tagsStr string
			rows.Scan(&tagsStr)
			for _, t := range strings.Fields(tagsStr) {
				if t != "" {
					tags[t] = true
				}
			}
		}
	}

	badges := map[string]interface{}{}
	for tag := range tags {
		badges[tag] = map[string]string{
			"svg":      fmt.Sprintf("%s/badge/%s/%s/%s.svg", siteRoot, project.BadgeKey, base64HMAC(project.BadgeKey, tag)+"-2", tag),
			"svg3":     fmt.Sprintf("%s/badge/%s/%s/%s.svg", siteRoot, project.BadgeKey, base64HMAC(project.BadgeKey, tag), tag),
			"json":     fmt.Sprintf("%s/badge/%s/%s/%s.json", siteRoot, project.BadgeKey, base64HMAC(project.BadgeKey, tag)+"-2", tag),
			"json3":    fmt.Sprintf("%s/badge/%s/%s/%s.json", siteRoot, project.BadgeKey, base64HMAC(project.BadgeKey, tag), tag),
			"shields":  fmt.Sprintf("%s/badge/%s/%s/%s.shields", siteRoot, project.BadgeKey, base64HMAC(project.BadgeKey, tag)+"-2", tag),
			"shields3": fmt.Sprintf("%s/badge/%s/%s/%s.shields", siteRoot, project.BadgeKey, base64HMAC(project.BadgeKey, tag), tag),
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"badges": badges})
}

func handleAPIFlips(w http.ResponseWriter, r *http.Request) {
	code := r.PathValue("code")

	project := authorizeAPIKey(r, true, false)
	if project == nil {
		jsonError("missing api key", 401)(w, r)
		return
	}

	check, err := getCheckByCode(code)
	if err != nil || check == nil {
		w.WriteHeader(404)
		return
	}
	if check.ProjectID != project.ID {
		w.WriteHeader(403)
		return
	}

	rows, err := db.Query("SELECT id,owner_id,created,processed,old_status,new_status,reason FROM flips WHERE owner_id=? ORDER BY id DESC", check.ID)
	if err != nil {
		jsonError("db error", 500)(w, r)
		return
	}
	defer rows.Close()

	flips := []map[string]interface{}{}
	for rows.Next() {
		var f Flip
		var processed sqlNullStr()
		rows.Scan(&f.ID, &f.OwnerID, &f.Created, &processed, &f.OldStatus, &f.NewStatus, &f.Reason)
		f.Processed = nullStr(processed)
		up := 0
		if f.NewStatus == "up" {
			up = 1
		}
		flips = append(flips, map[string]interface{}{
			"timestamp": strings.Replace(f.Created, ".", "", 1),
			"up":        up,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"flips": flips})
}

func handleAPINotificationStatus(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain")
	w.WriteHeader(200)
	fmt.Fprint(w, "")
}

func handleAPIBounces(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain")
	w.WriteHeader(200)
	fmt.Fprint(w, "OK")
}

func handleAPIOptions(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Headers", "X-Api-Key")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	w.Header().Set("Access-Control-Max-Age", "600")
	w.WriteHeader(204)
}

func handleAPIPutChecks(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Headers", "X-Api-Key")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
	w.Header().Set("Access-Control-Max-Age", "600")
	w.WriteHeader(405)
}

func handleAPIPatchChecks(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Headers", "X-Api-Key")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
	w.Header().Set("Access-Control-Max-Age", "600")
	w.WriteHeader(405)
}

// Helper types for nullable SQL scanning
type sqlNullStr = sql.NullString
type sqlNullInt = sql.NullInt64

func sqlNullStr() sql.NullString { return sql.NullString{} }
func sqlNullInt() sql.NullInt64  { return sql.NullInt64{} }

func nullStr(ns sql.NullString) *string {
	if ns.Valid {
		return &ns.String
	}
	return nil
}

func nullInt(ni sql.NullInt64) *int64 {
	if ni.Valid {
		return &ni.Int64
	}
	return nil
}

func derefStr(s *string) string {
	if s != nil {
		return *s
	}
	return ""
}

func derefInt(i *int64) int64 {
	if i != nil {
		return *i
	}
	return 0
}

func derefBool(b *bool) bool {
	if b != nil {
		return *b
	}
	return false
}

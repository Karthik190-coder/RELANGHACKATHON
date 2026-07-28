package main

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha1"
	"crypto/sha256"
	"database/sql"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	_ "github.com/glebarez/go-sqlite"
)

var db *sql.DB
var siteRoot = "http://localhost:8000"
var secretKey = "---"
var pingBodyLimit = 10000

func main() {
	if v := os.Getenv("SITE_ROOT"); v != "" {
		siteRoot = strings.TrimSuffix(v, "/")
	}
	if v := os.Getenv("SECRET_KEY"); v != "" {
		secretKey = v
	}

	var err error
	db, err = sql.Open("sqlite", "./healthchecks.db?_journal_mode=WAL&_busy_timeout=5000&_pragma=transaction_mode(IMMEDIATE)")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	initDB()

	mux := http.NewServeMux()

	// Test reset
	mux.HandleFunc("GET /__test/reset/", handleTestReset)
	mux.HandleFunc("POST /__test/reset/", handleTestReset)

	// API v1/v2/v3 - checks
	mux.HandleFunc("GET /api/v1/checks/", handleAPIListChecks)
	mux.HandleFunc("POST /api/v1/checks/", handleAPICreateCheck)
	mux.HandleFunc("GET /api/v2/checks/", handleAPIListChecks)
	mux.HandleFunc("POST /api/v2/checks/", handleAPICreateCheck)
	mux.HandleFunc("GET /api/v3/checks/", handleAPIListChecks)
	mux.HandleFunc("POST /api/v3/checks/", handleAPICreateCheck)

	mux.HandleFunc("GET /api/v1/checks/{code}", handleAPISingleCheck)
	mux.HandleFunc("POST /api/v1/checks/{code}", handleAPIUpdateCheck)
	mux.HandleFunc("DELETE /api/v1/checks/{code}", handleAPIDeleteCheck)
	mux.HandleFunc("GET /api/v2/checks/{code}", handleAPISingleCheck)
	mux.HandleFunc("POST /api/v2/checks/{code}", handleAPIUpdateCheck)
	mux.HandleFunc("DELETE /api/v2/checks/{code}", handleAPIDeleteCheck)
	mux.HandleFunc("GET /api/v3/checks/{code}", handleAPISingleCheck)
	mux.HandleFunc("POST /api/v3/checks/{code}", handleAPIUpdateCheck)
	mux.HandleFunc("DELETE /api/v3/checks/{code}", handleAPIDeleteCheck)

	// Pause/Resume
	mux.HandleFunc("POST /api/v1/checks/{code}/pause", handleAPIPause)
	mux.HandleFunc("POST /api/v1/checks/{code}/resume", handleAPIResume)
	mux.HandleFunc("POST /api/v2/checks/{code}/pause", handleAPIPause)
	mux.HandleFunc("POST /api/v2/checks/{code}/resume", handleAPIResume)
	mux.HandleFunc("POST /api/v3/checks/{code}/pause", handleAPIPause)
	mux.HandleFunc("POST /api/v3/checks/{code}/resume", handleAPIResume)

	// Pings list
	mux.HandleFunc("GET /api/v1/checks/{code}/pings/", handleAPIPings)
	mux.HandleFunc("GET /api/v2/checks/{code}/pings/", handleAPIPings)
	mux.HandleFunc("GET /api/v3/checks/{code}/pings/", handleAPIPings)

	// Ping body
	mux.HandleFunc("GET /api/v1/checks/{code}/pings/{n}/body", handleAPIPingBody)
	mux.HandleFunc("GET /api/v2/checks/{code}/pings/{n}/body", handleAPIPingBody)
	mux.HandleFunc("GET /api/v3/checks/{code}/pings/{n}/body", handleAPIPingBody)

	// Channels
	mux.HandleFunc("GET /api/v1/channels/", handleAPIChannels)
	mux.HandleFunc("GET /api/v2/channels/", handleAPIChannels)
	mux.HandleFunc("GET /api/v3/channels/", handleAPIChannels)

	// Badges
	mux.HandleFunc("GET /api/v1/badges/", handleAPIBadges)
	mux.HandleFunc("GET /api/v2/badges/", handleAPIBadges)
	mux.HandleFunc("GET /api/v3/badges/", handleAPIBadges)

	// Flips
	mux.HandleFunc("GET /api/v1/checks/{code}/flips/", handleAPIFlips)
	mux.HandleFunc("GET /api/v2/checks/{code}/flips/", handleAPIFlips)
	mux.HandleFunc("GET /api/v3/checks/{code}/flips/", handleAPIFlips)

	// Notification status
	mux.HandleFunc("POST /api/v1/notifications/{code}/status", handleAPINotificationStatus)
	mux.HandleFunc("POST /api/v2/notifications/{code}/status", handleAPINotificationStatus)
	mux.HandleFunc("POST /api/v3/notifications/{code}/status", handleAPINotificationStatus)

	// Bounces
	mux.HandleFunc("POST /api/v1/bounces/", handleAPIBounces)
	mux.HandleFunc("POST /api/v2/bounces/", handleAPIBounces)
	mux.HandleFunc("POST /api/v3/bounces/", handleAPIBounces)

	// OPTIONS for checks
	mux.HandleFunc("OPTIONS /api/v1/checks/{code}", handleAPIOptions)
	mux.HandleFunc("OPTIONS /api/v2/checks/{code}", handleAPIOptions)
	mux.HandleFunc("OPTIONS /api/v3/checks/{code}", handleAPIOptions)
	mux.HandleFunc("OPTIONS /api/v1/checks/", handleAPIOptions)
	mux.HandleFunc("OPTIONS /api/v2/checks/", handleAPIOptions)
	mux.HandleFunc("OPTIONS /api/v3/checks/", handleAPIOptions)
	mux.HandleFunc("PUT /api/v1/checks/", handleAPIPutChecks)
	mux.HandleFunc("PUT /api/v2/checks/", handleAPIPutChecks)
	mux.HandleFunc("PUT /api/v3/checks/", handleAPIPutChecks)
	mux.HandleFunc("PATCH /api/v1/checks/", handleAPIPatchChecks)
	mux.HandleFunc("PATCH /api/v2/checks/", handleAPIPatchChecks)
	mux.HandleFunc("PATCH /api/v3/checks/", handleAPIPatchChecks)

	// Ping by UUID
	mux.HandleFunc("GET /ping/{code}", handlePing)
	mux.HandleFunc("POST /ping/{code}", handlePing)
	mux.HandleFunc("GET /ping/{code}/fail", handlePingFail)
	mux.HandleFunc("POST /ping/{code}/fail", handlePingFail)
	mux.HandleFunc("GET /ping/{code}/start", handlePingStart)
	mux.HandleFunc("POST /ping/{code}/start", handlePingStart)
	mux.HandleFunc("GET /ping/{code}/log", handlePingLog)
	mux.HandleFunc("POST /ping/{code}/log", handlePingLog)
	mux.HandleFunc("GET /ping/{code}/{exitstatus}", handlePingExitStatus)
	mux.HandleFunc("POST /ping/{code}/{exitstatus}", handlePingExitStatus)

	// Ping by slug
	mux.HandleFunc("GET /ping/{pingkey}/{slug}", handlePingBySlug)
	mux.HandleFunc("POST /ping/{pingkey}/{slug}", handlePingBySlug)
	mux.HandleFunc("GET /ping/{pingkey}/{slug}/fail", handlePingBySlugAction)
	mux.HandleFunc("POST /ping/{pingkey}/{slug}/fail", handlePingBySlugAction)
	mux.HandleFunc("GET /ping/{pingkey}/{slug}/start", handlePingBySlugAction)
	mux.HandleFunc("POST /ping/{pingkey}/{slug}/start", handlePingBySlugAction)
	mux.HandleFunc("GET /ping/{pingkey}/{slug}/log", handlePingBySlugAction)
	mux.HandleFunc("POST /ping/{pingkey}/{slug}/log", handlePingBySlugAction)
	mux.HandleFunc("GET /ping/{pingkey}/{slug}/{exitstatus}", handlePingBySlugExit)
	mux.HandleFunc("POST /ping/{pingkey}/{slug}/{exitstatus}", handlePingBySlugExit)

	// Badge rendering
	mux.HandleFunc("GET /badge/{key}/{signature}/{tag}.{fmt}", handleBadge)
	mux.HandleFunc("GET /badge/{key}/{signature}.{fmt}", handleBadgeAll)
	mux.HandleFunc("GET /b/{states}/{key}.{fmt}", handleCheckBadge)

	// Accounts
	mux.HandleFunc("GET /accounts/login/", handleLogin)
	mux.HandleFunc("POST /accounts/login/", handleLoginPost)
	mux.HandleFunc("POST /accounts/logout/", handleLogout)
	mux.HandleFunc("GET /accounts/signup/csrf/", handleSignupCSRF)
	mux.HandleFunc("POST /accounts/signup/", handleSignup)
	mux.HandleFunc("GET /accounts/signup/", handleSignup)
	mux.HandleFunc("GET /accounts/login_link_sent/", handleLoginLinkSent)
	mux.HandleFunc("GET /accounts/check_token/{username}/{token}", handleCheckToken)
	mux.HandleFunc("POST /accounts/check_token/{username}/{token}", handleCheckToken)
	mux.HandleFunc("GET /accounts/profile/", handleProfile)
	mux.HandleFunc("POST /accounts/profile/", handleProfile)
	mux.HandleFunc("GET /accounts/profile/appearance/", handleAppearance)
	mux.HandleFunc("POST /accounts/profile/appearance/", handleAppearance)
	mux.HandleFunc("GET /accounts/profile/notifications/", handleNotifications)
	mux.HandleFunc("POST /accounts/profile/notifications/", handleNotifications)
	mux.HandleFunc("GET /accounts/close/", handleClose)
	mux.HandleFunc("POST /accounts/close/", handleClose)
	mux.HandleFunc("GET /accounts/set_password/", handleSetPassword)
	mux.HandleFunc("POST /accounts/set_password/", handleSetPassword)
	mux.HandleFunc("GET /accounts/change_email/", handleChangeEmail)
	mux.HandleFunc("POST /accounts/change_email/", handleChangeEmail)
	mux.HandleFunc("POST /accounts/unsubscribe_reports/{signed_username}", handleUnsubscribeReports)
	mux.HandleFunc("GET /accounts/unsubscribe_reports/{signed_username}", handleUnsubscribeReports)
	mux.HandleFunc("GET /accounts/two_factor/webauthn/", handleWebAuthn)
	mux.HandleFunc("GET /accounts/two_factor/totp/", handleTOTP)
	mux.HandleFunc("GET /accounts/login/two_factor/", handleLogin2FA)
	mux.HandleFunc("GET /accounts/login/two_factor/totp/", handleLoginTOTP)

	// Projects
	mux.HandleFunc("GET /projects/add/", handleAddProject)
	mux.HandleFunc("POST /projects/add/", handleAddProject)
	mux.HandleFunc("GET /projects/{code}/settings/", handleProjectSettings)
	mux.HandleFunc("POST /projects/{code}/settings/", handleProjectSettings)
	mux.HandleFunc("POST /projects/{code}/remove/", handleRemoveProject)
	mux.HandleFunc("GET /projects/{code}/checks/", handleProjectChecks)
	mux.HandleFunc("GET /projects/{code}/integrations/", handleProjectIntegrations)
	mux.HandleFunc("GET /projects/{code}/badges/", handleProjectBadges)
	mux.HandleFunc("GET /projects/menu/", handleProjectsMenu)

	// Front checks
	mux.HandleFunc("GET /checks/{code}/details/", handleCheckDetails)
	mux.HandleFunc("POST /checks/{code}/pause/", handleFrontPause)
	mux.HandleFunc("POST /checks/{code}/resume/", handleFrontResume)
	mux.HandleFunc("POST /checks/{code}/remove/", handleFrontRemove)
	mux.HandleFunc("GET /checks/{code}/log/", handleCheckLog)
	mux.HandleFunc("GET /checks/{code}/log_events/", handleCheckLogEvents)
	mux.HandleFunc("GET /checks/{code}/pings/{n}/", handlePingDetails)
	mux.HandleFunc("GET /checks/{code}/pings/{n}/body/", handlePingBodyFront)
	mux.HandleFunc("POST /checks/{code}/name/", handleUpdateName)
	mux.HandleFunc("POST /checks/{code}/timeout/", handleUpdateTimeout)
	mux.HandleFunc("POST /checks/{code}/filtering_rules/", handleFilteringRules)
	mux.HandleFunc("POST /checks/{code}/clear_events/", handleClearEvents)
	mux.HandleFunc("POST /checks/{code}/transfer/", handleTransfer)
	mux.HandleFunc("POST /checks/{code}/copy/", handleCopy)
	mux.HandleFunc("GET /cloaked/{key}/", handleUncloak)

	// Front checks root
	mux.HandleFunc("GET /checks/cron_preview/", handleCronPreview)
	mux.HandleFunc("GET /checks/oncalendar_preview/", handleOnCalendarPreview)
	mux.HandleFunc("GET /checks/validate_schedule/", handleValidateSchedule)
	mux.HandleFunc("POST /checks/add/", handleAddCheckFront)

	// Integrations front
	mux.HandleFunc("GET /integrations/", handleIntegrations)
	mux.HandleFunc("GET /integrations/{code}/checks/", handleChannelChecks)
	mux.HandleFunc("GET /integrations/{code}/name/", handleChannelName)
	mux.HandleFunc("GET /integrations/{code}/edit/", handleEditChannel)
	mux.HandleFunc("GET /integrations/{code}/test/", handleTestNotification)
	mux.HandleFunc("GET /integrations/{code}/remove/", handleRemoveChannel)

	// Integration add pages - generic handler
	mux.HandleFunc("GET /projects/{code}/add_slack/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_slack/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_pushover/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_pushover/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_telegram/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_telegram/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_discord/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_discord/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_gotify/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_gotify/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_pd/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_pd/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_webhook/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_webhook/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_email/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_email/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_sms/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_sms/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_signal/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_signal/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_shell/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_shell/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_whatsapp/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_whatsapp/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_call/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_call/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_zulip/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_zulip/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_mattermost/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_mattermost/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_msteamsw/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_msteamsw/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_opsgenie/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_opsgenie/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_pagertree/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_pagertree/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_victorops/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_victorops/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_rocketchat/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_rocketchat/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_spike/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_spike/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_trello/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_trello/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_pushbullet/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_pushbullet/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_ntfy/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_ntfy/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_github/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_github/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_googlechat/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_googlechat/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_matrix/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_matrix/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_apprise/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_apprise/", handleIntegrationAdd)
	mux.HandleFunc("GET /projects/{code}/add_group/", handleIntegrationAdd)
	mux.HandleFunc("POST /projects/{code}/add_group/", handleIntegrationAdd)

	// Docs
	mux.HandleFunc("GET /docs/", handleDocs)
	mux.HandleFunc("GET /docs/cron/", handleDocsCron)
	mux.HandleFunc("GET /docs/search/", handleDocsSearch)
	mux.HandleFunc("GET /docs/signals/", handleDocsSignals)
	mux.HandleFunc("GET /docs/{doc}/", handleDocPage)

	// Payments
	mux.HandleFunc("GET /billing/", handleBilling)
	mux.HandleFunc("POST /billing/", handleBilling)
	mux.HandleFunc("GET /pricing/", handlePricing)

	// Index
	mux.HandleFunc("GET /", handleIndex)
	mux.HandleFunc("GET /tv/", handleDashboard)

	// Contact vcf
	mux.HandleFunc("GET /contact.vcf", handleContactVCF)

	port := "8000"
	if v := os.Getenv("PORT"); v != "" {
		port = v
	}

	fmt.Printf("Listening on :%s\n", port)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}

func jsonError(msg string, status int) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		json.NewEncoder(w).Encode(map[string]string{"error": msg})
	}
}

func jsonString(v interface{}, status int) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		json.NewEncoder(w).Encode(v)
	}
}

func htmlResponse(w http.ResponseWriter, status int) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(status)
	fmt.Fprint(w, "<!DOCTYPE html><html><body>OK</body></html>")
}

func textResponse(w http.ResponseWriter, body string, status int) {
	w.Header().Set("Content-Type", "text/plain")
	w.WriteHeader(status)
	fmt.Fprint(w, body)
}

// parseAPIKey extracts the API key from headers or JSON body
func parseAPIKey(r *http.Request) string {
	if k := r.Header.Get("X-Api-Key"); k != "" {
		return k
	}
	if r.Method == "POST" && r.Body != nil {
		body, _ := io.ReadAll(r.Body)
		r.Body = io.NopCloser(strings.NewReader(string(body)))
		var data map[string]interface{}
		if json.Unmarshal(body, &data) == nil {
			if k, ok := data["api_key"]; ok {
				return fmt.Sprintf("%v", k)
			}
		}
	}
	return ""
}

func lookupProjectByAPIKey(apiKey string, acceptRW, acceptRO bool) *Project {
	if len(apiKey) != 32 {
		return nil
	}
	if apiKey[:4] == "hcw_" && acceptRW {
		secret8 := apiKey[4:12]
		rows, _ := db.Query("SELECT id,code,name,owner_id,api_key,api_key_readonly,badge_key,ping_key,show_slugs FROM projects WHERE api_key LIKE ?", secret8+"%")
		defer rows.Close()
		for rows.Next() {
			var p Project
			rows.Scan(&p.ID, &p.Code, &p.Name, &p.OwnerID, &p.APIKey, &p.APIKeyReadonly, &p.BadgeKey, &p.PingKey, &p.ShowSlugs)
			if p.compareAPIKey(apiKey) {
				return &p
			}
		}
	}
	if apiKey[:4] == "hcr_" && acceptRO {
		secret8 := apiKey[4:12]
		rows, _ := db.Query("SELECT id,code,name,owner_id,api_key,api_key_readonly,badge_key,ping_key,show_slugs FROM projects WHERE api_key_readonly LIKE ?", secret8+"%")
		defer rows.Close()
		for rows.Next() {
			var p Project
			rows.Scan(&p.ID, &p.Code, &p.Name, &p.OwnerID, &p.APIKey, &p.APIKeyReadonly, &p.BadgeKey, &p.PingKey, &p.ShowSlugs)
			if p.compareAPIKey(apiKey) {
				return &p
			}
		}
	}
	// Plain text keys
	if acceptRW && acceptRO {
		var p Project
		err := db.QueryRow("SELECT id,code,name,owner_id,api_key,api_key_readonly,badge_key,ping_key,show_slugs FROM projects WHERE api_key=? OR api_key_readonly=?", apiKey, apiKey).Scan(&p.ID, &p.Code, &p.Name, &p.OwnerID, &p.APIKey, &p.APIKeyReadonly, &p.BadgeKey, &p.PingKey, &p.ShowSlugs)
		if err == nil {
			return &p
		}
	} else if acceptRW {
		var p Project
		err := db.QueryRow("SELECT id,code,name,owner_id,api_key,api_key_readonly,badge_key,ping_key,show_slugs FROM projects WHERE api_key=?", apiKey).Scan(&p.ID, &p.Code, &p.Name, &p.OwnerID, &p.APIKey, &p.APIKeyReadonly, &p.BadgeKey, &p.PingKey, &p.ShowSlugs)
		if err == nil {
			return &p
		}
	} else if acceptRO {
		var p Project
		err := db.QueryRow("SELECT id,code,name,owner_id,api_key,api_key_readonly,badge_key,ping_key,show_slugs FROM projects WHERE api_key_readonly=?", apiKey).Scan(&p.ID, &p.Code, &p.Name, &p.OwnerID, &p.APIKey, &p.APIKeyReadonly, &p.BadgeKey, &p.PingKey, &p.ShowSlugs)
		if err == nil {
			return &p
		}
	}
	return nil
}

func authorizeAPIKey(r *http.Request, acceptRW, acceptRO bool) *Project {
	apiKey := parseAPIKey(r)
	if len(apiKey) != 32 {
		return nil
	}
	return lookupProjectByAPIKey(apiKey, acceptRW, acceptRO)
}

func getAPIVersion(r *http.Request) int {
	if strings.HasPrefix(r.URL.Path, "/api/v3/") {
		return 3
	}
	if strings.HasPrefix(r.URL.Path, "/api/v2/") {
		return 2
	}
	return 1
}

func generateUUID() string {
	b := make([]byte, 16)
	rand.Read(b)
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x0c) | 0x80
	return fmt.Sprintf("%08x-%04x-%04x-%04x-%012x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:])
}

func hmacSHA256(key, data string) string {
	mac := hmac.New(sha256.New, []byte(key))
	mac.Write([]byte(data))
	return hex.EncodeToString(mac.Sum(nil))
}

func base64HMAC(key, data string) string {
	mac := hmac.New(sha256.New, []byte(key))
	mac.Write([]byte(data))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

func checkBadgeSignature(badgeKey, tag, sig string) bool {
	ours := base64HMAC(badgeKey, tag)
	if len(ours) >= 8 && len(sig) >= 8 {
		return ours[:8] == sig[:8]
	}
	return false
}

func slugify(s string) string {
	s = strings.ToLower(s)
	s = strings.ReplaceAll(s, " ", "-")
	s = strings.ReplaceAll(s, "_", "-")
	// Remove non-alphanumeric chars except hyphens
	var result []byte
	for _, c := range []byte(s) {
		if (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' {
			result = append(result, c)
		}
	}
	return string(result)
}

func getSessionUser(r *http.Request) *User {
	cookie, err := r.Cookie("session")
	if err != nil {
		return nil
	}
	var u User
	err = db.QueryRow("SELECT id,username,email FROM users WHERE id=(SELECT user_id FROM sessions WHERE token=?)", cookie.Value).Scan(&u.ID, &u.Username, &u.Email)
	if err != nil {
		return nil
	}
	return &u
}

func getSessionProject(r *http.Request) *Project {
	user := getSessionUser(r)
	if user == nil {
		return nil
	}
	// Get the user's first project
	var p Project
	err := db.QueryRow("SELECT id,code,name,owner_id,api_key,api_key_readonly,badge_key,ping_key,show_slugs FROM projects WHERE owner_id=? LIMIT 1", user.ID).Scan(&p.ID, &p.Code, &p.Name, &p.OwnerID, &p.APIKey, &p.APIKeyReadonly, &p.BadgeKey, &p.PingKey, &p.ShowSlugs)
	if err != nil {
		return nil
	}
	return &p
}

func getCSRFToken(r *http.Request) string {
	cookie, err := r.Cookie("csrftoken")
	if err != nil {
		return ""
	}
	return cookie.Value
}

func ensureCSRFCookie(w http.ResponseWriter, r *http.Request) string {
	token := getCSRFToken(r)
	if token == "" {
		token = generateUUID()
		http.SetCookie(w, &http.Cookie{
			Name:     "csrftoken",
			Value:    token,
			Path:     "/",
			HttpOnly: false,
			MaxAge:   365 * 24 * 3600,
			SameSite: http.SameSiteLaxMode,
		})
	}
	return token
}

func checkCSRF(r *http.Request) bool {
	token := getCSRFToken(r)
	if token == "" {
		return false
	}
	formToken := r.FormValue("csrfmiddlewaretoken")
	if formToken == token {
		return true
	}
	// Also check header
	headerToken := r.Header.Get("X-CSRFToken")
	return headerToken == token
}

func setSessionCookie(w http.ResponseWriter, userID int64) string {
	token := generateUUID()
	db.Exec("INSERT INTO sessions (user_id, token) VALUES (?, ?)", userID, token)
	http.SetCookie(w, &http.Cookie{
		Name:     "session",
		Value:    token,
		Path:     "/",
		HttpOnly: true,
		MaxAge:   3600 * 24 * 30,
		SameSite: http.SameSiteLaxMode,
	})
	return token
}

func init() {
	rand.Reader.Read(make([]byte, 1)) // warm up
}

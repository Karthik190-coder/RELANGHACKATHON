package main

import (
	"fmt"
	"net/http"
	"strings"
	"time"
)

func handleLogin(w http.ResponseWriter, r *http.Request) {
	ensureCSRFCookie(w, r)
	if user := getSessionUser(r); user != nil {
		project := getSessionProject(r)
		if project != nil {
			http.Redirect(w, r, fmt.Sprintf("/projects/%s/checks/", project.Code), 302)
			return
		}
		http.Redirect(w, r, "/", 302)
		return
	}
	htmlResponse(w, 200)
}

func handleLoginPost(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()
	email := strings.ToLower(r.FormValue("email"))
	password := r.FormValue("password")
	action := r.FormValue("action")

	if action == "login" {
		// Password login
		if email == "" || password == "" {
			ensureCSRFCookie(w, r)
			htmlResponse(w, 200)
			return
		}

		user := getUserByEmail(email)
		if user == nil {
			ensureCSRFCookie(w, r)
			htmlResponse(w, 200)
			return
		}

		// Verify password - check against hash stored in password_hash
		var storedHash string
		err := db.QueryRow("SELECT password_hash FROM users WHERE id=?", user.ID).Scan(&storedHash)
		if err != nil || !verifyPassword(storedHash, password) {
			ensureCSRFCookie(w, r)
			htmlResponse(w, 200)
			return
		}

		setSessionCookie(w, user.ID)

		// Redirect
		redirectURL := r.FormValue("next")
		if redirectURL != "" && isAllowedRedirect(redirectURL) {
			http.Redirect(w, r, redirectURL, 302)
			return
		}

		// Redirect to project checks page
		project := getSessionProject(r)
		if project != nil {
			http.Redirect(w, r, fmt.Sprintf("/projects/%s/checks/", project.Code), 302)
		} else {
			http.Redirect(w, r, "/", 302)
		}
		return
	}

	// Magic link login (email)
	if email != "" {
		// Just redirect to link sent page
		response := redirectResponse(w, "/accounts/login_link_sent/")
		http.SetCookie(response, &http.Cookie{
			Name:     "auto-login",
			Value:    "1",
			MaxAge:   300,
			HttpOnly: true,
			Path:     "/",
			SameSite: http.SameSiteLaxMode,
		})
	}

	http.Redirect(w, r, "/accounts/login_link_sent/", 302)
}

func redirectResponse(w http.ResponseWriter, path string) *http.ResponseWriter {
	// This is a helper - actual redirect is done by the caller
	return &w
}

func handleLogout(w http.ResponseWriter, r *http.Request) {
	cookie, err := r.Cookie("session")
	if err == nil {
		db.Exec("DELETE FROM sessions WHERE token=?", cookie.Value)
	}
	http.SetCookie(w, &http.Cookie{
		Name:     "session",
		Value:    "",
		Path:     "/",
		MaxAge:   -1,
		HttpOnly: true,
	})
	http.Redirect(w, r, "/", 302)
}

func handleSignupCSRF(w http.ResponseWriter, r *http.Request) {
	// Check registration open (default: true)
	// Check not authenticated
	if user := getSessionUser(r); user != nil {
		w.WriteHeader(403)
		return
	}
	token := ensureCSRFCookie(w, r)
	w.Header().Set("Content-Type", "text/plain")
	fmt.Fprint(w, token)
}

func handleSignup(w http.ResponseWriter, r *http.Request) {
	if r.Method == "GET" {
		ensureCSRFCookie(w, r)
		htmlResponse(w, 200)
		return
	}

	// POST
	if user := getSessionUser(r); user != nil {
		w.WriteHeader(403)
		return
	}

	if !checkCSRF(r) {
		w.WriteHeader(403)
		return
	}

	r.ParseForm()
	identity := strings.ToLower(r.FormValue("identity"))

	if identity == "" {
		ensureCSRFCookie(w, r)
		htmlResponse(w, 200)
		return
	}

	// Check if user exists
	user := getUserByEmail(identity)
	if user == nil {
		// Create new user
		username := generateUUID()[:30]
		db.Exec("INSERT INTO users (username, email, password_hash) VALUES (?, ?, '')", username, identity)

		user = getUserByEmail(identity)
		if user != nil {
			// Create project for new user
			projectCode := generateUUID()
			badgeKey := username
			db.Exec("INSERT INTO projects (code, name, owner_id, badge_key) VALUES (?, '', ?, ?)", projectCode, user.ID, badgeKey)

			// Create check
			var projectID int64
			db.QueryRow("SELECT id FROM projects WHERE code=?", projectCode).Scan(&projectID)
			checkName := "My First Check"
			checkSlug := "my-first-check"
			createCheck(projectID, checkName, checkSlug, "", "", "simple", 86400, 3600, "* * * * *", "UTC", "", false, false, false, false, false, "", "", "")

			// Create email channel
			var channelCode string
			channelCode = generateUUID()
			nowStr := nowISO()
			var channelID int64
			result, _ := db.Exec("INSERT INTO channels (code, project_id, created, kind, value, email_verified) VALUES (?,?,?,?,?,1)", channelCode, projectCode, nowStr, "email", identity)
			if result != nil {
				channelID, _ = result.LastInsertId()
			}
			// Link channel to check
			if channelID > 0 {
				var checkID int64
				db.QueryRow("SELECT id FROM checks WHERE project_id=?", projectID).Scan(&checkID)
				if checkID > 0 {
					db.Exec("INSERT OR IGNORE INTO check_channels (check_id, channel_id) VALUES (?,?)", checkID, channelID)
				}
			}

			// Ensure profile
			getProfile(user.ID)
		}
	}

	// Send login link
	if user != nil {
		profile := getProfile(user.ID)
		token := profile.prepareToken()
		_ = token
	}

	ensureCSRFCookie(w, r)
	htmlResponse(w, 200)
}

func handleLoginLinkSent(w http.ResponseWriter, r *http.Request) {
	htmlResponse(w, 200)
}

func handleCheckToken(w http.ResponseWriter, r *http.Request) {
	username := r.PathValue("username")

	if r.Method != "POST" {
		// Check for auto-login cookie
		_, err := r.Cookie("auto-login")
		if err != nil {
			htmlResponse(w, 200)
			return
		}
	}

	user := getUserByUsername(username)
	if user == nil {
		http.Redirect(w, r, "/accounts/login/?account-closed", 302)
		return
	}

	setSessionCookie(w, user.ID)

	project := getProjectByID(0)
	// Get user's project
	db.QueryRow("SELECT id FROM projects WHERE owner_id=? LIMIT 1", user.ID).Scan(&project)

	http.Redirect(w, r, "/", 302)
}

func handleProfile(w http.ResponseWriter, r *http.Request) {
	user := getSessionUser(r)
	if user == nil {
		http.Redirect(w, r, "/accounts/login/", 302)
		return
	}

	if r.Method == "POST" {
		r.ParseForm()
		if "leave_project" in r.Form {
			// Leave project
		}
		if "tz" in r.Form {
			tz := r.FormValue("tz")
			db.Exec("UPDATE profiles SET tz=? WHERE user_id=?", tz, user.ID)
		}
	}

	ensureCSRFCookie(w, r)
	htmlResponse(w, 200)
}

func handleAppearance(w http.ResponseWriter, r *http.Request) {
	user := getSessionUser(r)
	if user == nil {
		http.Redirect(w, r, "/accounts/login/", 302)
		return
	}

	if r.Method == "POST" {
		theme := r.FormValue("theme")
		db.Exec("UPDATE profiles SET theme=? WHERE user_id=?", theme, user.ID)
	}

	ensureCSRFCookie(w, r)
	htmlResponse(w, 200)
}

func handleNotifications(w http.ResponseWriter, r *http.Request) {
	user := getSessionUser(r)
	if user == nil {
		http.Redirect(w, r, "/accounts/login/", 302)
		return
	}

	if r.Method == "POST" {
		reports := r.FormValue("reports")
		nagPeriod := r.FormValue("nag_period")
		if reports != "" {
			db.Exec("UPDATE profiles SET reports=? WHERE user_id=?", reports, user.ID)
		}
		if nagPeriod != "" {
			var np int
			fmt.Sscanf(nagPeriod, "%d", &np)
			db.Exec("UPDATE profiles SET nag_period=? WHERE user_id=?", np, user.ID)
		}
	}

	ensureCSRFCookie(w, r)
	htmlResponse(w, 200)
}

func handleClose(w http.ResponseWriter, r *http.Request) {
	user := getSessionUser(r)
	if user == nil {
		http.Redirect(w, r, "/accounts/login/", 302)
		return
	}

	if r.Method == "POST" {
		confirmation := r.FormValue("confirmation")
		if confirmation == user.Email {
			// Delete user's checks
			db.Exec("DELETE FROM checks WHERE project_id IN (SELECT id FROM projects WHERE owner_id=?)", user.ID)
			db.Exec("DELETE FROM channels WHERE project_id IN (SELECT id FROM projects WHERE owner_id=?)", user.ID)
			db.Exec("DELETE FROM projects WHERE owner_id=?", user.ID)
			db.Exec("DELETE FROM members WHERE user_id=?", user.ID)
			db.Exec("DELETE FROM sessions WHERE user_id=?", user.ID)
			db.Exec("DELETE FROM users WHERE id=?", user.ID)
			http.Redirect(w, r, "/accounts/login/?account-closed", 302)
			return
		}
	}

	ensureCSRFCookie(w, r)
	htmlResponse(w, 200)
}

func handleSetPassword(w http.ResponseWriter, r *http.Request) {
	user := getSessionUser(r)
	if user == nil {
		http.Redirect(w, r, "/accounts/login/", 302)
		return
	}
	htmlResponse(w, 200)
}

func handleChangeEmail(w http.ResponseWriter, r *http.Request) {
	user := getSessionUser(r)
	if user == nil {
		http.Redirect(w, r, "/accounts/login/", 302)
		return
	}
	htmlResponse(w, 200)
}

func handleUnsubscribeReports(w http.ResponseWriter, r *http.Request) {
	if r.Method == "POST" {
		htmlResponse(w, 200)
		return
	}
	htmlResponse(w, 200)
}

func handleWebAuthn(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(404)
}

func handleTOTP(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(404)
}

func handleLogin2FA(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(404)
}

func handleLoginTOTP(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(404)
}

func isAllowedRedirect(url string) bool {
	if url == "" {
		return false
	}
	if strings.Contains(url, "://") {
		return false
	}
	allowedRoutes := []string{
		"/checks/", "/projects/", "/accounts/", "/integrations/",
	}
	for _, route := range allowedRoutes {
		if strings.HasPrefix(url, route) {
			return true
		}
	}
	return false
}

func (p *Profile) prepareToken() string {
	token := generateUUID()
	p.Token = token
	db.Exec("UPDATE profiles SET token=? WHERE user_id=?", token, p.UserID)
	return token
}

func init() {
	_ = time.Now() // ensure time import used
}

package main

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"
)

var badgeWidths = map[byte]int{
	'a': 7, 'b': 7, 'c': 6, 'd': 7, 'e': 6, 'f': 4, 'g': 7, 'h': 7,
	'i': 3, 'j': 3, 'k': 7, 'l': 3, 'm': 10, 'n': 7, 'o': 7, 'p': 7,
	'q': 7, 'r': 4, 's': 6, 't': 5, 'u': 7, 'v': 7, 'w': 9, 'x': 6,
	'y': 7, 'z': 7, '0': 7, '1': 6, '2': 7, '3': 7, '4': 7, '5': 7,
	'6': 7, '7': 7, '8': 7, '9': 7, 'A': 8, 'B': 7, 'C': 8, 'D': 8,
	'E': 7, 'F': 6, 'G': 9, 'H': 8, 'I': 3, 'J': 4, 'K': 7, 'L': 6,
	'M': 10, 'N': 8, 'O': 9, 'P': 6, 'Q': 9, 'R': 7, 'S': 7, 'T': 7,
	'U': 8, 'V': 8, 'W': 11, 'X': 7, 'Y': 7, 'Z': 7, '-': 4, '_': 6,
}

var badgeColors = map[string]string{
	"up":   "#4c1",
	"late": "#fe7d37",
	"down": "#e05d44",
}

func getBadgeWidth(s string) int {
	total := 0
	for i := 0; i < len(s); i++ {
		w, ok := badgeWidths[s[i]]
		if !ok {
			w = 7
		}
		total += w
	}
	return total
}

func getBadgeSVG(tag, status string) string {
	w1 := getBadgeWidth(tag) + 10
	w2 := getBadgeWidth(status) + 10
	color := badgeColors[status]
	if color == "" {
		color = "#999"
	}

	return fmt.Sprintf(`<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="20"><linearGradient id="a" x2="0" y2="100%%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient><rect rx="3" width="%d" height="20" fill="#555"/><rect rx="3" x="%d" width="%d" height="20" fill="%s"/><rect rx="3" width="%d" height="20" fill="url(#a)"/><g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11"><text x="%g" y="15" fill="#010101" fill-opacity=".3">%s</text><text x="%g" y="14">%s</text><text x="%d" y="15" fill="#010101" fill-opacity=".3">%s</text><text x="%d" y="14">%s</text></g></svg>`,
		w1+w2, w1+w2, w1, w2, color, w1+w2,
		float64(w1)/2, tag, float64(w1)/2, tag,
		w1+float64(w2)/2, status, w1+float64(w2)/2, status)
}

func handleBadge(w http.ResponseWriter, r *http.Request) {
	badgeKey := r.PathValue("key")
	signature := r.PathValue("signature")
	tag := r.PathValue("tag")
	fmt_ := r.PathValue("fmt")

	if fmt_ != "svg" && fmt_ != "json" && fmt_ != "shields" {
		w.WriteHeader(404)
		return
	}

	withLate := true
	if len(signature) == 10 && signature[len(signature)-2:] == "-2" {
		withLate = false
	}

	if !checkBadgeSignature(badgeKey, tag, signature) {
		w.WriteHeader(404)
		return
	}

	project := getProjectByBadgeKey(badgeKey)
	if project == nil {
		w.WriteHeader(404)
		return
	}

	// Find checks for this tag
	query := "SELECT id,name,slug,tags,code,kind,desc,project_id,created,timeout,grace,schedule,tz,filter_subject,filter_body,filter_http_body,filter_default_fail,start_kw,success_kw,failure_kw,methods,manual_resume,badge_key,n_pings,last_ping,last_start,last_start_rid,last_duration,has_confirmation_link,alert_after,status FROM checks WHERE project_id=?"
	if tag != "*" {
		query += " AND tags LIKE ?"
	}

	var rows_data string
	_ = rows_data

	status := "up"
	total := 0
	grace := 0
	down := 0

	if tag == "*" {
		rows, err := db.Query(query, project.ID)
		if err == nil {
			defer rows.Close()
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

				total++
				checkStatus := c.Status
				if checkStatus == "down" {
					down++
					status = "down"
					if fmt_ == "svg" {
						break
					}
				} else if checkStatus == "grace" {
					grace++
					if status == "up" && withLate {
						status = "late"
					}
				}
			}
		}
	} else {
		rows, err := db.Query(query+" AND tags LIKE ?", project.ID, "%"+tag+"%")
		if err == nil {
			defer rows.Close()
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

				// Precise tag matching
				tagsList := strings.Fields(c.Tags)
				found := false
				for _, t := range tagsList {
					if t == tag {
						found = true
						break
					}
				}
				if !found {
					continue
				}

				total++
				checkStatus := c.Status
				if checkStatus == "down" {
					down++
					status = "down"
					if fmt_ == "svg" {
						break
					}
				} else if checkStatus == "grace" {
					grace++
					if status == "up" && withLate {
						status = "late"
					}
				}
			}
		}
	}

	if fmt_ == "shields" {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"schemaVersion": 1,
			"label":        tag,
			"message":      status,
			"color":        badgeColors[status],
		})
		return
	}

	if fmt_ == "json" {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": status,
			"total":  total,
			"grace":  grace,
			"down":   down,
		})
		return
	}

	// SVG
	svg := getBadgeSVG(tag, status)
	w.Header().Set("Content-Type", "image/svg+xml")
	fmt.Fprint(w, svg)
}

func handleBadgeAll(w http.ResponseWriter, r *http.Request) {
	badgeKey := r.PathValue("key")
	signature := r.PathValue("signature")
	fmt_ := r.PathValue("fmt")

	handleBadge(w, r)
	_ = badgeKey
	_ = signature
	_ = fmt_
}

func handleCheckBadge(w http.ResponseWriter, r *http.Request) {
	statesStr := r.PathValue("states")
	badgeKey := r.PathValue("key")
	fmt_ := r.PathValue("fmt")

	states, _ := strconv.Atoi(statesStr)

	if fmt_ != "svg" && fmt_ != "json" && fmt_ != "shields" {
		w.WriteHeader(404)
		return
	}

	check := getCheckByBadgeKey(badgeKey)
	if check == nil {
		w.WriteHeader(404)
		return
	}

	checkStatus := check.Status
	status := "up"
	if checkStatus == "down" {
		status = "down"
	} else if checkStatus == "grace" && states == 3 {
		status = "late"
	}

	if fmt_ == "shields" {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"schemaVersion": 1,
			"label":        check.NameThenCode(),
			"message":      status,
			"color":        badgeColors[status],
		})
		return
	}

	if fmt_ == "json" {
		graceVal := 0
		downVal := 0
		if checkStatus == "grace" {
			graceVal = 1
		}
		if checkStatus == "down" {
			downVal = 1
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": status,
			"total":  1,
			"grace":  graceVal,
			"down":   downVal,
		})
		return
	}

	svg := getBadgeSVG(check.NameThenCode(), status)
	w.Header().Set("Content-Type", "image/svg+xml")
	fmt.Fprint(w, svg)
}

func (c *Check) NameThenCode() string {
	if c.Name != "" {
		return c.Name
	}
	return c.Code
}

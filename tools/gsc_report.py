#!/usr/bin/env python3
"""Daily Search Console report for all of Aslan's Google accounts.

Runs on the VPS (stdlib only). Not served by the website.

  python3 tools/gsc_report.py setup   # one time: secret, sign in accounts, cron
  python3 tools/gsc_report.py add     # sign in one more Google account
  python3 tools/gsc_report.py run     # build the report JSON (cron does this hourly)

Config with secrets lives in /opt/gsc-report/config.json (chmod 600), never in git.
The report is written to /var/www/aslanmammadli.com/gsc/r-<random>.json.
"""
import datetime, getpass, json, os, secrets, subprocess, sys, urllib.parse, urllib.request

CLIENT_ID = "270075953810-iig309062qcrh0anb39lj6chhffe47pn.apps.googleusercontent.com"
REDIRECT = "http://localhost:8765"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly openid email"
CONF_DIR = "/opt/gsc-report"
CONF = CONF_DIR + "/config.json"
WEB_DIR = "/var/www/aslanmammadli.com/gsc"
API = "https://www.googleapis.com/webmasters/v3"


def load():
    try:
        with open(CONF) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"accounts": []}


def save(c):
    os.makedirs(CONF_DIR, exist_ok=True)
    with open(CONF, "w") as f:
        json.dump(c, f, indent=1)
    os.chmod(CONF, 0o600)


def post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def api(token, path, body=None):
    req = urllib.request.Request(API + path, method="POST" if body else "GET",
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def add_account(c):
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID, "redirect_uri": REDIRECT, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent select_account"})
    print("\n1) Open this link in your browser and sign in with the Google account:\n")
    print(url)
    print("\n2) You will land on a page that does not load (localhost). That is expected.")
    pasted = input("3) Copy that page's full address from the address bar and paste it here: ").strip()
    code = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query).get("code", [pasted])[0]
    tok = post("https://oauth2.googleapis.com/token", {
        "code": code, "client_id": CLIENT_ID, "client_secret": c["client_secret"],
        "redirect_uri": REDIRECT, "grant_type": "authorization_code"})
    if "refresh_token" not in tok:
        sys.exit("No refresh token returned. Try again.")
    email = "unknown"
    try:
        req = urllib.request.Request("https://www.googleapis.com/oauth2/v3/userinfo",
                                     headers={"Authorization": "Bearer " + tok["access_token"]})
        email = json.load(urllib.request.urlopen(req, timeout=30)).get("email", email)
    except Exception:
        pass
    c["accounts"] = [a for a in c["accounts"] if a["email"] != email] + [{"email": email, "refresh_token": tok["refresh_token"]}]
    save(c)
    print(f"Added {email}.")


def access_token(c, acct):
    return post("https://oauth2.googleapis.com/token", {
        "client_id": CLIENT_ID, "client_secret": c["client_secret"],
        "refresh_token": acct["refresh_token"], "grant_type": "refresh_token"})["access_token"]


def run(c):
    # Last two complete days. Search Console data settles after about 2 days.
    day = datetime.date.today() - datetime.timedelta(days=2)
    prev = day - datetime.timedelta(days=1)
    sites, errors = {}, []
    for a in c["accounts"]:
        try:
            tok = access_token(c, a)
            for s in api(tok, "/sites").get("siteEntry", []):
                if s["permissionLevel"] != "siteUnverifiedUser" and s["siteUrl"] not in sites:
                    sites[s["siteUrl"]] = tok
        except Exception as e:
            errors.append(f"{a['email']}: {e}")

    def metrics(site, tok, d):
        rows = api(tok, f"/sites/{urllib.parse.quote(site, safe='')}/searchAnalytics/query",
                   {"startDate": str(d), "endDate": str(d), "type": "web"}).get("rows", [])
        r = rows[0] if rows else {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}
        return {k: round(r[k], 4) for k in ("clicks", "impressions", "ctr", "position")}

    out = []
    for site, tok in sites.items():
        name = site[10:] if site.startswith("sc-domain:") else site.split("//")[-1].rstrip("/")
        try:
            out.append({"site": name, "day": metrics(site, tok, day), "prev": metrics(site, tok, prev)})
        except Exception as e:
            errors.append(f"{name}: {e}")
    out.sort(key=lambda s: -s["day"]["impressions"])
    report = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"),
              "date": str(day), "compared_with": str(prev), "sites": out, "errors": errors}
    os.makedirs(WEB_DIR, exist_ok=True)
    path = f"{WEB_DIR}/r-{c['report_key']}.json"
    with open(path + ".tmp", "w") as f:
        json.dump(report, f, indent=1)
    os.replace(path + ".tmp", path)
    return path


def setup():
    c = load()
    if not c.get("client_secret"):
        c["client_secret"] = getpass.getpass("Paste the Google client secret (hidden): ").strip()
    c.setdefault("report_key", secrets.token_urlsafe(18))
    save(c)
    while True:
        add_account(c)
        if input("Add another Google account? (y/n): ").strip().lower() != "y":
            break
    line = f"45 * * * * python3 /opt/aslanmammadli-repo/tools/gsc_report.py run >/dev/null 2>&1 # gsc-report"
    cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    new = "\n".join(l for l in cur.splitlines() if "gsc-report" not in l) + "\n" + line + "\n"
    subprocess.run(["crontab", "-"], input=new.lstrip("\n"), text=True, check=True)
    run(c)
    print("\nDone. Report URL (send this to Claude):")
    print(f"https://aslanmammadli.com/gsc/r-{c['report_key']}.json")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "setup":
        setup()
    elif cmd == "add":
        add_account(load())
    else:
        print(run(load()))

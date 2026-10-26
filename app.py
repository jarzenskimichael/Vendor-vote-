
import os, sqlite3, secrets, hashlib, io, re
from functools import wraps
from flask import Flask, request, redirect, url_for, session, render_template_string, flash, make_response, abort
import qrcode
app=Flask(__name__)
app.secret_key=os.environ.get("APP_SECRET","change-this-secret-before-deploying")
ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD","")
DB_PATH=os.environ.get("DATABASE_PATH","votes.db")
BASE_URL=os.environ.get("BASE_URL","").rstrip("/")
app.config["SESSION_COOKIE_HTTPONLY"]=True
app.config["SESSION_COOKIE_SAMESITE"]="Lax"
app.config["SESSION_COOKIE_SECURE"]=os.environ.get("COOKIE_SECURE","0")=="1"

def db():
 c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c
def setting(k,d=""):
 with db() as c:
  r=c.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone()
 return r["value"] if r else d
def put(k,v):
 with db() as c: c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))
def voter_hash(t): return hashlib.sha256((app.secret_key+":"+t).encode()).hexdigest()
def base(): return BASE_URL or request.url_root.rstrip("/")
def admin(fn):
 from functools import wraps
 @wraps(fn)
 def w(*a,**kw):
  if not session.get("admin"): return redirect(url_for("login",next=request.path))
  return fn(*a,**kw)
 return w
def init():
 with db() as c:
  c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
  c.execute("CREATE TABLE IF NOT EXISTS vendors(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,slug TEXT NOT NULL UNIQUE,active INTEGER NOT NULL DEFAULT 1)")
  c.execute("CREATE TABLE IF NOT EXISTS votes(id INTEGER PRIMARY KEY AUTOINCREMENT,vendor_id INTEGER NOT NULL,voter_hash TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL DEFAULT(datetime('now')))")
  c.execute("INSERT OR IGNORE INTO settings VALUES('voting_open','1')")
  c.execute("INSERT OR IGNORE INTO settings VALUES('results_public','0')")
  c.execute("INSERT OR IGNORE INTO settings VALUES('event_title','Halloween Night Market')")
  if c.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]==0:
   for i in range(1,16): c.execute("INSERT INTO vendors(name,slug) VALUES(?,?)",(f"Vendor {i:02d}",f"vendor-{i:02d}"))
init()
SHELL="""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>{{title}}</title><style>
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at top,#342033,#101014 60%);color:#fff;font:16px system-ui,-apple-system,sans-serif;min-height:100vh}main{max-width:760px;margin:auto;padding:22px 16px 48px}.brand{font-size:12px;letter-spacing:.2em;color:#ff8b45;font-weight:800;text-transform:uppercase}.panel{background:#1b1a22;border:1px solid #453542;border-radius:20px;padding:22px;margin-top:18px}h1{font-size:clamp(32px,8vw,48px);line-height:1.04;margin:12px 0}h2{margin-top:0}p{line-height:1.55;color:#c8c4ce}.vendor{font-size:30px;font-weight:850;color:#fff0d6;margin:14px 0}button,.button{display:inline-block;width:100%;border:0;border-radius:12px;background:#ff8b45;color:#20120c;font-size:16px;font-weight:800;text-align:center;text-decoration:none;padding:14px;cursor:pointer}input{width:100%;padding:12px;border-radius:10px;border:1px solid #554758;background:#101014;color:#fff;margin:6px 0 12px}label{font-size:14px;font-weight:650}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.tile{padding:14px;background:#111116;border:1px solid #433542;border-radius:12px;color:#fff;text-decoration:none}.small{font-size:12px;color:#aaa;overflow-wrap:anywhere}.flash{padding:10px;border-radius:8px;background:#342033;margin:8px 0}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:9px 6px;border-bottom:1px solid #423440}th{font-size:12px;color:#ffbc91;text-transform:uppercase}.row{display:flex;gap:8px;align-items:center}.row input{margin:0}.row button{width:auto;padding:10px}.bar{height:6px;background:#38313b;border-radius:8px;margin-top:6px}.bar span{display:block;height:100%;background:#ff8b45}.small a{color:#ffbc91}
</style></head><body><main><div class=brand>✦ {{event_title}} · Community Choice</div>{% with ms=get_flashed_messages() %}{% for m in ms %}<div class=flash>{{m}}</div>{% endfor %}{% endwith %}{{body|safe}}<p class=small style="text-align:center;margin-top:28px">One vote per customer · Please vote fairly</p></main></body></html>"""
def page(title,body): return render_template_string(SHELL,title=title,body=body,event_title=setting("event_title","Halloween Night Market"))
@app.route("/")
def home():
 return page("Halloween Night Market Voting",'<section class=panel><div class=brand>THE PEOPLE’S PICK</div><h1>Cast your vote.<br>Make it count.</h1><p>Scan the QR code at your favorite vendor booth to vote for the Halloween Night Market overall winner.</p><p>One vote total per customer. Results stay secret until the organizer closes the contest.</p><a class=button href=/vendors>Browse participating vendors</a></section>')
@app.route("/vendors")
def vendors():
 with db() as c: vs=c.execute("SELECT * FROM vendors WHERE active=1 ORDER BY name COLLATE NOCASE").fetchall()
 tiles="".join(f'<a class=tile href="{url_for("vote",vendor=v["slug"])}"><strong>{v["name"]}</strong><p>Vote for this booth →</p></a>' for v in vs)
 return page("Vendors",f'<section class=panel><h1>Choose your favorite</h1><p>Scan the booth QR code for the quickest experience.</p><div class=grid>{tiles}</div></section>')
@app.route("/vote")
def vote():
 slug=request.args.get("vendor","")
 with db() as c:
  v=c.execute("SELECT * FROM vendors WHERE slug=? AND active=1",(slug,)).fetchone()
  t=request.cookies.get("hm_voter")
  already=bool(t and c.execute("SELECT 1 FROM votes WHERE voter_hash=?",(voter_hash(t),)).fetchone())
 if not v: abort(404)
 if setting("voting_open","1")!="1": body='<section class=panel><h1>Voting is closed</h1><p>Thanks for joining us!</p></section>'
 elif already: body='<section class=panel><h1>Vote already received</h1><p>This browser has already submitted a vote. Thanks for participating!</p></section>'
 else: body=f"""<section class=panel><div class=brand>YOUR VOTE</div><h1>Vote for your favorite</h1><p>You're voting for:</p><div class=vendor>{v["name"]}</div><p>Each customer gets one vote. Your vote cannot be changed after submission.</p><form method=post action=/cast><input type=hidden name=vendor value="{v["slug"]}"><label style="display:flex;gap:10px;align-items:flex-start;margin:16px 0"><input style="width:auto" type=checkbox required> I confirm this is my one vote.</label><button>Submit my vote</button></form></section>"""
 return page("Vote",body)
@app.route("/cast",methods=["POST"])
def cast():
 if setting("voting_open","1")!="1": return page("Voting closed","<section class=panel><h1>Voting is closed</h1></section>")
 slug=request.form.get("vendor",""); token=request.cookies.get("hm_voter") or secrets.token_urlsafe(32)
 with db() as c:
  v=c.execute("SELECT * FROM vendors WHERE slug=? AND active=1",(slug,)).fetchone()
  if not v: abort(400)
  try: c.execute("INSERT INTO votes(vendor_id,voter_hash) VALUES(?,?)",(v["id"],voter_hash(token))); ok=True
  except sqlite3.IntegrityError: ok=False
 body=(f'<section class=panel><div class=brand>VOTE RECORDED</div><h1>Thank you!</h1><p>Your vote for <strong>{v["name"]}</strong> has been submitted. Results will be revealed after voting closes.</p></section>' if ok else '<section class=panel><h1>Vote already received</h1><p>Only one vote per browser is accepted.</p></section>')
 r=make_response(page("Vote submitted",body)); r.set_cookie("hm_voter",token,max_age=3888000,httponly=True,samesite="Lax",secure=app.config["SESSION_COOKIE_SECURE"]); return r
@app.route("/admin",methods=["GET","POST"])
def login():
 if session.get("admin"): return redirect(url_for("dashboard"))
 if request.method=="POST":
  if ADMIN_PASSWORD and secrets.compare_digest(request.form.get("password",""),ADMIN_PASSWORD):
   session["admin"]=True; return redirect(url_for("dashboard"))
  flash("Password incorrect, or ADMIN_PASSWORD is not configured.")
 return page("Organizer Login",'<section class=panel><h1>Organizer access</h1><p>Sign in to manage vendors, voting and results.</p><form method=post><label>Organizer password</label><input type=password name=password required><button>Sign in</button></form><p class=small>Set ADMIN_PASSWORD in hosting settings before launch.</p></section>')
@app.route("/admin/logout")
def logout(): session.clear(); return redirect("/admin")
@app.route("/admin/dashboard",methods=["GET","POST"])
@admin
def dashboard():
 if request.method=="POST":
  a=request.form.get("action")
  if a=="toggle": put("voting_open","0" if setting("voting_open","1")=="1" else "1")
  elif a=="results": put("results_public","0" if setting("results_public","0")=="1" else "1")
  elif a=="event": put("event_title",request.form.get("event_title","Halloween Night Market")[:100])
  elif a=="add":
   name=request.form.get("name","").strip()[:100]; slug=re.sub(r"[^a-z0-9-]+","-",request.form.get("slug","").lower()).strip("-")[:60]
   if name and slug:
    try:
     with db() as c: c.execute("INSERT INTO vendors(name,slug) VALUES(?,?)",(name,slug))
     flash("Vendor added.")
    except sqlite3.IntegrityError: flash("That URL ID already exists.")
  elif a=="rename":
   with db() as c: c.execute("UPDATE vendors SET name=? WHERE id=?",(request.form.get("name","").strip()[:100],request.form.get("id")))
  elif a=="active":
   with db() as c: c.execute("UPDATE vendors SET active=1-active WHERE id=?",(request.form.get("id"),))
  elif a=="reset" and request.form.get("confirm")=="RESET":
   with db() as c: c.execute("DELETE FROM votes")
   flash("All votes deleted.")
  return redirect(url_for("dashboard"))
 with db() as c:
  vs=c.execute("SELECT v.*,COUNT(votes.id) votes FROM vendors v LEFT JOIN votes ON votes.vendor_id=v.id GROUP BY v.id ORDER BY votes DESC,v.name COLLATE NOCASE").fetchall()
  total=c.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
 active=sum(v["active"] for v in vs); opened=setting("voting_open","1")=="1"; public=setting("results_public","0")=="1"; mx=max([v["votes"] for v in vs] or [0])
 rows=""
 for v in vs:
  dest=base()+url_for("vote",vendor=v["slug"]); width=int(v["votes"]/mx*100) if mx else 0
  rows+=f"""<tr><td><strong>{v["name"]}</strong><div class=small>ID: {v["slug"]} · {"Active" if v["active"] else "Inactive"}</div><div class=small><a href="{dest}">{dest}</a></div></td><td>{v["votes"]}<div class=bar><span style="width:{width}%"></span></div></td><td><a href="{url_for("qr",vendor=v["slug"])}">QR</a></td><td><form class=row method=post><input type=hidden name=action value=rename><input type=hidden name=id value="{v["id"]}"><input name=name value="{v["name"]}"><button>Save</button></form><form method=post style="margin-top:5px"><input type=hidden name=action value=active><input type=hidden name=id value="{v["id"]}"><button style="background:#514654;color:white">{"Deactivate" if v["active"] else "Activate"}</button></form></td></tr>"""
 body=f"""<section class=panel><div class=row style="justify-content:space-between"><div><div class=brand>ORGANIZER DASHBOARD</div><h1>Contest control</h1></div><a href=/admin/logout>Log out</a></div><div class=grid><div class=tile><div class=small>TOTAL VOTES</div><div style="font-size:28px;font-weight:850">{total}</div></div><div class=tile><div class=small>ACTIVE VENDORS</div><div style="font-size:28px;font-weight:850">{active}</div></div><div class=tile><div class=small>VOTING</div><div style="font-size:20px;font-weight:850">{"OPEN" if opened else "CLOSED"}</div></div></div>
 <form method=post style="margin-top:14px"><input type=hidden name=action value=event><label>Event title</label><input name=event_title value="{setting("event_title","Halloween Night Market")}"><button>Save event title</button></form>
 <div class=grid style="margin-top:10px"><form method=post><input type=hidden name=action value=toggle><button>{"Close voting now" if opened else "Reopen voting"}</button></form><form method=post><input type=hidden name=action value=results><button style="background:#514654;color:white">{"Hide public results" if public else "Reveal public results"}</button></form></div><p class=small>Results stay private by default. Close voting before revealing the winner.</p></section>
 <section class=panel><h2>Vendor roster & live tally</h2><p>Rename placeholders; each vendor's QR destination updates automatically.</p><div style="overflow:auto"><table><tr><th>Vendor / QR destination</th><th>Votes</th><th>QR</th><th>Manage</th></tr>{rows}</table></div>
 <h2 style="margin-top:24px">Add vendor</h2><form method=post><input type=hidden name=action value=add><label>Vendor name</label><input name=name placeholder="Spooky Sweets" required><label>Unique URL ID</label><input name=slug placeholder="spooky-sweets" required><button>Add vendor</button></form>
 <h2 style="margin-top:24px">Print booth QR codes</h2><a class=button href=/admin/qr-sheet target=_blank>Open printable QR sheet</a>
 <h2 style="margin-top:24px">Danger zone</h2><form method=post><input type=hidden name=action value=reset><label>Type RESET to delete all votes</label><input name=confirm placeholder=RESET><button style="background:#8b3131;color:white">Delete all votes</button></form></section>"""
 return page("Organizer Dashboard",body)
@app.route("/qr/<vendor>")
@admin
def qr(vendor):
 with db() as c: v=c.execute("SELECT * FROM vendors WHERE slug=?",(vendor,)).fetchone()
 if not v: abort(404)
 out=io.BytesIO(); qrcode.make(base()+url_for("vote",vendor=vendor)).save(out,format="PNG")
 r=make_response(out.getvalue()); r.headers["Content-Type"]="image/png"; return r
@app.route("/admin/qr-sheet")
@admin
def sheet():
 with db() as c: vs=c.execute("SELECT * FROM vendors WHERE active=1 ORDER BY name COLLATE NOCASE").fetchall()
 cards="".join(f'<article><img src="{url_for("qr",vendor=v["slug"])}"><h2>{v["name"]}</h2><p>Scan to cast your one vote</p><small>{base()+url_for("vote",vendor=v["slug"])}</small></article>' for v in vs)
 return f"""<!doctype html><html><head><meta name=viewport content="width=device-width"><title>Vendor QR Sheet</title><style>body{{font-family:Arial;margin:16px;color:#111}}.sheet{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}article{{border:1px solid #888;border-radius:8px;padding:8px;text-align:center;break-inside:avoid}}img{{width:150px;height:150px}}h2{{font-size:17px;margin:5px}}p{{margin:5px}}small{{font-size:9px;overflow-wrap:anywhere}}@media print{{button{{display:none}}article{{padding:5px}}img{{width:125px;height:125px}}}}</style></head><body><button onclick="window.print()">Print QR signs</button><h1>Halloween Night Market — Vendor QR Codes</h1><p>Print and place each code at the matching vendor booth. Only print after deployment URL is set.</p><div class=sheet>{cards}</div></body></html>"""
@app.route("/results")
def results():
 if setting("results_public","0")!="1": return page("Results",'<section class=panel><h1>Results are under wraps</h1><p>The organizer will reveal the winner when the contest ends.</p></section>')
 with db() as c: vs=c.execute("SELECT v.name,COUNT(votes.id) votes FROM vendors v LEFT JOIN votes ON votes.vendor_id=v.id WHERE v.active=1 GROUP BY v.id ORDER BY votes DESC,v.name COLLATE NOCASE").fetchall()
 total=sum(v["votes"] for v in vs); winner=vs[0] if vs else None
 rows="".join(f'<tr><td>{i+1}. {v["name"]}</td><td>{v["votes"]}</td></tr>' for i,v in enumerate(vs))
 return page("Results",f'<section class=panel><div class=brand>THE PEOPLE HAVE SPOKEN</div><h1>And the winner is…</h1><div class=vendor>{winner["name"] if winner and winner["votes"] else "No votes recorded"}</div><p>{winner["votes"] if winner else 0} votes · {total} total votes</p><table><tr><th>Place</th><th>Votes</th></tr>{rows}</table></section>')
@app.route("/health")
def health(): return {"status":"ok"}
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT","5000")))

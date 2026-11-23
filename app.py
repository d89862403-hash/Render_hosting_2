import os,sys,time,json,signal,threading,subprocess
from pathlib import Path
from datetime import datetime,timezone
from flask import Flask,request,redirect,url_for,render_template,session,flash,jsonify,Response,abort
DATA=Path(os.getenv("DATA_DIR","/var/data")); UP=DATA/"uploads"; LOG=DATA/"logs"
UP.mkdir(parents=True,exist_ok=True); LOG.mkdir(parents=True,exist_ok=True)
app=Flask(__name__); app.secret_key=os.getenv("FLASK_SECRET","change-me")
TOKEN=os.getenv("ADMIN_TOKEN",""); MAX=int(os.getenv("MAX_UPLOAD_MB","50")); app.config["MAX_CONTENT_LENGTH"]=MAX*1024*1024
lock=threading.RLock(); procs={}
ALLOWED={".py":"Python",".js":"Node.js",".mjs":"Node.js",".java":"Java",".php":"PHP",".sh":"Shell"}
def auth():
 if not session.get("ok"):
  if not TOKEN: abort(503,"Set ADMIN_TOKEN in Render environment variables.")
  abort(401)
@app.before_request
def protect():
 if request.endpoint not in ("login","health","static"):
  if not session.get("ok") and request.method == "GET" and request.endpoint == "home":
   return redirect(url_for("login"))
  auth()
@app.get("/health")
def health(): return jsonify(ok=True,service="ZORVEX HOSTING")
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  if TOKEN and request.form.get("token")==TOKEN: session["ok"]=True; return redirect(url_for("home"))
  flash("Incorrect token.")
 return render_template("login.html")
@app.post("/logout")
def logout(): session.clear(); return redirect(url_for("login"))
def clean(n):
 n=Path(n).name
 if not n or n in (".","..") or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in n): raise ValueError("Invalid filename")
 return n
def log(n,s):
 with (LOG/(n+".log")).open("a") as f: f.write(f"[{datetime.now(timezone.utc).isoformat()}] {s}\n")
def command(p):
 return {".py":[sys.executable,"-u",str(p)],".js":["node",str(p)],".mjs":["node",str(p)],".java":["java",str(p)],".php":["php",str(p)],".sh":["bash",str(p)]}[p.suffix.lower()]
def info():
 out=[]
 for p in sorted(UP.iterdir()):
  if not p.is_file(): continue
  q=procs.get(p.name)
  if q and q.poll() is not None: procs.pop(p.name,None); q=None
  out.append(dict(name=p.name,size=p.stat().st_size,language=ALLOWED.get(p.suffix.lower(),"Unsupported"),status="Running" if q else "Stopped"))
 return out
@app.get("/")
def home(): return render_template("index.html",files=info(),max_mb=MAX,email=os.getenv("OWNER_EMAIL",""))
@app.post("/upload")
def upload():
 f=request.files.get("file")
 if not f or not f.filename: flash("Choose a file."); return redirect(url_for("home"))
 try:
  n=clean(f.filename)
  if Path(n).suffix.lower() not in ALLOWED: raise ValueError("Supported: .py .js .mjs .java .php .sh")
  if (UP/n).exists(): raise ValueError("File already exists.")
  f.save(UP/n); log(n,"Uploaded"); flash("Upload complete.")
 except Exception as e: flash(str(e))
 return redirect(url_for("home"))
@app.post("/check")
def check():
 n=clean(request.form.get("name","")); p=UP/n
 if not p.is_file(): return jsonify(ok=False,error="File not found"),404
 return jsonify(ok=True,name=n,language=ALLOWED.get(p.suffix.lower()),size=p.stat().st_size,message="File exists.")
@app.post("/<action>/<name>")
def action(action,name):
 try: n=clean(name)
 except Exception as e: return jsonify(ok=False,error=str(e)),400
 p=UP/n
 if not p.is_file(): return jsonify(ok=False,error="File not found"),404
 with lock:
  q=procs.get(n)
  if q and q.poll() is not None: procs.pop(n,None); q=None
  if action in ("stop","restart") and q:
   os.killpg(q.pid,signal.SIGTERM)
   try:q.wait(timeout=4)
   except subprocess.TimeoutExpired: os.killpg(q.pid,signal.SIGKILL)
   procs.pop(n,None); log(n,"Stopped")
  if action in ("start","restart"):
   try:
    out=(LOG/(n+".log")).open("a")
    env={"PATH":os.getenv("PATH","/usr/local/bin:/usr/bin:/bin"),"HOME":str(DATA),"PYTHONUNBUFFERED":"1"}
    q=subprocess.Popen(command(p),cwd=UP,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,env=env,start_new_session=True)
    procs[n]=q; log(n,"Started")
   except Exception as e:return jsonify(ok=False,error=str(e)),400
  elif action=="delete":
   if q:
    os.killpg(q.pid,signal.SIGTERM); procs.pop(n,None)
   p.unlink(missing_ok=True); (LOG/(n+".log")).unlink(missing_ok=True); return jsonify(ok=True,message="Deleted")
  elif action not in ("stop","logs"): return jsonify(ok=False,error="Unknown action"),404
 return jsonify(ok=True,message=action.title()+" completed")
@app.get("/logs/<name>")
def logs(name):
 n=clean(name); p=LOG/(n+".log")
 def stream():
  p.touch(exist_ok=True)
  with p.open() as f:
   f.seek(0,2)
   while True:
    line=f.readline()
    if line: yield "data: "+json.dumps(line)+"\n\n"
    else: time.sleep(.5)
 return Response(stream(),mimetype="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
@app.post("/install")
def install():
 p=UP/"requirements.txt"
 if not p.is_file():return jsonify(ok=False,error="Upload requirements.txt first"),400
 out=(LOG/"install.log").open("a")
 q=subprocess.Popen([sys.executable,"-m","pip","install","--user","-r",str(p)],stdout=out,stderr=subprocess.STDOUT,env={**os.environ,"PYTHONUSERBASE":str(DATA/"python-user")})
 return jsonify(ok=True,message="Install started. See install logs.")
@app.get("/install-logs")
def install_logs():
 p=LOG/"install.log"; return jsonify(text=p.read_text(errors="replace")[-12000:] if p.exists() else "No logs")

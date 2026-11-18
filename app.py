import os, csv, io, random, math, secrets, hashlib
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for, session, flash, abort,
                   Response, jsonify, send_from_directory)
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-change-me'),
                  SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(BASE, 'ghostguard.db'),
                  SQLALCHEMY_TRACK_MODIFICATIONS=False)
db = SQLAlchemy(app)
lm = LoginManager(app); lm.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    pw = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    must_change = db.Column(db.Boolean, default=True)
class Worksite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80)); district = db.Column(db.String(60))
    lat = db.Column(db.Float); lng = db.Column(db.Float); radius = db.Column(db.Integer, default=300)
    supervisor = db.Column(db.String(80))
class Worker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(12), unique=True); name = db.Column(db.String(100)); age = db.Column(db.Integer)
    phone = db.Column(db.String(15)); district = db.Column(db.String(60)); state = db.Column(db.String(40), default='Maharashtra')
    job_card = db.Column(db.String(30)); site_id = db.Column(db.Integer, db.ForeignKey('worksite.id'))
    wage = db.Column(db.Integer, default=312); bio_hash = db.Column(db.String(64)); acct = db.Column(db.String(20))
    status = db.Column(db.String(10), default='Active'); risk = db.Column(db.Integer, default=0)
    synthetic = db.Column(db.Boolean, default=False); ftype = db.Column(db.String(12))
    registered = db.Column(db.DateTime, default=datetime.utcnow)
    site = db.relationship('Worksite')
    attendance = db.relationship('Attendance', backref='worker', order_by='Attendance.day.desc()')
    events = db.relationship('FreezeEvent', backref='worker', order_by='FreezeEvent.at.desc()')
class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id')); day = db.Column(db.Integer)
    present = db.Column(db.Boolean); lat = db.Column(db.Float); lng = db.Column(db.Float)
    dist = db.Column(db.Float); bio = db.Column(db.Float); pay = db.Column(db.Integer); risk = db.Column(db.Integer)
class FreezeEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id')); action = db.Column(db.String(10))
    reason = db.Column(db.String(300)); by = db.Column(db.String(40)); at = db.Column(db.DateTime, default=datetime.utcnow)
class Audit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(40)); action = db.Column(db.String(60)); target = db.Column(db.String(120))
    at = db.Column(db.DateTime, default=datetime.utcnow)

PERMS = {'freeze': {'super_admin', 'district_admin'}, 'write': {'super_admin', 'district_admin', 'field_officer'},
         'delete': {'super_admin'}, 'audit': {'super_admin'}, 'export': {'super_admin', 'district_admin', 'auditor'},
         'reset': {'super_admin'}}
def can(p): return current_user.is_authenticated and current_user.role in PERMS[p]
def need(p):
    def d(f):
        @wraps(f)
        @login_required
        def w(*a, **k):
            if not can(p): abort(403)
            return f(*a, **k)
        return w
    return d
def log(action, target=''):
    db.session.add(Audit(user=current_user.username if current_user.is_authenticated else '-', action=action, target=target))
def cat(r): return 'Low' if r < 30 else 'Medium' if r < 60 else 'High' if r < 80 else 'Critical'
RANGES = {'Low': (0, 29), 'Medium': (30, 59), 'High': (60, 79), 'Critical': (80, 100)}
app.jinja_env.globals.update(csrf=lambda: session.setdefault('csrf', secrets.token_hex(16)), can=can, cat=cat)
@lm.user_loader
def load(i): return db.session.get(User, int(i))

@app.before_request
def guard():
    if request.method == 'POST' and (not session.get('csrf') or request.form.get('csrf') != session['csrf']): abort(400, 'Invalid CSRF token')
    if current_user.is_authenticated and current_user.must_change and request.endpoint not in ('change_password', 'logout', 'static'):
        return redirect(url_for('change_password'))

# ---------- scoring (rule engine, ported from the original prototype) ----------
def hav(a, b, c, d):
    r = math.pi / 180; x = math.sin((c - a) * r / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin((d - b) * r / 2) ** 2
    return 12742000 * math.asin(math.sqrt(x))
def rscore(dist, rad, present, pay, wage, bio, dup, acct):
    s = 0
    if present and dist > rad: s += round(25 + min(15, (dist - rad) / 150))
    if dup: s += 45
    if pay > 0 and not present: s += 35
    elif pay > wage: s += 25
    if bio < .7: s += 20 if bio < .5 else 15
    if acct: s += 20
    if present and dist < 3: s += 10
    return min(100, round(.85 * min(100, s)))

def seed():
    R = random.Random(2026); rr = R.uniform
    nm = ['Bhor', 'Velhe', 'Mulshi', 'Maval', 'Purandar', 'Haveli', 'Junnar', 'Khed', 'Ambegaon', 'Daund', 'Baramati', 'Indapur']
    sup = ['R. Kulkarni', 'S. Jadhav', 'M. Shinde', 'A. Pawar', 'V. More', 'P. Gaikwad']
    sites = [Worksite(name=n, district='Pune', lat=18.3 + rr(0, .5), lng=73.5 + rr(0, .7), radius=300, supervisor=sup[i % 6]) for i, n in enumerate(nm)]
    db.session.add_all(sites); db.session.flush()
    fn = ['Ramesh', 'Sunita', 'Ganesh', 'Meena', 'Dattu', 'Lata', 'Sachin', 'Kavita', 'Anil', 'Sangeeta', 'Vijay', 'Asha']
    ln = ['Patil', 'Jadhav', 'Shinde', 'More', 'Pawar', 'Gaikwad', 'Kale', 'Bhosale', 'Chavan', 'Waghmare', 'Salunke', 'Mane']
    W = [Worker(code=f'W{i+1:03d}', name=f'{R.choice(fn)} {R.choice(ln)}', age=R.randint(19, 62), phone='9' + ''.join(R.choice('0123456789') for _ in range(9)),
                district='Pune', job_card=f'MH-{i+1:05d}', site_id=sites[i % 12].id, wage=312, bio_hash='B%x' % R.getrandbits(30),
                acct=f'AC{7000+i}', synthetic=True) for i in range(180)]
    idx = {x.id: i for i, x in enumerate(sites)}
    pool = [w for w in W if idx[w.site_id] % 6 in (2, 4)]
    def take(t, n):
        c = 0
        while c < n:
            w = R.choice(pool) if R.random() < .6 else R.choice(W)
            if w.ftype: continue
            w.ftype = t; c += 1
    take('ghost', 9); take('proxy', 12); take('payment', 10); take('dup', 8)
    for i, w in enumerate([w for w in W if w.ftype == 'ghost']): w.acct = f'AC9{i%3}'
    for w in [w for w in W if w.ftype == 'dup']:
        a = R.choice(W)
        while a.ftype: a = R.choice(W)
        a.ftype = 'dup'; w.bio_hash = a.bio_hash
    hc, ac = {}, {}
    for w in W: hc[w.bio_hash] = hc.get(w.bio_hash, 0) + 1; ac[w.acct] = ac.get(w.acct, 0) + 1
    db.session.add_all(W); db.session.flush()
    for w in W:
        s = sites[idx[w.site_id]]; mx = 0
        for d in range(14):
            present = R.random() < .88; dist = rr(5, 220); bio = rr(.88, .99); pay = 0
            if not w.ftype:
                if R.random() < .012: dist = rr(320, 520)
                if R.random() < .012: bio = rr(.6, .75)
            if w.ftype == 'ghost': present = True; dist = rr(0, 2); bio = rr(.3, .62)
            if w.ftype == 'proxy' and present and R.random() < .7: dist = rr(900, 6000); bio = rr(.7, .9)
            if present: pay = w.wage
            if w.ftype == 'payment' and R.random() < .3: pay = 2 * w.wage if present else w.wage
            if not present and not pay: continue
            b = rr(0, 6.2832); lat = s.lat + dist * math.cos(b) / 111320; lng = s.lng + dist * math.sin(b) / (111320 * math.cos(math.radians(s.lat)))
            dist = hav(s.lat, s.lng, lat, lng)
            risk = rscore(dist, s.radius, present, pay, w.wage, bio, hc[w.bio_hash] > 1, ac[w.acct] > 1); mx = max(mx, risk)
            db.session.add(Attendance(worker_id=w.id, day=d + 1, present=present, lat=lat, lng=lng, dist=dist, bio=bio, pay=pay, risk=risk))
        w.risk = mx
    db.session.commit()

def init():
    db.create_all()
    if not User.query.first():
        for u, r in [('admin', 'super_admin'), ('district', 'district_admin'), ('field', 'field_officer'), ('auditor', 'auditor')]:
            db.session.add(User(username=u, role=r, pw=generate_password_hash('Admin@123'), must_change=True))
        db.session.commit()
    if not Worker.query.first(): seed()

# ---------- auth ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form.get('username', '').strip()).first()
        if u and check_password_hash(u.pw, request.form.get('password', '')):
            login_user(u); log('login'); db.session.commit(); return redirect(url_for('home'))
        flash('Wrong username or password.', 'err')
    return render_template('auth.html', title='Sign in', login=True)
@app.route('/logout', methods=['POST'])
@login_required
def logout():
    log('logout'); db.session.commit(); logout_user(); return redirect(url_for('login'))
@app.route('/password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old, new = request.form.get('old', ''), request.form.get('new', '')
        if not check_password_hash(current_user.pw, old): flash('Current password is wrong.', 'err')
        elif len(new) < 8 or new == old or not any(c.isdigit() for c in new): flash('New password needs 8+ characters, a digit, and must differ from the old one.', 'err')
        else:
            current_user.pw = generate_password_hash(new); current_user.must_change = False; log('password changed'); db.session.commit()
            flash('Password updated.', 'ok'); return redirect(url_for('home'))
    return render_template('auth.html', title='Change password', login=False)

# ---------- pages ----------
@app.route('/')
@login_required
def home():
    ws = Worker.query.all(); counts = {c: sum(1 for w in ws if cat(w.risk) == c) for c in RANGES}
    flagged = Attendance.query.filter(Attendance.risk >= 40).count()
    top = Worker.query.order_by(Worker.risk.desc()).limit(10).all()
    recent = Attendance.query.filter(Attendance.risk >= 40).order_by(Attendance.risk.desc(), Attendance.id.desc()).limit(6).all()
    srows = []
    for s in Worksite.query.all():
        ids = [x.id for x in Worker.query.filter_by(site_id=s.id)]
        c = Attendance.query.filter(Attendance.worker_id.in_(ids)).count() or 1
        f = Attendance.query.filter(Attendance.worker_id.in_(ids), Attendance.risk >= 40).count()
        srows.append(dict(name=s.name, sup=s.supervisor, workers=len(ids), flagged=f, rate=f / c))
    srows.sort(key=lambda r: -r['rate'])
    return render_template('home.html', n=len(ws), active=sum(w.status == 'Active' for w in ws), frozen=sum(w.status == 'Frozen' for w in ws),
                           flagged=flagged, records=Attendance.query.count(), sites=Worksite.query.count(), counts=counts, top=top,
                           recent=recent, srows=srows)

@app.route('/workers')
@login_required
def workers():
    q = Worker.query; s = request.args.get('q', '').strip(); site = request.args.get('site', type=int); c = request.args.get('cat', '')
    if s: q = q.filter(db.or_(Worker.name.ilike(f'%{s}%'), Worker.code.ilike(f'%{s}%'), Worker.job_card.ilike(f'%{s}%')))
    if site: q = q.filter(Worker.site_id == site)
    if c in RANGES: q = q.filter(Worker.risk.between(*RANGES[c]))
    sort = request.args.get('sort', 'code'); col = {'code': Worker.code, 'name': Worker.name, 'risk': Worker.risk.desc()}.get(sort, Worker.code)
    p = q.order_by(col).paginate(page=request.args.get('page', 1, type=int), per_page=20, error_out=False)
    return render_template('workers.html', p=p, sites=Worksite.query.all(), s=s, site=site, c=c, sort=sort)

def validate(f):
    name, phone = f.get('name', '').strip(), f.get('phone', '').strip()
    try: age, wage, site = int(f.get('age', '')), int(f.get('wage', '')), int(f.get('site_id', ''))
    except ValueError: return None, 'Age, wage and worksite must be numbers.'
    if len(name) < 3: return None, 'Name must have at least 3 characters.'
    if not (18 <= age <= 90): return None, 'Age must be between 18 and 90.'
    if not (phone.isdigit() and len(phone) == 10): return None, 'Phone must be 10 digits.'
    if not (50 <= wage <= 2000): return None, 'Daily wage must be between 50 and 2000.'
    if not db.session.get(Worksite, site): return None, 'Choose a valid worksite.'
    return dict(name=name, age=age, phone=phone, wage=wage, site_id=site), None

@app.route('/workers/new', methods=['GET', 'POST'])
@need('write')
def worker_new():
    if request.method == 'POST':
        d, err = validate(request.form); ref = request.form.get('bio_ref', '').strip()
        if not err and len(ref) < 6: err = 'Biometric reference ID must have at least 6 characters.'
        if err: flash(err, 'err')
        else:
            n = (db.session.query(db.func.max(Worker.id)).scalar() or 0) + 1
            w = Worker(code=f'W{n+1000:04d}', district=request.form.get('district', 'Pune').strip() or 'Pune', job_card=f'MH-{n+90000:05d}',
                       bio_hash=hashlib.sha256(ref.encode()).hexdigest(), acct='AC' + secrets.token_hex(3), **d)
            db.session.add(w); db.session.flush(); log('worker created', w.code); db.session.commit()
            flash(f'Worker {w.code} registered.', 'ok'); return redirect(url_for('worker', wid=w.id))
    return render_template('worker_new.html', sites=Worksite.query.all())

@app.route('/workers/<int:wid>')
@login_required
def worker(wid):
    w = db.get_or_404(Worker, wid)
    return render_template('worker.html', w=w, att=w.attendance[:40], sites=Worksite.query.all(),
                           dup=Worker.query.filter(Worker.bio_hash == w.bio_hash, Worker.id != w.id).all(),
                           shared=Worker.query.filter(Worker.acct == w.acct, Worker.id != w.id).all(),
                           paid=sum(a.pay for a in w.attendance), pending=sum(w.wage for a in w.attendance if a.present and not a.pay))

@app.route('/workers/<int:wid>/edit', methods=['POST'])
@need('write')
def worker_edit(wid):
    w = db.get_or_404(Worker, wid); d, err = validate({**request.form, 'age': request.form.get('age', w.age)})
    if err: flash(err, 'err')
    else:
        for k, v in d.items(): setattr(w, k, v)
        log('worker edited', w.code); db.session.commit(); flash('Worker updated.', 'ok')
    return redirect(url_for('worker', wid=wid))

@app.route('/workers/<int:wid>/status', methods=['POST'])
@need('freeze')
def worker_status(wid):
    w = db.get_or_404(Worker, wid); act = request.form.get('action'); reason = request.form.get('reason', '').strip()
    if act not in ('freeze', 'unfreeze') or len(reason) < 5: flash('A reason of at least 5 characters is required.', 'err'); return redirect(url_for('worker', wid=wid))
    if act == 'freeze' and w.status == 'Frozen' or act == 'unfreeze' and w.status != 'Frozen': flash('Status already set.', 'err'); return redirect(url_for('worker', wid=wid))
    w.status = 'Frozen' if act == 'freeze' else 'Active'
    db.session.add(FreezeEvent(worker_id=w.id, action=act, reason=reason, by=current_user.username)); log(f'account {act}d', f'{w.code}: {reason}'); db.session.commit()
    flash(f'Account {act}d. This status does not stop wages or benefits.', 'ok'); return redirect(url_for('worker', wid=wid))

@app.route('/workers/<int:wid>/delete', methods=['POST'])
@need('delete')
def worker_delete(wid):
    w = db.get_or_404(Worker, wid); Attendance.query.filter_by(worker_id=wid).delete(); FreezeEvent.query.filter_by(worker_id=wid).delete()
    log('worker deleted', w.code); db.session.delete(w); db.session.commit(); flash('Worker deleted.', 'ok'); return redirect(url_for('workers'))

@app.route('/workers/export.csv')
@need('export')
def export():
    o = io.StringIO(); c = csv.writer(o); c.writerow(['code', 'name', 'age', 'phone', 'district', 'job_card', 'worksite', 'wage', 'status', 'risk', 'category', 'synthetic'])
    for w in Worker.query.order_by(Worker.code): c.writerow([w.code, w.name, w.age, w.phone, w.district, w.job_card, w.site.name, w.wage, w.status, w.risk, cat(w.risk), w.synthetic])
    log('export workers'); db.session.commit()
    return Response(o.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=workers.csv'})

@app.route('/map')
@login_required
def map_page(): return render_template('map.html')
@app.route('/api/map')
@login_required
def api_map():
    out = []
    for s in Worksite.query.all():
        ids = [w.id for w in Worker.query.filter_by(site_id=s.id)]
        n = Attendance.query.filter(Attendance.worker_id.in_(ids)).count() or 1; f = Attendance.query.filter(Attendance.worker_id.in_(ids), Attendance.risk >= 40).count()
        out.append(dict(id=s.id, name=s.name, lat=s.lat, lng=s.lng, radius=s.radius, sup=s.supervisor, workers=len(ids), flagged=f, rate=round(f / n, 3)))
    pts = [dict(lat=a.lat, lng=a.lng, w=a.worker.code, name=a.worker.name, risk=a.risk, dist=round(a.dist), day=a.day) for a in Attendance.query.filter(Attendance.risk >= 40).order_by(Attendance.risk.desc()).limit(400)]
    return jsonify(sites=out, points=pts)

@app.route('/engine')
@login_required
def engine(): return render_template('engine.html')
@app.route('/engine-app')
@login_required
def engine_app(): return send_from_directory(os.path.join(BASE, 'engine'), 'engine.html')

@app.route('/audit')
@need('audit')
def audit(): return render_template('audit.html', rows=Audit.query.order_by(Audit.at.desc()).limit(300).all())
@app.route('/reset', methods=['POST'])
@need('reset')
def reset():
    for m in (Attendance, FreezeEvent, Worker, Worksite): m.query.delete()
    db.session.commit(); seed(); log('demo data reset'); db.session.commit(); flash('Demo data reset.', 'ok'); return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context(): init()
    app.run(debug=False)

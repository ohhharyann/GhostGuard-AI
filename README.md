# GhostGuard AI (full-stack upgrade)

Flask + SQLite + Flask-Login. The original browser fraud engine (alerts, network check, evaluation metrics, Live Check) is kept unchanged and opens under **Fraud Engine**.

## Run on Windows (CMD)
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000. The database (`ghostguard.db`) and the synthetic demo data are created on first run and are not recreated on restart.

Optional: `set SECRET_KEY=your-long-random-string` before `python app.py` (see `.env.example`).

## Demo accounts
All use password `Admin@123` and must change it on first login.

| Username | Role | Can do |
|---|---|---|
| admin | Super Admin | everything, incl. delete workers, audit logs, reset demo data |
| district | District Administrator | add/edit workers, freeze/unfreeze, export |
| field | Field Officer | add/edit workers |
| auditor | Auditor | read-only, export |

Permissions are enforced on the server. All forms use CSRF tokens; passwords are hashed.

## What is built
Login/logout/change password · workers (search, filter, sort, pagination, add, edit, profile tabs, delete, CSV export) · freeze/unfreeze with mandatory reason, history and audit log (human action only, wages unaffected) · Leaflet map with Street/Satellite/Terrain layers, geofence circles, flagged attendance points from the database · overview dashboard from database counts · audit log · reset demo data.

## Limitations (not built)
- The SQLite risk scores use the rule engine only (ported to Python). The Isolation Forest, evaluation metrics and Live Check run in the browser engine page on its own generated dataset, not on the database.
- No separate Attendance, Payments, Alerts-investigation, User Management, Reports (beyond workers CSV) or Settings pages; no Cytoscape network graph, marker clustering, notifications or dark mode.
- Not tested against a live server here (the build environment had no network to install Flask-SQLAlchemy); run it and report any error text.
- Demo data is synthetic. Map tiles need internet access.

## UI redesign (this version)
Only templates, `static/style.css` and `static/app.js` were redesigned. Models, routes, auth, permissions and the fraud engine are unchanged, except `home()` in `app.py`, which now also passes active-worker count, recent alerts and a per-worksite summary to the dashboard (all read from the database).

- Shared layout (`base.html`): collapsible sidebar (saved between visits), off-canvas menu on mobile, top bar with worker search, light/dark theme switch and account menu.
- Dashboard: KPI cards, two charts, recent alerts, worksite risk summary, map preview, highest-risk workers.
- Workers: sortable columns, filters, risk bars, status badges, per-row action menu, empty states. Profile tabs: Overview, Personal details, Attendance, Payments, Fraud history, Biometric, Account status.
- Freeze/unfreeze, delete, sign out and reset demo data all use a confirmation dialog. Freeze/unfreeze still requires a reason.
- Map: full-width, Street/Satellite/Terrain switcher, geofence circles, flagged attendance points, worksite filter, legend, loading and error states.
- Responsive layouts and a login page with a split layout.

### Not in this redesign
- Sidebar links exist only for pages that exist: Overview, Workers, Worksites & Maps, Fraud Engine, Audit Logs (Super Admin). Attendance, Payments, Fraud Alerts, Investigations, Reports, User Management and Settings have no backend pages yet, so they are not linked. Pending investigations is not shown because no investigation data exists.
- The Fraud Engine page is the original page in an iframe and keeps its own look; the theme switch does not restyle it. Dashboard charts pick up the theme on page reload.

### Testing status
Checked: every template renders with mock data (including empty states) and all page scripts pass a JavaScript syntax check; `app.py` compiles. Not checked: running the Flask server, logging in and out, role-based menus, search and filters against the database, the freeze dialog, live map layer switching, and responsive layouts in a real browser or console errors. Run the app and test these before presenting.

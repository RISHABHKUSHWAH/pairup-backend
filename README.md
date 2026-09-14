# PairUp — Backend (Python Django + Django REST Framework)

This is the **Python Django** implementation of the PairUp REST API backend, providing 100% drop-in compatibility with the original PHP backend. It powers:
- The web frontend in `../website`
- The React Native mobile app in `../mobile`
- The Flutter mobile app in `../flutter_app`

---

## Quick Start (Local Development)

You need Python 3.10+ installed.

### 1. Set Up Environment & Install Dependencies
```powershell
cd backend_django
# Create virtual environment (if not already created)
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Windows CMD:
.\.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Configure Environment & Migrate
```powershell
# Copy example configuration (defaults to SQLite db.sqlite3)
if (!(Test-Path .env)) { Copy-Item .env.example .env }

# Run database migrations
python manage.py migrate

# Seed initial platform settings & site pages (Privacy, Terms, Help, Contact)
python manage.py seed_site_pages
```

### 3. Create Admin / Superadmin Accounts
```powershell
# Superadmin (can promote/revoke admins, edit platform settings & pages)
python manage.py create_superadmin "Super Admin" super@example.com "supersecret123"

# Admin (can resolve disputes, approve mentors, review audit logs)
python manage.py create_admin "Admin Name" admin@example.com "adminsecret123"
```

### 4. Run the Development Server
```powershell
python manage.py runserver 127.0.0.1:8080
```
The API is now live at `http://127.0.0.1:8080` (and Django Admin at `http://127.0.0.1:8080/admin/`).

---

## Running the Automated Test Suite
```powershell
python manage.py test api
```
Runs comprehensive tests verifying registration, JWT authentication, mentor profiles, escrow bookings, dispute resolution, chat anti-leak guards, problem posts, and admin/superadmin flows.

---

## Production Configuration (MySQL / PostgreSQL)

1. Set up your MySQL database.
2. Edit `.env`:
   ```env
   SECRET_KEY=generate-a-strong-secret-key
   DEBUG=False
   ALLOWED_HOSTS=api.yourdomain.com

   JWT_SECRET=generate-a-long-random-jwt-secret
   JWT_TTL_HOURS=24
   CORS_ALLOWED_ORIGINS=https://yourdomain.com

   DB_CONNECTION=mysql
   DB_NAME=pairup
   DB_USER=your_db_user
   DB_PASS=your_db_password
   DB_HOST=127.0.0.1
   DB_PORT=3306
   ```
3. Run migrations and collect static files:
   ```powershell
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

---

## API Reference

All requests and responses use JSON (except `POST /api/mentors/me/photo` which uses `multipart/form-data`). Authenticated routes require `Authorization: Bearer <token>`.

| Method | Path | Auth Role | Description |
|---|---|---|---|
| **POST** | `/api/auth/register` | Public | Register (`{name, email, password, role: "learner"|"mentor"}`) |
| **POST** | `/api/auth/login` | Public | Login (`{email, password}`) -> JWT token & user |
| **GET** | `/api/auth/me` | Authenticated | Current user details |
| **PUT** | `/api/auth/me` | Authenticated | Update name and/or password |
| **GET** | `/api/mentors` | Public | Browse mentors (`?skill=&search=&online=1&sort=rating|price_low|price_high|sessions`) |
| **GET** | `/api/mentors/{id}` | Public | Mentor profile + sections + reviews |
| **PUT** | `/api/mentors/me` | Mentor | Update own mentor profile |
| **PUT** | `/api/mentors/me/online-status` | Mentor | Toggle online status (`{online: true|false}`) |
| **POST** | `/api/mentors/me/photo` | Mentor | Upload profile picture (< 2MB JPEG/PNG/WebP) |
| **POST** | `/api/mentors/apply` | Learner | Apply to become a mentor |
| **POST/DELETE** | `/api/mentors/me/experience` | Mentor | Add / delete experience items |
| **POST/DELETE** | `/api/mentors/me/projects` | Mentor | Add / delete project items |
| **POST/DELETE** | `/api/mentors/me/education` | Mentor | Add / delete education items |
| **POST/DELETE** | `/api/mentors/me/certifications` | Mentor | Add / delete certification items |
| **POST/DELETE** | `/api/mentors/me/awards` | Mentor | Add / delete award items |
| **PUT** | `/api/mentors/me/availability` | Mentor | Set weekly availability slots |
| **POST** | `/api/bookings` | Learner | Request a session (`{mentor_id, topic, duration_minutes, price}`) |
| **GET** | `/api/bookings` | Authenticated | List all bookings for current user |
| **POST** | `/api/bookings/{id}/accept` | Mentor | Accept session request |
| **POST** | `/api/bookings/{id}/pay` | Learner | Pay session — funds held in simulated escrow |
| **POST** | `/api/bookings/{id}/complete` | Participant | Mark session complete — releases escrow funds |
| **POST** | `/api/bookings/{id}/dispute` | Participant | Dispute paid session (`{reason: "..."}`) |
| **GET** | `/api/bookings/{id}` | Participant | Session detail |
| **GET/PUT** | `/api/bookings/{id}/notes` | Participant | Private per-user session notes (auto-saved) |
| **GET** | `/api/payments/mine` | Authenticated | User payment history |
| **POST** | `/api/messages` | Authenticated | Send message (filtered for external contact info leaks) |
| **GET** | `/api/messages?with={id}` | Authenticated | Chat thread with another user |
| **GET** | `/api/messages/conversations` | Authenticated | Conversations list with latest message preview |
| **POST** | `/api/reviews` | Learner | Review completed session (`{booking_id, rating, comment}`) |
| **GET** | `/api/reviews?mentor_id={id}` | Public | Reviews for a mentor |
| **GET** | `/api/reviews/mine` | Authenticated | My submitted or received reviews |
| **POST** | `/api/problems` | Learner | Post a problem request |
| **GET** | `/api/problems` | Authenticated | Browse open problems |
| **GET** | `/api/problems/mine` | Learner | My problem posts |
| **POST/DEL** | `/api/problems/{id}/close` | Learner | Close or delete a problem |
| **POST** | `/api/problems/{id}/proposals` | Mentor | Submit proposal on problem |
| **GET** | `/api/problems/{id}/proposals` | Learner | View proposals on problem |
| **POST** | `/api/problems/{id}/proposals/{pId}/accept` | Learner | Accept proposal & create booking |
| **GET** | `/api/proposals/mine` | Mentor | My submitted proposals |
| **GET** | `/api/admin/stats` | Admin | Metrics & 14-day revenue series |
| **GET** | `/api/admin/users` | Admin | List users filtered by role |
| **GET** | `/api/admin/all-users` | Admin | Combined user list |
| **GET** | `/api/admin/payments` | Admin | Payment history with user details |
| **GET** | `/api/admin/bookings` | Admin | All booking records |
| **GET** | `/api/admin/mentors/pending` | Admin | Pending mentor approvals |
| **POST** | `/api/admin/mentors/{id}/approve` | Admin | Approve mentor |
| **POST** | `/api/admin/mentors/{id}/reject` | Admin | Reject mentor |
| **GET** | `/api/admin/disputes` | Admin | Open disputes |
| **POST** | `/api/admin/disputes/{id}/resolve` | Admin | Resolve dispute (`{action: "release"|"refund"}`) |
| **GET** | `/api/admin/payouts` | Admin | Mentor payout balance report |
| **GET/PUT** | `/api/admin/settings` | Admin/Super | Platform settings (commission rate) |
| **GET/DEL** | `/api/admin/reviews` | Admin | Review moderation |
| **GET/POST** | `/api/admin/problems` | Admin | Problem moderation & force-close |
| **GET** | `/api/admin/refunds` | Admin | Refund logs |
| **GET** | `/api/admin/notifications` | Admin | System status alerts |
| **GET** | `/api/admin/audit-logs` | Admin | Accountability audit log |
| **GET** | `/api/admin/contact-messages` | Admin | Contact form submissions |
| **GET** | `/api/superadmin/admins` | Superadmin | List all admins |
| **GET** | `/api/superadmin/search-users` | Superadmin | Search users to promote |
| **POST** | `/api/superadmin/admins/{id}/promote` | Superadmin | Promote user to admin |
| **POST** | `/api/superadmin/admins/{id}/revoke` | Superadmin | Revoke admin access |
| **GET** | `/api/pages/{slug}` | Public | Content for privacy/terms/help/contact |
| **GET/PUT** | `/api/admin/pages` | Superadmin | Edit page content |
| **POST** | `/api/contact` | Public | Submit contact form |
"# pairup-backend" 

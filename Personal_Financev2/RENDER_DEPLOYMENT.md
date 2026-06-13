# Render Deployment Guide

*Step-by-step guide to put your Django app live on the internet*

---

## 🧠 The Big Picture

Normally your app runs only on YOUR computer (`localhost`). Nobody else can access it.
Render is a cloud service that hosts your app 24/7 so anyone can visit it.

You give Render 3 things:
1. **Your code** — via GitHub
2. **What to install** — `requirements.txt`
3. **How to run it** — `Procfile`

---

## 📁 Files You Need in Your Project

### 1. `requirements.txt`
A shopping list of Python packages your app needs.
Render reads this and runs `pip install -r requirements.txt`.

```txt
django==6.0.5
gunicorn==23.0.0
whitenoise==6.9.0
psycopg2-binary==2.9.12
... (all other packages)
```

### 2. `runtime.txt`
Tells Render which Python version to use.

```
python-3.13.0
```

### 3. `Procfile`
Tells Render how to START your app. Like telling a waiter "this is what I ordered".

```
web: gunicorn Personal_Financev2.wsgi --log-file -
```

**What this means:**
- `web:` — this is a web process
- `gunicorn` — a server that runs Django (better than `runserver`)
- `Personal_Financev2.wsgi` — tells gunicorn where your Django app is
- `--log-file -` — print logs to console so Render can show them

---

## 🔧 Changes to `settings.py`

Think of `settings.py` as the control panel of your app. We need to make it flexible — able to work BOTH on your computer AND on Render.

### Why?
Your computer uses:
- Secret key: `django-insecure-mdysx8...`
- Database: `localhost` (PostgreSQL on your PC)

Render uses:
- Secret key: something secret and different
- Database: a big URL like `postgresql://user:pass@render.com/db`

So instead of writing fixed values, we tell Django to **look at environment variables** first. If a variable exists (on Render), use it. If not, fall back to the local value.

```python
import os

# If Render provides SECRET_KEY, use it. Otherwise use local one.
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-mdysx8l3f...')

# If Render sets DEBUG=False, turn off debug mode.
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# If Render provides ALLOWED_HOSTS, use those. Otherwise allow all for local dev.
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
```

### Database Setup — The Smart Way

```python
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # We're on Render! Parse the URL into parts Django understands.
    import urllib.parse
    url = urllib.parse.urlparse(DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': url.path[1:],      # e.g., "finance_db"
            'USER': url.username,       # e.g., "finance_user"
            'PASSWORD': url.password,   # e.g., "abc123..."
            'HOST': url.hostname,       # e.g., "dpg-xxx.render.com"
            'PORT': url.port or '5432', # default PostgreSQL port
        }
    }
else:
    # We're on local computer — use local PostgreSQL
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'Personal_Finance_Tracker_DBv2',
            'USER': 'postgres',
            'PASSWORD': 'Admin@123',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }
```

### Static Files (CSS, JS, Images)

Normally Django doesn't serve static files in production. We add WhiteNoise — a tool that DOES serve them.

```python
# In MIDDLEWARE — add WhiteNoise right after SecurityMiddleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # <-- this is new
    ...
]

# At the bottom of settings.py
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if os.environ.get('CSRF_TRUSTED_ORIGINS') else []
```

---

## 🌐 Step-by-Step on Render Website

### Step 1: Create a Web Service

| Screen field | What to type |
|-------------|--------------|
| **New +** → **Web Service** | Connect your GitHub account |
| Select repo | `davedragon05/Personal-Finance-Tracker` |
| **Name** | `jarvis-finance` |
| **Region** | Choose closest to you (e.g., Singapore) |
| **Branch** | `main` |
| **Root Directory** | `Personal_Financev2` ⬅️ IMPORTANT! |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt && python manage.py collectstatic --noinput` |
| **Start Command** | `gunicorn Personal_Financev2.wsgi --log-file -` |
| **Instance Type** | `Free` |

**What is Root Directory?**
Your `manage.py`, `requirements.txt`, and `Procfile` are inside the `Personal_Financev2/` folder. Setting Root Directory tells Render "go into that folder first before doing anything."

**Why no `migrate` in Build Command?**
On Render's free plan, the database isn't ready during the BUILD phase. Build is just for preparing files. The database only exists at RUNTIME. So we run migrations separately.

---

### Step 2: Add Environment Variables (Click "Advanced")

Environment variables are like secret notes your app can read. They keep sensitive info (passwords, keys) out of your code.

Click the **Advanced** button at the bottom, then **Add Environment Variable** for each:

| Key | Value | Why? |
|-----|-------|------|
| `SECRET_KEY` | *(run command below)* | Signs sessions & cookies |
| `DEBUG` | `False` | Turn off debug mode (security) |
| `ALLOWED_HOSTS` | `.onrender.com,jarvis-finance.onrender.com` | Which domains are allowed |
| `CSRF_TRUSTED_ORIGINS` | `https://jarvis-finance.onrender.com` | For form submissions |

Generate a random secret key in your terminal:
```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

### Step 3: Create a PostgreSQL Database

Your local database (`Personal_Finance_Tracker_DBv2`) only exists on YOUR computer. Render needs its own database in the cloud.

1. Click **New +** → **PostgreSQL**
2. Fill in:
   - **Name**: `finance-db` (just a label, any name works)
   - **Database**: `finance_db`
   - **User**: `finance_user`
   - **Region**: same as your web service
3. Click **Create Database**

After creation, find the **External Connection String** — it looks like this:

```
postgresql://finance_user:mW41pqeyC6Kg30EjhuJTv4Ev9lNiZEQ4@dpg-d8mf7qu7r5hc739njf8g-a.singapore-postgres.render.com/finance_db_qym0
```

This string contains everything Django needs to connect:
```
postgresql:// USERNAME : PASSWORD @ HOST : PORT / DATABASE
```

---

### Step 4: Link Database to Web Service

Your web service and database need to know about each other.

1. Go to your **Web Service** (`jarvis-finance`)
2. Click **Environment** tab
3. Click **Add Environment Variable**
4. **Name**: `DATABASE_URL`
5. **Value**: *(paste the External Connection String)*
6. Click **Save Changes**

Now when your app starts on Render, it reads `DATABASE_URL` and connects to the cloud database!

---

### Step 5: Run Migrations

Migrations are like setting up the tables in your database. You need to run them once.

**On free Render plan:** There's no Shell access. So we run migrations FROM our local computer, but pointing TO Render's database.

```powershell
# 1. Set the DATABASE_URL to Render's database
$env:DATABASE_URL = "postgresql://finance_user:mW41pqeyC6Kg30EjhuJTv4Ev9lNiZEQ4@dpg-d8mf7qu7r5hc739njf8g-a.singapore-postgres.render.com/finance_db_qym0"

# 2. Run migrations (this creates all the tables)
python manage.py migrate

# 3. Create a superuser so you can log into /admin/
python manage.py createsuperuser --noinput --username david --email david@example.com
```

*(The password was set to `Admin123` via environment variable)*

---

### Step 6: Trigger a Deploy

1. In your Web Service dashboard, click **Manual Deploy** → **Deploy latest commit**
2. Wait for the build to finish (check **Logs** tab for live output)
3. Once done, visit **https://jarvis-finance.onrender.com**

---

## ✅ You're Live!

| What | URL |
|------|-----|
| Your app | `https://jarvis-finance.onrender.com` |
| Admin panel | `https://jarvis-finance.onrender.com/admin/` |
| Login | `david` / `Admin123` |

---

## 🧹 Local Development (Back to Your Computer)

To run locally again, just use `python manage.py runserver` as usual. Django will see there's no `DATABASE_URL` environment variable set in your terminal and use the local PostgreSQL settings instead.

---

## ❓ Common Issues

**"Build fails — requirements.txt not found"**
→ Check Root Directory is set to `Personal_Financev2`

**"Cannot connect to database"**
→ Make sure you added `DATABASE_URL` environment variable to Web Service

**"CSRF verification failed"**
→ Make sure `CSRF_TRUSTED_ORIGINS` env var matches your actual Render URL

**"App loads but no CSS styling"**
→ Run `collectstatic` during build (it's in the Build Command already)

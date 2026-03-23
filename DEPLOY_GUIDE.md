# Getting SipSense Online: A Complete Beginner's Guide

This guide assumes you've never deployed a web app before. It walks you through
every single step, from getting a server to having SipSense live on the internet
with a real URL.

---

## Table of Contents

1. [What You're Building](#1-what-youre-building)
2. [What You Need Before Starting](#2-what-you-need-before-starting)
3. [Step 1: Get a Server](#step-1-get-a-server)
4. [Step 2: Get a Domain Name](#step-2-get-a-domain-name)
5. [Step 3: Connect to Your Server](#step-3-connect-to-your-server)
6. [Step 4: Install Docker on the Server](#step-4-install-docker-on-the-server)
7. [Step 5: Get Your Code onto the Server](#step-5-get-your-code-onto-the-server)
8. [Step 6: Configure Environment Variables](#step-6-configure-environment-variables)
9. [Step 7: Build and Start the App](#step-7-build-and-start-the-app)
10. [Step 8: Point Your Domain to the Server](#step-8-point-your-domain-to-the-server)
11. [Step 9: Set Up HTTPS (SSL)](#step-9-set-up-https-ssl)
12. [Step 10: Import Your Whiskey Data](#step-10-import-your-whiskey-data)
13. [Keeping It Running](#keeping-it-running)
14. [Updating the App](#updating-the-app)
15. [Costs Breakdown](#costs-breakdown)
16. [Troubleshooting](#troubleshooting)

---

## 1. What You're Building

When you run SipSense online, here's what happens when someone visits your site:

```
User's browser
      │
      ▼
Your server (e.g., a DigitalOcean "Droplet")
      │
      ▼
Docker is running 3 containers:
   ┌─────────────────────────────────────────────┐
   │  frontend (nginx)  ← serves the React app   │
   │       │                                      │
   │       │ proxies /api/ requests to ──►        │
   │       │                                      │
   │  backend (FastAPI)  ← handles API calls      │
   │       │                                      │
   │       ▼                                      │
   │  db (PostgreSQL)   ← stores all the data     │
   └─────────────────────────────────────────────┘
```

"Docker containers" are like lightweight virtual computers. Each one runs a
single piece of your app. Docker Compose starts all three together.

---

## 2. What You Need Before Starting

- [ ] A **credit card** (for the server — about $6-12/month)
- [ ] Your **Anthropic API key** (for Claude-powered features)
- [ ] A **GitHub account** (you probably have this already)
- [ ] Your SipSense code **pushed to GitHub** (so you can pull it onto the server)
- [ ] About **1-2 hours** of time

Optional but recommended:
- [ ] A **domain name** (~$10-15/year) — otherwise you'll access it via IP address

---

## Step 1: Get a Server

You need a computer that's always on and connected to the internet. Cloud
providers rent these to you for a few dollars a month.

### Recommended: DigitalOcean (simplest for beginners)

1. Go to [digitalocean.com](https://www.digitalocean.com) and create an account
2. Click **"Create"** → **"Droplets"** (their name for a server)
3. Choose these settings:
   - **Region:** Pick the one closest to you (e.g., New York, San Francisco)
   - **Image:** Ubuntu 24.04 LTS
   - **Size:** "Basic" → **Regular** → **$12/mo (2 GB RAM / 1 CPU)**
     - SipSense needs 2GB because PyTorch (the ML library) uses a lot of memory
     - $6/mo (1GB) works too if you add swap space (extra step, shown below)
   - **Authentication:** Choose **"SSH Key"** (more secure than password)

#### What's an SSH key? How do I make one?

An SSH key is like a special password file on your computer. It lets you log
into your server without typing a password every time.

**On your Mac, open Terminal and run:**

```bash
# Check if you already have one
ls ~/.ssh/id_ed25519.pub
```

If that file doesn't exist, create one:

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
# Press Enter 3 times to accept defaults (no passphrase is fine for now)
```

Now copy the PUBLIC key (the .pub file — never share the private one!):

```bash
cat ~/.ssh/id_ed25519.pub
# This prints something like: ssh-ed25519 AAAAC3Nza... your_email@example.com
```

Copy that entire line and paste it into the DigitalOcean SSH key field.

4. Click **"Create Droplet"**
5. Wait ~60 seconds. You'll see an **IP address** like `167.99.123.45`. Write this down!

### Alternative: AWS EC2

If you prefer AWS, the existing `deploy/setup.sh` script is designed for EC2.
The steps are similar but AWS has more configuration screens. For a first-time
deploy, DigitalOcean is simpler.

### Alternative: Hetzner (cheapest)

[Hetzner](https://www.hetzner.com/cloud) offers 2GB servers for ~$4.50/mo.
Same setup process as DigitalOcean.

---

## Step 2: Get a Domain Name

A domain name (like `sipsense.com`) makes your app look professional and is
required for HTTPS. **You can skip this step** and just use the IP address,
but you won't get HTTPS (the lock icon in the browser).

### Where to buy one

1. Go to [Namecheap](https://www.namecheap.com) or [Cloudflare Registrar](https://www.cloudflare.com/products/registrar/)
2. Search for a domain (e.g., `sipsense.app`, `mysipsense.com`)
3. Buy it (~$10-15/year for a `.com`, some TLDs like `.xyz` are ~$2/year)

Don't configure DNS yet — we'll do that in Step 8 after the server is ready.

---

## Step 3: Connect to Your Server

Now you'll "SSH into" your server. This means opening a remote terminal on it.

```bash
# Replace 167.99.123.45 with YOUR server's IP address
ssh root@167.99.123.45
```

The first time, it'll ask "Are you sure you want to continue connecting?" —
type `yes` and press Enter.

You should now see something like:

```
root@ubuntu-sipsense:~#
```

**You're now typing commands on your server, not your Mac.** Everything below
happens on the server unless stated otherwise.

---

## Step 4: Install Docker on the Server

Docker runs your app in containers. Here's how to install it:

```bash
# Update the package list (like refreshing the app store)
apt update

# Install packages that let apt use HTTPS
apt install -y ca-certificates curl

# Add Docker's official GPG key (proves the software is legit)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker's repository to apt (tells apt where to find Docker)
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

Verify it worked:

```bash
docker --version
# Should print something like: Docker version 27.x.x

docker compose version
# Should print something like: Docker Compose version v2.x.x
```

### If you got the $6/mo server (1GB RAM): Add swap space

Swap is like extra RAM that uses disk space. It's slower but prevents crashes:

```bash
# Create a 2GB swap file
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Make it permanent (survives reboots)
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Verify
free -h
# You should see "Swap: 2.0Gi" in the output
```

---

## Step 5: Get Your Code onto the Server

### Option A: Clone from GitHub (recommended)

First, make sure your code is pushed to a GitHub repository. On your Mac:

```bash
# If you haven't pushed to GitHub yet:
cd ~/repos/sipsense
git remote add origin https://github.com/YOUR_USERNAME/sipsense.git
git push -u origin main
```

Then, on your server:

```bash
# Create the app directory
mkdir -p /opt/sipsense

# Clone your repo
git clone https://github.com/YOUR_USERNAME/sipsense.git /opt/sipsense

# Go into the directory
cd /opt/sipsense
```

If your repo is **private**, you'll need to either:
- Use a [GitHub Personal Access Token](https://github.com/settings/tokens)
  and clone with `https://YOUR_TOKEN@github.com/YOUR_USERNAME/sipsense.git`
- Or add your server's SSH key to your GitHub account

### Option B: Copy files directly from your Mac

If you don't want to use GitHub, you can copy files directly. **On your Mac**
(not on the server):

```bash
# This copies your entire project to the server
# Replace 167.99.123.45 with your server's IP
rsync -avz --exclude='node_modules' --exclude='.venv' --exclude='*.db' \
  ~/repos/sipsense/ root@167.99.123.45:/opt/sipsense/
```

---

## Step 6: Configure Environment Variables

Your app needs secret values (API keys, passwords) that shouldn't be in your
code. These go in `.env` files.

```bash
cd /opt/sipsense
```

### For production deployment:

```bash
# Copy the template
cp .env.example .env.production
```

Now edit it:

```bash
nano .env.production
```

This opens a basic text editor. Change the values to:

```
POSTGRES_PASSWORD=REPLACE_WITH_A_STRONG_PASSWORD
JWT_SECRET_KEY=REPLACE_WITH_A_RANDOM_STRING
ANTHROPIC_API_KEY=sk-ant-api03-YOUR_REAL_KEY_HERE
CORS_ORIGINS=https://yourdomain.com
SIPSENSE_ENV=production
```

**How to generate a strong password/secret:**

```bash
# Run this on the server to generate a random string — copy the output
openssl rand -hex 32
```

Use one random string for `POSTGRES_PASSWORD` and a different one for
`JWT_SECRET_KEY`.

**Saving in nano:** Press `Ctrl+O` (that's the letter O, not zero), then
press Enter to save. Press `Ctrl+X` to exit.

---

## Step 7: Build and Start the App

This is the big moment! Docker will download all the dependencies, build your
app, and start everything.

```bash
cd /opt/sipsense

# Build and start all 3 containers (db, backend, frontend)
# The first time takes 5-15 minutes because it downloads and installs everything
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build
```

**What those flags mean:**
- `-f docker-compose.yml -f docker-compose.production.yml` — use both config files
- `up` — start the services
- `-d` — run in background (so you can close your terminal and it keeps running)
- `--build` — rebuild the images from the Dockerfiles

### Watch the build progress

```bash
# See what's happening (live logs, press Ctrl+C to stop watching)
docker compose -f docker-compose.yml -f docker-compose.production.yml logs -f
```

### Check that everything is running

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml ps
```

You should see something like:

```
NAME                 STATUS
sipsense-db-1        Up (healthy)
sipsense-backend-1   Up (healthy)
sipsense-frontend-1  Up
```

All three should say "Up". If the database says "Up (healthy)" that's even
better — the health check passed.

### Test it!

```bash
# Test the backend API
curl http://localhost/api/

# Should return something like:
# {"status":"ok","message":"Welcome to SipSense"}
```

If you got a response, your app is running! Open a web browser and go to:

```
http://YOUR_SERVER_IP_ADDRESS
```

You should see the SipSense frontend. It won't have any whiskey data yet
(we'll import that in Step 10), but the UI should load.

---

## Step 8: Point Your Domain to the Server

*Skip this step if you're not using a domain name.*

You need to create a **DNS A record** that points your domain to your server's
IP address.

### On Namecheap:

1. Log in → "Domain List" → click "Manage" on your domain
2. Go to "Advanced DNS" tab
3. Add a new record:
   - **Type:** A Record
   - **Host:** `@` (this means the root domain, like `sipsense.com`)
   - **Value:** Your server's IP (e.g., `167.99.123.45`)
   - **TTL:** Automatic
4. (Optional) Add another for `www`:
   - **Type:** A Record
   - **Host:** `www`
   - **Value:** Same IP address

### On Cloudflare:

1. Log in → select your domain → "DNS" in the sidebar
2. Click "Add record"
3. Same fields as above

**DNS takes 5-30 minutes to propagate.** You can check if it's working:

```bash
# Run this on your Mac
dig yourdomain.com +short
# Should show your server's IP address
```

Once DNS is working, open `http://yourdomain.com` in your browser — you should
see SipSense!

---

## Step 9: Set Up HTTPS (SSL)

HTTPS gives you the lock icon in the browser and encrypts traffic. It's free
with Let's Encrypt, but since we're running everything in Docker, the easiest
approach is to add a **Caddy reverse proxy** in front of your containers.

*Skip this step if you're not using a domain name — HTTPS requires a domain.*

### Option A: Caddy (simplest — handles SSL automatically)

We'll add a Caddy container that sits in front of nginx and handles SSL.

On your server, create a Caddy configuration file:

```bash
cat > /opt/sipsense/Caddyfile << 'EOF'
yourdomain.com {
    reverse_proxy frontend:80
}
EOF
```

Replace `yourdomain.com` with your actual domain name.

Now create a production compose override that adds Caddy:

```bash
cat >> /opt/sipsense/docker-compose.production.yml << 'EOF'

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    depends_on:
      - frontend
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
EOF
```

And add the volumes:

```bash
# Open the file and add caddy_data and caddy_config under volumes:
nano /opt/sipsense/docker-compose.production.yml
```

Then update the frontend service in production compose to NOT expose port 80
publicly (Caddy will handle that instead):

In `docker-compose.production.yml`, change the frontend `ports` to `expose`:

```yaml
  frontend:
    expose:
      - "80"  # Only accessible within Docker network, Caddy forwards to it
```

Restart:

```bash
cd /opt/sipsense
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build
```

Caddy automatically gets an SSL certificate from Let's Encrypt. Visit
`https://yourdomain.com` — you should see the lock icon!

### Option B: Certbot + Nginx (more traditional)

If you'd rather use the traditional approach with certbot, install it on the
**host** (not in Docker):

```bash
apt install -y certbot python3-certbot-nginx
```

This approach is more complex because you need to put nginx on the host instead
of in Docker. The Caddy approach above is much simpler for beginners.

---

## Step 10: Import Your Whiskey Data

Right now your production database is empty. You need to get your whiskey data
in there.

### Option A: Copy your local SQLite database and convert it

This is the easiest if you already have whiskey data in your local `sipsense.db`.

**On your Mac:**

```bash
# Copy your local database to the server
scp ~/repos/sipsense/backend/sipsense.db root@167.99.123.45:/opt/sipsense/backend/
```

**On your server:**

```bash
cd /opt/sipsense

# Open a shell inside the backend container
docker compose -f docker-compose.yml -f docker-compose.production.yml exec backend bash

# Inside the container, you can run a Python script to migrate data
# from SQLite to PostgreSQL
python3 -c "
from app.database import engine, Base
from app import models
# Create all tables
Base.metadata.create_all(bind=engine)
print('Tables created successfully!')
"
```

Then you'll need to write a migration script to copy data from the SQLite file
to PostgreSQL. Here's a basic approach:

```bash
# Install sqlite3 tools in the container
apt-get update && apt-get install -y sqlite3

# Export data from SQLite as SQL INSERT statements
sqlite3 /opt/sipsense/backend/sipsense.db .dump > /tmp/sqlite_dump.sql

# Exit the container
exit
```

A cleaner approach is to use a Python script — we can set that up separately.

### Option B: Run your scrapers in production

```bash
cd /opt/sipsense

# Open a shell in the backend container
docker compose -f docker-compose.yml -f docker-compose.production.yml exec backend bash

# Run scrapers (this takes a while)
cd /opt/sipsense/backend
python3 -m scraper.run
```

---

## Keeping It Running

### Your app auto-restarts

Docker Compose is configured with `restart: unless-stopped`, which means:
- If a container crashes, Docker restarts it automatically
- If the server reboots, Docker starts your containers again
- The only way it stops is if you explicitly tell it to

### Useful commands (run these on your server)

```bash
cd /opt/sipsense

# See what's running
docker compose -f docker-compose.yml -f docker-compose.production.yml ps

# View logs (last 100 lines)
docker compose -f docker-compose.yml -f docker-compose.production.yml logs --tail=100

# View logs for just the backend
docker compose -f docker-compose.yml -f docker-compose.production.yml logs backend --tail=100

# Follow logs in real-time (Ctrl+C to stop)
docker compose -f docker-compose.yml -f docker-compose.production.yml logs -f

# Stop everything
docker compose -f docker-compose.yml -f docker-compose.production.yml down

# Restart everything
docker compose -f docker-compose.yml -f docker-compose.production.yml restart

# Restart just the backend
docker compose -f docker-compose.yml -f docker-compose.production.yml restart backend
```

### Tip: Make a shortcut alias

Those compose commands are really long. Add this to your server's shell config:

```bash
echo 'alias sipsense="docker compose -f /opt/sipsense/docker-compose.yml -f /opt/sipsense/docker-compose.production.yml"' >> ~/.bashrc
source ~/.bashrc
```

Now you can just type:

```bash
cd /opt/sipsense
sipsense ps
sipsense logs --tail=50
sipsense restart backend
```

---

## Updating the App

When you make changes to your code and want to deploy them:

### On your Mac:

```bash
cd ~/repos/sipsense
git add -A
git commit -m "describe your changes"
git push origin main
```

### On your server:

```bash
cd /opt/sipsense

# Pull the latest code
git pull origin main

# Rebuild and restart (only rebuilds containers that changed)
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build
```

The `--build` flag tells Docker to rebuild only the containers whose files
changed. This is usually faster than the initial build (2-5 minutes).

Your database data is safe — it lives in a Docker volume that persists across
rebuilds.

---

## Costs Breakdown

| Item | Cost | Notes |
|------|------|-------|
| Server (DigitalOcean 2GB) | $12/mo | Or $6/mo for 1GB + swap |
| Domain name | $10-15/yr | Optional, ~$1/mo |
| SSL certificate | Free | Via Caddy/Let's Encrypt |
| Anthropic API | Pay-per-use | Free tier available; ~$5-20/mo with moderate use |
| **Total** | **~$13-28/mo** | |

### Cheaper alternatives

- **Hetzner** 2GB server: ~$4.50/mo (cheapest reliable option)
- **Oracle Cloud** free tier: $0/mo (always-free ARM instance with 24GB RAM — great but setup is more complex)
- **Fly.io** or **Railway**: Pay-per-use, can be cheaper for low-traffic apps

---

## Troubleshooting

### "I can't connect to my server IP in the browser"

Check that port 80 is open in your server's firewall:

```bash
# On the server
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 22/tcp    # Don't lock yourself out of SSH!
ufw enable
```

On DigitalOcean, also check: Networking → Firewalls → make sure ports 80, 443,
and 22 are allowed.

### "Container keeps restarting"

Check the logs to see what's wrong:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml logs backend --tail=50
```

Common issues:
- **"ModuleNotFoundError"** — A Python package is missing. Check `requirements.txt`
- **"connection refused" to database** — The `db` container isn't ready yet. Wait
  30 seconds and check again
- **"out of memory"** — Your server needs more RAM or swap space

### "Frontend loads but API calls fail"

This usually means the backend isn't running or nginx can't reach it:

```bash
# Check if backend is actually running
docker compose -f docker-compose.yml -f docker-compose.production.yml ps

# Test the backend directly
docker compose -f docker-compose.yml -f docker-compose.production.yml exec frontend \
  curl http://backend:8000/
```

### "I need to look at the database"

```bash
# Open a PostgreSQL shell
docker compose -f docker-compose.yml -f docker-compose.production.yml exec db \
  psql -U sipsense -d sipsense

# Inside psql:
\dt                    -- list all tables
SELECT count(*) FROM whiskeys;  -- count whiskeys
\q                     -- quit
```

### "I messed up and want to start fresh"

```bash
cd /opt/sipsense

# Stop everything and DELETE all data (database, uploads, everything)
docker compose -f docker-compose.yml -f docker-compose.production.yml down -v

# Start fresh
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build
```

**Warning:** The `-v` flag deletes all volumes (your database data). Only do
this if you really want to start over.

### "My .env changes aren't taking effect"

Docker Compose reads `.env` files when it starts. You need to restart:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml down
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d
```

---

## Quick Reference Card

```
┌──────────────────────────────────────────────────────┐
│  SipSense Deployment Cheat Sheet                     │
├──────────────────────────────────────────────────────┤
│                                                      │
│  SSH in:     ssh root@YOUR_IP                        │
│  Go to app:  cd /opt/sipsense                        │
│                                                      │
│  Start:      docker compose -f docker-compose.yml \  │
│                -f docker-compose.production.yml \    │
│                up -d --build                         │
│                                                      │
│  Stop:       docker compose ... down                 │
│  Logs:       docker compose ... logs --tail=100      │
│  Status:     docker compose ... ps                   │
│  Update:     git pull && docker compose ... up -d \  │
│                --build                               │
│                                                      │
│  DB shell:   docker compose ... exec db \            │
│                psql -U sipsense -d sipsense          │
│                                                      │
│  Backend shell:                                      │
│              docker compose ... exec backend bash    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

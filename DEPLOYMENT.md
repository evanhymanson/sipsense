# SipSense Deployment Guide (AWS)

A step-by-step guide to deploy SipSense on AWS from scratch.
Written for beginners — no prior AWS or deployment experience needed.

---

## Table of Contents

1. [Overview — How the App Works](#1-overview--how-the-app-works)
2. [Prerequisites — What You Need](#2-prerequisites--what-you-need)
3. [Step 1: Create an AWS Account](#3-step-1-create-an-aws-account)
4. [Step 2: Launch an EC2 Instance](#4-step-2-launch-an-ec2-instance)
5. [Step 3: Connect to Your Server via SSH](#5-step-3-connect-to-your-server-via-ssh)
6. [Step 4: Install Docker on the Server](#6-step-4-install-docker-on-the-server)
7. [Step 5: Get Your Code on the Server](#7-step-5-get-your-code-on-the-server)
8. [Step 6: Configure Environment Variables](#8-step-6-configure-environment-variables)
9. [Step 7: Launch the App](#9-step-7-launch-the-app)
10. [Step 8: Verify Everything Works](#10-step-8-verify-everything-works)
11. [Step 9: Add a Domain Name](#11-step-9-add-a-domain-name)
12. [Step 10: Add HTTPS (SSL)](#12-step-10-add-https-ssl)
13. [Step 11: Set Up Auto-Deploy (CI/CD)](#13-step-11-set-up-auto-deploy-cicd)
14. [Common Tasks Cheat Sheet](#14-common-tasks-cheat-sheet)
15. [Troubleshooting](#15-troubleshooting)
16. [AWS Cost Breakdown](#16-aws-cost-breakdown)

---

## 1. Overview — How the App Works

SipSense has 3 parts that all run together on one server:

```
    Users (browser)
         │
         ▼
┌─────────────────┐
│    Frontend      │  ← React app served by nginx (port 80)
│    (nginx)       │
│        │         │
│        ▼         │
│    Backend       │  ← FastAPI Python server (port 8000)
│    (gunicorn)    │
│        │         │
│        ▼         │
│    Database      │  ← PostgreSQL (port 5432)
│    (postgres)    │
└─────────────────┘
     EC2 Instance
```

- **Frontend**: React app built by Vite, served by nginx. What users see in their browser.
- **Backend**: FastAPI Python server. Handles API calls, ML recommendations, Claude AI chat.
- **Database**: PostgreSQL stores all whiskey data, user accounts, reviews, etc.

Docker runs all 3 as separate "containers" on one EC2 instance.

---

## 2. Prerequisites — What You Need

Before you start, make sure you have:

- [ ] A **credit card** (AWS requires one, but the free tier means you won't be charged much)
- [ ] An **Anthropic API key** for Claude AI chat features — get one at [console.anthropic.com](https://console.anthropic.com)
- [ ] **Git** installed on your Mac (you already have it — type `git --version` in Terminal to confirm)
- [ ] Your SipSense code pushed to **GitHub** (public or private repo)

---

## 3. Step 1: Create an AWS Account

If you already have an AWS account, skip to Step 2.

1. Go to [aws.amazon.com](https://aws.amazon.com)
2. Click **Create an AWS Account** (top right)
3. Enter your email, set a password, choose an account name
4. Enter your credit card info (you get **12 months of free tier**)
5. Choose the **Basic (Free)** support plan
6. Sign in to the **AWS Management Console**

> **What is AWS Free Tier?** You get a `t2.micro` instance (1 GB RAM) free for 12 months.
> However, SipSense uses PyTorch which needs more memory, so we'll use a `t3.small`
> (2 GB RAM) which costs ~$15/month. If you want to save money and stay on free tier,
> you can use `t2.micro` with swap space (explained below).

---

## 4. Step 2: Launch an EC2 Instance

EC2 = "Elastic Compute Cloud" = a virtual server in the cloud. Here's how to create one:

### 4a. Go to EC2

1. In the AWS Console, search for **EC2** in the top search bar
2. Click **EC2** to open the EC2 Dashboard
3. Click the orange **Launch instance** button

### 4b. Configure your instance

Fill in each section:

**Name:**
```
SipSense-Server
```

**Application and OS Images (AMI):**
1. Click **Ubuntu**
2. Select **Ubuntu Server 24.04 LTS (Free tier eligible)**
3. Architecture: **64-bit (x86)**

**Instance type:**
- Pick **t3.small** (2 GB RAM, 2 vCPUs) — ~$15/month
- Or pick **t2.micro** (1 GB RAM, free tier) if you want to save money

> If you use `t2.micro`, you'll add swap space later so PyTorch doesn't crash.

**Key pair (login):**
This is how you'll SSH into your server.

1. Click **Create new key pair**
2. Name it: `sipsense-key`
3. Key pair type: **RSA**
4. Private key file format: **.pem**
5. Click **Create key pair**
6. A file called `sipsense-key.pem` will download — **keep this safe, you can't download it again!**

Now move the key to a safe place on your Mac:

```bash
# Run this in your Mac terminal
mv ~/Downloads/sipsense-key.pem ~/.ssh/sipsense-key.pem
chmod 400 ~/.ssh/sipsense-key.pem
```

**Network settings:**
Click **Edit** and configure the security group (firewall rules):

| Type | Port | Source | Why |
|------|------|--------|-----|
| SSH | 22 | My IP | So you can connect to the server |
| HTTP | 80 | Anywhere (0.0.0.0/0) | So users can visit your site |
| HTTPS | 443 | Anywhere (0.0.0.0/0) | For SSL (later) |

> "My IP" means only YOUR computer can SSH in. More secure than "Anywhere".

**Configure storage:**
- Change from 8 GB to **20 GB** (gp3)
- Docker images + PyTorch + database need space

### 4c. Launch it

1. Click **Launch instance**
2. Click **View all instances**
3. Wait for the **Instance state** to say **Running** (takes ~30 seconds)
4. Click on your instance to see its details
5. Copy the **Public IPv4 address** (e.g. `54.123.xxx.xxx`) — you'll need this!

> **Save this IP address somewhere.** You'll use it many times.

---

## 5. Step 3: Connect to Your Server via SSH

Open Terminal on your Mac and run:

```bash
ssh -i ~/.ssh/sipsense-key.pem ubuntu@YOUR_SERVER_IP
```

Replace `YOUR_SERVER_IP` with the IP you copied (e.g. `54.123.xxx.xxx`).

- Type `yes` when it asks about the fingerprint
- You're now logged into your server! You should see a prompt like: `ubuntu@ip-172-31-xx-xx:~$`

> **If it says "Permission denied"**: Make sure you ran `chmod 400 ~/.ssh/sipsense-key.pem`
>
> **If it times out**: Go back to EC2 > Security Groups and make sure port 22 is open to your IP.

### Make an alias (optional, but convenient)

Add this to your Mac's `~/.zshrc` so you can just type `ssh sipsense`:

```bash
echo 'alias ssh-sipsense="ssh -i ~/.ssh/sipsense-key.pem ubuntu@YOUR_SERVER_IP"' >> ~/.zshrc
source ~/.zshrc
```

---

## 6. Step 4: Install Docker on the Server

Run these commands on the server (you should already be SSH'd in):

```bash
# Update the system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Let the ubuntu user run Docker without sudo
sudo usermod -aG docker ubuntu

# Install Docker Compose plugin
sudo apt-get install -y docker-compose-plugin

# IMPORTANT: Log out and back in so the group change takes effect
exit
```

Now SSH back in:

```bash
ssh -i ~/.ssh/sipsense-key.pem ubuntu@YOUR_SERVER_IP
```

Verify Docker works:

```bash
docker --version
# Should print something like: Docker version 27.x.x

docker compose version
# Should print something like: Docker Compose version v2.x.x
```

### Add swap space (important if using t2.micro)

If your instance has less than 2 GB RAM, add swap to prevent out-of-memory crashes:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Verify:

```bash
free -h
# Should show "Swap: 2.0G" in the output
```

---

## 7. Step 5: Get Your Code on the Server

### Option A: Public GitHub repo

```bash
git clone https://github.com/YOUR_USERNAME/sipsense.git /opt/sipsense
```

### Option B: Private GitHub repo

You need to create a deploy key:

```bash
# Generate a key ON THE SERVER
ssh-keygen -t ed25519 -C "sipsense-deploy" -f ~/.ssh/deploy_key -N ""

# Print the public key
cat ~/.ssh/deploy_key.pub
```

Copy the output, then:

1. Go to your GitHub repo > **Settings** > **Deploy keys**
2. Click **Add deploy key**
3. Title: `SipSense EC2`
4. Paste the public key
5. Click **Add key**

Now clone:

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/deploy_key" git clone git@github.com:YOUR_USERNAME/sipsense.git /opt/sipsense
```

### Set ownership

```bash
sudo chown -R ubuntu:ubuntu /opt/sipsense
cd /opt/sipsense
```

---

## 8. Step 6: Configure Environment Variables

```bash
cd /opt/sipsense

# Copy the example env file
cp .env.example .env

# Edit it
nano .env
```

Fill in each value:

```env
# Database password — make this long and random
# Generate one: openssl rand -base64 24
POSTGRES_PASSWORD=PASTE_A_RANDOM_PASSWORD_HERE

# JWT secret for user authentication
# Generate one: python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=PASTE_A_RANDOM_STRING_HERE

# Claude AI API key (from https://console.anthropic.com/settings/keys)
ANTHROPIC_API_KEY=sk-ant-api03-your-real-key-here

# Your domain or server IP
CORS_ORIGINS=http://YOUR_SERVER_IP
```

**How to save in nano:**
1. Press `Ctrl + X`
2. Press `Y` (yes, save)
3. Press `Enter` (confirm filename)

> **Security tip:** Never commit your `.env` file to GitHub. It's already in `.gitignore`.

---

## 9. Step 7: Launch the App

```bash
cd /opt/sipsense

# Build and start all containers in the background
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build
```

**What happens:**
1. Docker downloads base images (Python, Node, PostgreSQL, nginx)
2. Installs Python packages including PyTorch (CPU version)
3. Builds the React frontend
4. Starts PostgreSQL, then the backend, then the frontend

**This takes 5-15 minutes the first time.** Subsequent rebuilds are much faster because
Docker caches layers.

Watch the build progress:

```bash
# Watch all logs in real time
docker compose logs -f

# Or watch just one service
docker compose logs backend -f

# Press Ctrl+C to stop watching (the app keeps running)
```

---

## 10. Step 8: Verify Everything Works

### Check containers are running

```bash
docker compose ps
```

You should see 3 services all with status **running**:

```
NAME                    STATUS
sipsense-db-1          running (healthy)
sipsense-backend-1     running
sipsense-frontend-1    running
```

### Test the API

```bash
curl http://localhost/api/whiskeys/?limit=1
```

You should get a JSON response with whiskey data.

### Test in your browser

Open your browser and go to:

```
http://YOUR_SERVER_IP
```

You should see the SipSense app!

> **If it doesn't load:** Check the [Troubleshooting](#15-troubleshooting) section below.

### Import whiskey data (if needed)

If you have an existing SQLite database locally with your whiskey data:

```bash
# Run this on YOUR MAC (not the server)
scp -i ~/.ssh/sipsense-key.pem backend/sipsense.db ubuntu@YOUR_SERVER_IP:/opt/sipsense/backend/

# Then on the server, run your scrapers to populate PostgreSQL
cd /opt/sipsense
docker compose exec backend python -m scraper.run
```

---

## 11. Step 9: Add a Domain Name

Instead of `http://54.123.xxx.xxx`, get a real domain like `sipsense.com`.

### 11a. Buy a domain

Cheapest options:
- [Namecheap](https://namecheap.com) — domains from ~$9/year
- [Cloudflare Registrar](https://cloudflare.com) — at-cost pricing
- [AWS Route 53](https://aws.amazon.com/route53/) — $12/year for `.com` (keeps everything in AWS)

### 11b. Option 1 — Using Route 53 (all inside AWS)

1. In the AWS Console, search for **Route 53**
2. Click **Hosted zones** > **Create hosted zone**
3. Domain name: `yourdomain.com`
4. Type: **Public hosted zone**
5. Click **Create hosted zone**
6. Route 53 gives you 4 **nameservers** (NS records) — they look like: `ns-123.awsdns-45.com`
7. Go to your domain registrar and **replace the nameservers** with the Route 53 ones
8. Back in Route 53, click **Create record**:
   - Record name: (leave blank for root domain)
   - Record type: **A**
   - Value: `YOUR_SERVER_IP`
   - TTL: 300
   - Click **Create records**
9. Create another record for `www`:
   - Record name: `www`
   - Record type: **A**
   - Value: `YOUR_SERVER_IP`
   - TTL: 300

### 11b. Option 2 — Using Namecheap/Cloudflare (simpler)

In your registrar's DNS settings, add:

| Type | Host | Value | TTL |
|------|------|-------|-----|
| A    | @    | YOUR_SERVER_IP | 300 (5 min) |
| A    | www  | YOUR_SERVER_IP | 300 (5 min) |

### 11c. Wait for DNS propagation

DNS changes take 5-30 minutes (sometimes up to 48 hours). Check if it's working:

```bash
# Run on your Mac
nslookup yourdomain.com
# Should show your server's IP address
```

### 11d. Update your environment

```bash
# On the server
cd /opt/sipsense
nano .env

# Change this line:
CORS_ORIGINS=https://yourdomain.com
```

Restart:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d
```

---

## 12. Step 10: Add HTTPS (SSL)

HTTPS encrypts traffic and shows the padlock icon. Required for production apps.
Free with Let's Encrypt.

### Install Caddy as a reverse proxy

Caddy automatically gets and renews SSL certificates — no configuration needed.

```bash
# Install Caddy on the EC2 host (NOT inside Docker)
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update
sudo apt-get install caddy
```

### Configure Caddy

```bash
sudo tee /etc/caddy/Caddyfile << 'EOF'
yourdomain.com {
    reverse_proxy localhost:80
}

www.yourdomain.com {
    redir https://yourdomain.com{uri} permanent
}
EOF
```

Replace `yourdomain.com` with your actual domain.

### Update Docker to avoid port conflict

Since Caddy needs port 80/443, update the production compose to use a different port.
Create a file `docker-compose.ssl.yml`:

```bash
cat > /opt/sipsense/docker-compose.ssl.yml << 'EOF'
services:
  frontend:
    ports:
      - "8080:80"
EOF
```

Then restart everything:

```bash
cd /opt/sipsense

# Use the SSL override instead of production (which uses port 80)
docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d

# Start Caddy
sudo systemctl restart caddy
```

### Verify HTTPS

Open `https://yourdomain.com` in your browser. You should see the padlock icon.

Caddy automatically renews certificates before they expire — no cron jobs needed.

---

## 13. Step 11: Set Up Auto-Deploy (CI/CD)

Your repo already has GitHub Actions workflows. When you push code to `main`,
it automatically deploys to your server.

### 13a. Add GitHub Secrets

1. Go to your GitHub repo
2. Click **Settings** > **Secrets and variables** > **Actions**
3. Click **New repository secret** for each:

| Secret Name | What to put |
|---|---|
| `STAGING_HOST` | Your server's public IP (e.g. `54.123.xxx.xxx`) |
| `STAGING_SSH_KEY` | Contents of `~/.ssh/sipsense-key.pem` (the whole file including BEGIN/END lines) |
| `PRODUCTION_HOST` | Same IP (or a separate production server later) |
| `PRODUCTION_SSH_KEY` | Same key contents |

To copy your key contents:

```bash
# On your Mac
cat ~/.ssh/sipsense-key.pem | pbcopy
# Now it's on your clipboard — paste into GitHub
```

### 13b. Prepare the server

Make sure GitHub Actions can deploy:

```bash
# On the server
sudo chown -R ubuntu:ubuntu /opt/sipsense
```

### 13c. How the pipeline works

```
You push code to main on GitHub
         │
         ▼
┌─────────────────────────────┐
│  CI: Run tests              │  ← Runs pytest + npm build
│  (.github/workflows/ci.yml) │
└─────────────┬───────────────┘
              │ tests pass
              ▼
┌─────────────────────────────┐
│  Auto-deploy to STAGING     │  ← Runs on port 8080
│  (deploy.yml)               │
└─────────────┬───────────────┘
              │ manual trigger
              ▼
┌─────────────────────────────┐
│  Deploy to PRODUCTION       │  ← Backs up DB first, then deploys
│  (deploy.yml)               │
└─────────────────────────────┘
```

**Staging** deploys automatically on every push to `main`.
**Production** requires you to manually trigger it:

1. Go to GitHub > **Actions** tab
2. Click the **Deploy** workflow on the left
3. Click **Run workflow** (top right)
4. Select **production** from the dropdown
5. Click the green **Run workflow** button

### 13d. Test the pipeline

```bash
# On your Mac — make a small change and push
cd ~/repos/sipsense
echo "# test" >> README.md
git add README.md
git commit -m "test: verify CI/CD pipeline"
git push origin main
```

Go to GitHub > **Actions** and watch it run.

---

## 14. Common Tasks Cheat Sheet

### Connecting to your server

```bash
ssh -i ~/.ssh/sipsense-key.pem ubuntu@YOUR_SERVER_IP
```

### Docker commands (run these on the server)

| Task | Command |
|---|---|
| Start everything | `docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build` |
| Stop everything | `docker compose down` |
| Restart everything | `docker compose restart` |
| View all logs | `docker compose logs -f` |
| View backend logs | `docker compose logs backend -f --tail 100` |
| View frontend logs | `docker compose logs frontend -f --tail 100` |
| Check status | `docker compose ps` |
| Open database shell | `docker compose exec db psql -U sipsense sipsense` |
| Run backend command | `docker compose exec backend python -c "print('hello')"` |
| Rebuild one service | `docker compose up -d --build backend` |
| Clean up disk space | `docker system prune -a` |

### Deploying new code manually

```bash
# On the server
cd /opt/sipsense
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build
```

### Backing up the database

```bash
# Create backup
docker compose exec db pg_dump -U sipsense sipsense > ~/backup_$(date +%Y%m%d).sql

# Restore from backup
cat ~/backup_20260314.sql | docker compose exec -T db psql -U sipsense sipsense
```

### Checking server health

```bash
# Memory
free -h

# Disk space
df -h

# CPU / processes
htop   # install with: sudo apt install htop

# Docker disk usage
docker system df
```

---

## 15. Troubleshooting

### "Connection refused" when visiting the IP in browser

**Cause:** The security group doesn't allow HTTP traffic.

**Fix:**
1. Go to AWS Console > EC2 > your instance
2. Click the **Security** tab
3. Click on the security group link
4. **Edit inbound rules**
5. Add: Type = **HTTP**, Port = **80**, Source = **Anywhere (0.0.0.0/0)**
6. Add: Type = **HTTPS**, Port = **443**, Source = **Anywhere (0.0.0.0/0)**
7. Click **Save rules**

### "Permission denied (publickey)" when SSH-ing

```bash
# Make sure the key has correct permissions
chmod 400 ~/.ssh/sipsense-key.pem

# Make sure you're using the right username (ubuntu, NOT root)
ssh -i ~/.ssh/sipsense-key.pem ubuntu@YOUR_SERVER_IP
```

### Container keeps restarting

```bash
# Check what's wrong
docker compose logs backend --tail 50

# Common causes:
# - Missing environment variable → check .env file
# - Database not ready yet → wait a minute and try again
# - Port conflict → another service on the same port
```

### Out of memory (OOM killed)

PyTorch uses a lot of memory. Signs: the backend container keeps restarting,
or `dmesg | grep oom` shows OOM messages.

```bash
# Check current memory
free -h

# Add 2GB swap if you haven't already
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Or upgrade your EC2 instance:
# 1. Stop the instance in AWS Console
# 2. Actions > Instance settings > Change instance type
# 3. Select t3.small (2GB) or t3.medium (4GB)
# 4. Start the instance
# Note: The public IP may change! Use an Elastic IP to prevent this.
```

### Public IP changed after stopping/starting instance

AWS gives you a new IP each time you stop/start an EC2 instance.

**Fix: Use an Elastic IP (free while attached to a running instance)**

1. AWS Console > EC2 > **Elastic IPs**
2. Click **Allocate Elastic IP address**
3. Click **Allocate**
4. Select the new Elastic IP > **Actions** > **Associate Elastic IP address**
5. Choose your instance
6. Click **Associate**

Now your IP never changes, even if you stop/start the instance.

> An Elastic IP is **free** while attached to a running instance. You're charged
> ~$4/month if the instance is stopped, so release it if you're not using it.

### Frontend loads but API calls fail

1. Check backend is running: `docker compose ps`
2. Check backend logs: `docker compose logs backend --tail 50`
3. Test API directly: `curl http://localhost:8000/api/whiskeys/?limit=1`
4. Check nginx proxy config: `docker compose logs frontend --tail 50`
5. Make sure `.env` exists and has all values filled in

### "Cannot connect to the Docker daemon"

```bash
sudo systemctl start docker
sudo systemctl enable docker
```

### Disk space full

```bash
# Check what's using space
df -h
du -sh /var/lib/docker

# Clean up unused Docker data
docker system prune -a

# Remove old logs
sudo journalctl --vacuum-time=7d
```

---

## 16. AWS Cost Breakdown

### Monthly cost estimate

| Resource | Free Tier? | Cost after Free Tier |
|---|---|---|
| EC2 t2.micro (1 GB RAM) | Free for 12 months | ~$8/month |
| EC2 t3.small (2 GB RAM) | Not free tier | ~$15/month |
| EBS 20 GB storage | 30 GB free for 12 months | ~$2/month |
| Elastic IP (attached) | Free | Free |
| Data transfer (first 100 GB) | Free | Free |
| Route 53 domain | N/A | $0.50/month + $12/year for domain |
| **Total (free tier t2.micro)** | | **~$0-2/month** for first year |
| **Total (t3.small)** | | **~$17/month** |

### Money-saving tips

1. **Use t2.micro + swap** for development/low traffic — free for 12 months
2. **Reserve an instance** — pay upfront for 1 year and save ~30%
3. **Stop the instance** when not using it — you only pay for storage (~$2/month)
4. **Use Spot Instances** for non-production — up to 90% cheaper (but can be interrupted)
5. **Set a billing alarm** so you don't get surprised:
   - AWS Console > **Billing** > **Budgets** > **Create budget**
   - Set a monthly budget of $20 and get email alerts at 80%

---

## Summary: The Minimum Steps

If you want the absolute shortest path from zero to deployed:

```bash
# 1. Launch a t3.small EC2 with Ubuntu 24.04
#    (open ports 22, 80, 443 in security group)

# 2. SSH in
ssh -i ~/.ssh/sipsense-key.pem ubuntu@YOUR_IP

# 3. Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
sudo apt-get install -y docker-compose-plugin
exit  # log out and back in

# 4. SSH back in, clone and configure
ssh -i ~/.ssh/sipsense-key.pem ubuntu@YOUR_IP
git clone https://github.com/YOUR_USER/sipsense.git /opt/sipsense
cd /opt/sipsense
cp .env.example .env
nano .env  # fill in POSTGRES_PASSWORD, JWT_SECRET_KEY, ANTHROPIC_API_KEY

# 5. Launch
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build

# 6. Visit http://YOUR_IP in your browser!
```

That's it. Everything else (domain, HTTPS, CI/CD) is optional and can be added later.

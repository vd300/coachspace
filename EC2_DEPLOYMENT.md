# EC2 Deployment

This project can run on one EC2 instance with Docker. Keep it to one instance while it uses SQLite. Before scaling horizontally, move the database to RDS Postgres and store uploaded media in S3.

## 1. Launch The Instance

Use an Amazon Linux EC2 instance.

Suggested starter settings:

- Instance type: `t3.small`
- Storage: 20 GB or more
- Security group inbound rules:
  - SSH `22` from your IP only
  - HTTP `80` from `0.0.0.0/0`
  - HTTPS `443` from `0.0.0.0/0` when you add TLS

## 2. Install Docker

SSH into the instance and run:

```bash
sudo yum update -y
sudo yum install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
```

Log out and SSH back in so the Docker group takes effect.

## 3. Copy The Project To EC2

From your local machine, create a clean archive that does not include `.venv`, databases, uploads, or the bundled AWS CLI files:

```bash
tar --exclude='.venv' --exclude='data' --exclude='uploads/*' --exclude='aws' --exclude='awscliv2.zip' --exclude='coachspace.zip' -czf coachspace.tar.gz .
scp -i your-key.pem coachspace.tar.gz ec2-user@YOUR_EC2_PUBLIC_IP:/home/ec2-user/
```

On EC2:

```bash
mkdir -p ~/coachspace
tar -xzf ~/coachspace.tar.gz -C ~/coachspace
cd ~/coachspace
cp .env.ec2.example .env.ec2
```

Edit `.env.ec2` and set a real `APP_SECRET`.

Generate one with:

```bash
openssl rand -hex 32
```

## 4. Run The App

```bash
docker build -t coachspace .
docker volume create coachspace-data
docker volume create coachspace-uploads
docker rm -f coachspace 2>/dev/null || true
docker run -d \
  --name coachspace \
  --restart unless-stopped \
  -p 80:8000 \
  --env-file .env.ec2 \
  -v coachspace-data:/app/data \
  -v coachspace-uploads:/app/uploads \
  coachspace
```

Check it:

```bash
docker ps
curl http://localhost/health
```

Then open:

```text
http://YOUR_EC2_PUBLIC_IP
```

## 5. Update The App

Copy a fresh archive to EC2, extract it over `~/coachspace`, then run:

```bash
cd ~/coachspace
docker build -t coachspace .
docker rm -f coachspace
docker run -d \
  --name coachspace \
  --restart unless-stopped \
  -p 80:8000 \
  --env-file .env.ec2 \
  -v coachspace-data:/app/data \
  -v coachspace-uploads:/app/uploads \
  coachspace
```

The SQLite database and local uploads are stored in Docker volumes named `coachspace-data` and `coachspace-uploads`, so they survive container rebuilds.

## 6. Production Notes

- Set `APP_SECRET` before exposing the app publicly.
- Use S3 for uploaded videos/audio/PDFs before real users rely on the app.
- Add a domain and HTTPS with Nginx plus Let's Encrypt, or put an AWS Application Load Balancer in front of the instance.
- Keep only one EC2 instance until SQLite is replaced by RDS Postgres.

## Move Uploads To S3

The app already supports direct browser uploads to S3. Keep the bucket private; the API will create presigned upload and playback URLs.

1. Create an S3 bucket, for example:

```text
coachspace-prod-media-yourname
```

Use the same AWS region as your EC2 instance when possible. Keep **Block all public access** enabled.

2. Add this CORS configuration to the S3 bucket:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["POST", "GET", "HEAD"],
    "AllowedOrigins": ["http://YOUR_EC2_PUBLIC_IP"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

For the current test EC2 URL, use:

```json
"AllowedOrigins": ["http://34.201.17.50"]
```

When you add a domain and HTTPS, replace this with the domain origin, for example `https://app.example.com`.

3. Create an IAM role for EC2 and attach this policy. Replace the bucket name:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::coachspace-prod-media-yourname/*"
    }
  ]
}
```

Attach the role to the running EC2 instance:

```text
EC2 -> Instances -> select instance -> Actions -> Security -> Modify IAM role
```

4. Update `.env.ec2` on EC2:

```bash
cd ~/coachspace
nano .env.ec2
```

Set:

```env
STORAGE_BACKEND=s3
S3_BUCKET_NAME=coachspace-prod-media-yourname
AWS_REGION=us-east-1
CORS_ORIGINS=http://34.201.17.50
```

Use your actual bucket name and region.

5. Restart the container:

```bash
docker rm -f coachspace
docker run -d \
  --name coachspace \
  --restart unless-stopped \
  -p 80:8000 \
  --env-file .env.ec2 \
  -v coachspace-data:/app/data \
  -v coachspace-uploads:/app/uploads \
  coachspace
```

6. Test as a teacher by uploading a new video, audio file, or PDF. New uploads should appear under the bucket prefix:

```text
media/<teacher_user_id>/
```

Existing local uploads stay in the old Docker volume. If you need them moved too, upload them separately to S3 and update the `media_items` rows in SQLite.

## Troubleshooting Public Access

If `curl http://localhost/health` works on EC2 but `http://YOUR_EC2_PUBLIC_IP` does not work from your browser, check these in order:

1. Confirm Docker is publishing port 80:

```bash
docker ps
sudo ss -lntp | grep ':80'
```

You should see a port mapping like `0.0.0.0:80->8000/tcp`.

2. Confirm the instance can reach its own public IP:

```bash
curl http://YOUR_EC2_PUBLIC_IP/health
```

3. In the EC2 security group, add an inbound rule:

```text
Type: HTTP
Protocol: TCP
Port: 80
Source: 0.0.0.0/0
```

For IPv6, also add `::/0`.

4. Confirm you are using the current public IPv4 address from the EC2 instance details page. Public IPs change after stop/start unless you attach an Elastic IP.

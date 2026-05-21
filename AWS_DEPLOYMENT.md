# AWS Deployment

This project can run on AWS as a Dockerized FastAPI app, with uploaded media stored in S3.

## Recommended AWS Shape

- **Compute:** Elastic Beanstalk Docker environment, or ECS/Fargate later.
- **Media storage:** S3 bucket for videos, audio, and PDFs.
- **Database:** SQLite is still used by the current app. Keep the first AWS deployment to one instance, then migrate to RDS Postgres before scaling horizontally.
- **CDN:** CloudFront in front of S3 when you want faster video delivery.

App Runner is not the best default for this project in 2026 because AWS documentation now shows an availability-change notice for new App Runner customers. Elastic Beanstalk or ECS/Fargate are safer AWS choices.

## S3 Bucket

Create a private S3 bucket, for example:

```text
coachspace-prod-media
```

Add this CORS configuration to the bucket so the browser can upload directly to S3:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["POST", "GET", "HEAD"],
    "AllowedOrigins": ["https://your-domain.example"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

For local testing against S3, temporarily add:

```json
"http://127.0.0.1:8000"
```

to `AllowedOrigins`.

## IAM Permissions

The app runtime needs permission to upload, read, and verify objects in the media bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:HeadObject"],
      "Resource": "arn:aws:s3:::coachspace-prod-media/*"
    }
  ]
}
```

Attach this to the Elastic Beanstalk EC2 instance profile, ECS task role, or whichever runtime role runs the container.

## Environment Variables

Set these in the AWS service:

```text
APP_SECRET=<long-random-secret>
STORAGE_BACKEND=s3
S3_BUCKET_NAME=coachspace-prod-media
AWS_REGION=ap-south-1
CORS_ORIGINS=https://your-domain.example
```

Optional if you put CloudFront in front of S3:

```text
S3_PUBLIC_BASE_URL=https://your-cloudfront-domain.example
```

If `S3_PUBLIC_BASE_URL` is not set, the API returns temporary presigned S3 URLs for playback.

## Elastic Beanstalk Docker Deploy

The repo already includes a `Dockerfile`, so Elastic Beanstalk can build and run it.

1. Install and configure the AWS CLI and EB CLI.
2. From the project root, initialize Elastic Beanstalk:

```bash
eb init -p docker coachspace --region ap-south-1
```

3. Create a single-instance environment for the current SQLite-based app:

```bash
eb create coachspace-prod --single --instance-type t3.small
```

4. Set environment variables:

```bash
eb setenv APP_SECRET="<long-random-secret>" STORAGE_BACKEND=s3 S3_BUCKET_NAME=coachspace-prod-media AWS_REGION=ap-south-1 CORS_ORIGINS=https://your-domain.example
```

5. Deploy:

```bash
eb deploy
```

6. Check health:

```text
https://your-eb-url/health
```

## Important Scaling Note

S3 now handles the large uploaded files. The remaining scaling limit is the SQLite database. Before running multiple app instances, migrate the database layer to Postgres on Amazon RDS.

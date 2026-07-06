#!/usr/bin/env python
"""Effectue un pg_dump et l'upload vers le bucket S3 configuré."""
import os
import subprocess
import sys
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

def backup():
    # Récupération des variables d'environnement
    db_url = os.environ["DATABASE_URL"]
    aws_access_key = os.environ["DJANGO_AWS_ACCESS_KEY_ID"]
    aws_secret_key = os.environ["DJANGO_AWS_SECRET_ACCESS_KEY"]
    endpoint_url = os.environ["DJANGO_AWS_S3_ENDPOINT_URL"]
    region = os.environ.get("DJANGO_AWS_REGION_NAME", "eu-central-1")
    bucket_name = os.environ["DJANGO_AWS_STORAGE_BUCKET_NAME"]
    # On stockera les backups dans un dossier "backups/" du bucket
    backup_prefix = "backups"

    # Générer un nom de fichier horodaté
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dump_filename = f"backup_{timestamp}.sql"
    local_path = f"/tmp/{dump_filename}"

    print(f"[BACKUP] Dumping database to {local_path}...")
    # Extraire les informations de connexion depuis DATABASE_URL
    # Format : postgresql://user:password@host:port/dbname?sslmode=require
    # On utilise pg_dump en mode URI
    try:
        subprocess.run(
            ["pg_dump", "--no-owner", "--no-acl", "-Fc", "-f", local_path, db_url],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"[BACKUP] pg_dump failed: {e.stderr}")
        sys.exit(1)

    print("[BACKUP] Uploading to S3...")
    # Connexion à S3 (Supabase Storage)
    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        endpoint_url=endpoint_url,
        region_name=region,
    )

    s3_key = f"{backup_prefix}/{dump_filename}"
    try:
        s3.upload_file(local_path, bucket_name, s3_key)
        print(f"[BACKUP] Successfully uploaded to s3://{bucket_name}/{s3_key}")
    except ClientError as e:
        print(f"[BACKUP] Upload failed: {e}")
        sys.exit(1)
    finally:
        # Nettoyer le fichier temporaire
        os.remove(local_path)

if __name__ == "__main__":
    backup()
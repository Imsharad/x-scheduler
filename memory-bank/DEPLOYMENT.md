# X-Scheduler Deployment Documentation

This document keeps track of all deployments of the X-Scheduler application.

## Latest Deployment (May 2, 2025)

### AWS Instance Details
- **Instance ID**: i-0249b0f93a193f917
- **Instance Type**: t2.micro
- **Region**: us-east-1
- **Public IP**: 3.86.239.33
- **Key Pair File**: deploy/keys/x-scheduler-key-latest.pem

### Deployment Method
- **Docker Container** - Application is now containerized for better isolation and reliability
- **Automated Deployment Script** - Single command deployment using update-deploy.sh

### Access Information
- **SSH Command**: 
  ```bash
  ssh -i deploy/keys/x-scheduler-key-latest.pem ec2-user@3.86.239.33
  ```

### Monitoring Commands
- **View Docker Container Logs**:
  ```bash
  docker-compose logs -f
  ```
- **Check Container Status**:
  ```bash
  docker ps
  ```

### Docker Setup Process
1. Created Dockerfile and docker-compose.yml
2. Built and tested locally
3. Deployed to EC2 instance
4. Set up to automatically restart containers
5. Created automated update-deploy.sh script for seamless updates

### Automated Deployment Process

To update the application on the EC2 instance:

1. Make your code changes locally and push to the main branch on GitHub
2. Run the update script:
   ```bash
   ./update-deploy.sh
   ```
3. The script will:
   - Connect to the EC2 instance
   - Pull latest code from GitHub
   - Rebuild and restart the Docker containers
   - Show logs of the running application

### Important Files

- **Dockerfile**: Defines the container build process
- **docker-compose.yml**: Configures container runtime settings
- **update-deploy.sh**: Automates the deployment process
- **deploy/keys/**: Contains SSH keys for connecting to the instance
- **config/google-credentials.json**: Google API credentials (NOT in Git)

### Google Sheets Integration

The application now exclusively uses Google Sheets as its content source. When deploying, make sure:

1. The Google credentials file is present on the EC2 instance
2. The Sheet ID is correctly configured in the config file
3. The service account has access to the Google Sheet

To copy the Google credentials to the EC2 instance:

```bash
scp -i deploy/keys/x-scheduler-key-latest.pem config/google-credentials.json ec2-user@3.86.239.33:/home/ec2-user/x-scheduler/config/
```

### Troubleshooting

If deployment issues occur:

1. Check SSH connectivity:
   ```bash
   ssh -i deploy/keys/x-scheduler-key-latest.pem ec2-user@3.86.239.33
   ```

2. Verify Docker is running:
   ```bash
   sudo systemctl status docker
   ```

3. Verify container logs:
   ```bash
   docker-compose logs
   ```

4. Common issues:
   - Google credentials missing or incorrect
   - Permissions on the credentials file (should be 600)
   - Network connectivity to Google services
   - Docker container resource limits

### Rollback Process

If needed, you can roll back to a previous version:

1. SSH into the instance
2. Navigate to the app directory: `cd /home/ec2-user/x-scheduler`
3. Check out a specific commit: `git checkout <commit-hash>`
4. Rebuild containers: `docker-compose up -d --build`

## Previous Deployments

### Initial Deployment (May 1, 2024)
- **Instance ID**: i-0919722bc17abca2b
- **Instance Type**: t2.micro
- **Region**: us-east-1
- **Public IP**: 52.91.129.242
- **Key Pair File**: x-scheduler-key-1746083577.pem
- **Method**: systemd service

## Troubleshooting

### Docker Issues
```bash
# Check container status
docker ps -a

# View detailed logs
docker-compose logs

# Restart container
docker-compose restart

# Rebuild container after changes
docker-compose up -d --build
```

### SSH Connection Issues
- Ensure key file has correct permissions: `chmod 400 deploy/keys/x-scheduler-key-latest.pem`
- Verify security group allows SSH access from your IP

### If the service is not running
```bash
# Check status
sudo systemctl status x-scheduler.service

# View error logs
sudo journalctl -u x-scheduler.service -e

# Restart service
sudo systemctl restart x-scheduler.service
```

### If AWS credentials expire
Update AWS credentials in the AWS console and reconfigure using `aws configure` with the new credentials. 
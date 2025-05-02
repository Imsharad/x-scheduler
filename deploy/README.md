# X-Scheduler Deployment

This document contains information about deploying the X-Scheduler application to AWS.

## Latest Deployment Information

The most recent deployment was completed with the following details:

- **Instance ID**: i-0919722bc17abca2b
- **Instance Type**: t2.micro
- **Region**: us-east-1
- **Public IP**: 52.91.129.242
- **Key Pair File**: x-scheduler-key-1746083577.pem
- **Deployment Date**: May 1, 2024

## Access Information

### SSH Access
```bash
ssh -i x-scheduler-key-1746083577.pem ec2-user@52.91.129.242
```

### Monitoring

View system service logs:
```bash
journalctl -u x-scheduler.service -f
```

View application logs:
```bash
tail -f /home/ec2-user/x-scheduler/src/log/pipeline.log
```

## AWS Deployment Process

### Prerequisites

1. **AWS CLI**: Install and configure with administrator credentials
   ```
   pip install awscli
   aws configure
   ```
2. **jq**: Required for JSON parsing in the deployment script
   ```
   # MacOS
   brew install jq
   
   # Ubuntu/Debian
   sudo apt install jq
   
   # Amazon Linux/RHEL/CentOS
   sudo yum install jq
   ```
3. **Git Repository**: Ensure your code is in a Git repository that EC2 can access

### Deployment Steps

1. **Customize deployment configuration**:
   Edit the beginning of `deploy.sh` to set your AWS region, repository URL, and other parameters
   
2. **Run the deployment script**:
   ```bash
   ./deploy.sh
   ```
   
3. **What the script does**:
   - Creates IAM policy for SSM parameter access
   - Creates IAM role and instance profile for EC2
   - Sets up security group with SSH access
   - Securely stores X API credentials in SSM Parameter Store
   - Creates EC2 key pair for SSH access
   - Launches EC2 instance with the application
   - Sets up systemd service for automatic startup

## Updating the Deployed Application

To update the application after making code changes:

1. Push changes to your Git repository
2. SSH into the EC2 instance:
   ```bash
   ssh -i x-scheduler-key-1746083577.pem ec2-user@52.91.129.242
   ```
3. Update and restart the application:
   ```bash
   cd /home/ec2-user/x-scheduler
   git pull
   sudo systemctl restart x-scheduler.service
   ```

## Troubleshooting

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
Update AWS credentials in the AWS console and reconfigure using:
```bash
aws configure
```

## Deployment History

| Date | Instance ID | Public IP | Key Pair |
|------|-------------|-----------|----------|
| 05/01/2024 | i-0919722bc17abca2b | 52.91.129.242 | x-scheduler-key-1746083577.pem | 

## Deployment Learnings, Troubleshooting, and Future Notes

### Key Learnings
- **Security Groups:** Always ensure your EC2 security group allows SSH (port 22) from your current public IP in CIDR notation (e.g., `YOUR.IP.ADDRESS/32`).
- **Key File Location:** Store your SSH private keys in a secure, organized location (e.g., `deploy/keys/`) and use the correct path when connecting.
- **Multiple Instances:** Running `deploy.sh` multiple times will create new EC2 instances. Manually terminate unused instances to avoid extra costs.
- **.pem Permissions:** SSH key files must have permissions set to `chmod 400`.
- **IP Changes:** If your public IP changes, update the security group rule accordingly.
- **SSH Troubleshooting:** Use `ssh -v ...` for verbose output if you have connection issues.
- **Logs and Service Status:** After connecting, check service status with `sudo systemctl status x-scheduler.service` and logs with `tail -f /home/ec2-user/x-scheduler/src/log/pipeline.log`.

### Common Issues & Fixes
- **Operation timed out:** Usually means your security group does not allow SSH from your IP, or your instance is not running.
- **Key not accessible:** Double-check the path and permissions of your `.pem` file.
- **Multiple running instances:** Clean up unused EC2 instances in the AWS Console.
- **Wrong IP in security group:** Always use `/32` CIDR notation for single IPs.

### Future Notes
- Consider adding a healthcheck script to automate post-deployment validation.
- For updates, SSH into the instance and pull new code instead of re-running `deploy.sh`.
- For production, restrict SSH access to only trusted IPs and consider using a bastion host.
- Regularly rotate and securely store your SSH keys.
- Monitor AWS costs and terminate unused resources.
- Consider automating instance cleanup or adding prompts to `deploy.sh` to avoid accidental multiple deployments.

---

_This section is a living document. Add new learnings and troubleshooting tips as you continue to deploy and maintain X-Scheduler._ 
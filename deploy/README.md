# X-Scheduler Deployment

This document contains information about deploying the X-Scheduler application to AWS, including necessary infrastructure components and setup.

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

The deployment process utilizes a CloudFormation template (`deploy/aws/x-scheduler-stack.yaml`) managed via a shell script (`deploy/aws/deploy-aws.sh`).

### Prerequisites

1.  **AWS CLI**: Install and configure with appropriate permissions to create the resources defined in the CloudFormation template.
    ```bash
    pip install awscli
    aws configure
    ```
2.  **jq**: Required for JSON parsing in helper scripts. (Installation instructions as before)
3.  **Git Repository**: Ensure your code is in a Git repository accessible by CodeDeploy/EC2 or include the codebase in the deployment package.

### AWS Resources Created

The CloudFormation template (`deploy/aws/x-scheduler-stack.yaml`) provisions the following key resources:

1.  **EC2 Instance:**
    *   Runs the main scheduler application and the OAuth web server.
    *   Defaults to `t2.micro` but monitor performance, especially with video processing (`yt-dlp`) and consider upgrading if needed.
    *   Uses an Amazon Linux 2 AMI (or specified alternative).
    *   Launched within a specified VPC and Subnet.

2.  **IAM Role & Instance Profile:**
    *   Grants the EC2 instance necessary permissions to:
        *   Access SSM Parameter Store for secrets (API keys, OAuth credentials).
        *   Interact with the S3 bucket (GetObject, PutObject, DeleteObject).
        *   Interact with the DynamoDB table (PutItem, GetItem, UpdateItem, DeleteItem).
        *   (Optionally) Interact with other AWS services if needed (e.g., CloudWatch Logs).
    *   The specific policy is defined within the CloudFormation template or attached separately.

3.  **Security Group:**
    *   Allows inbound SSH (Port 22) from specified CIDR ranges (defaults to your current IP).
    *   Allows inbound HTTP/HTTPS (Port 80/443 or a custom port like 5000) from the internet (`0.0.0.0/0`) for the OAuth web server callback URL. **Ensure this is configured correctly for the OAuth flow to work.**

4.  **S3 Bucket:**
    *   **Purpose:** Used for temporary storage of videos downloaded via `yt-dlp` or uploaded directly before being sent to the X API via chunked upload.
    *   **Configuration:**
        *   The bucket name is typically defined as a parameter in the CloudFormation template or configured via environment variables (`AWS_S3_BUCKET`).
        *   **Crucially, configure a Lifecycle Rule** on this bucket to automatically delete objects after a short period (e.g., 1-3 days) to prevent accumulation of temporary video files and associated costs.

5.  **DynamoDB Table:**
    *   **Purpose:** Securely stores user-specific OAuth 2.0 refresh tokens obtained during the web-based authorization flow.
    *   **Table Name:** `XSchedulerUserTokens` (or as configured via `DYNAMODB_TABLE` environment variable/config).
    *   **Primary Key:** `user_id` (String). This typically corresponds to the X User ID.
    *   **Attributes:** Stores the refresh token and potentially other metadata like access token expiry.
    *   Provisioned with on-demand capacity mode by default.

6.  **SSM Parameters:** (Optional but Recommended)
    *   Used to securely store sensitive configuration like X API keys, OAuth Client ID/Secret, Google credentials, etc.
    *   The EC2 instance's IAM role needs permission to read these parameters.

### Deployment Steps

1.  **Customize CloudFormation Parameters:**
    Review and potentially modify parameters within `deploy/aws/x-scheduler-stack.yaml` or prepare a parameter file (`parameters.json`). Key parameters often include VPC ID, Subnet ID, Instance Type, Key Pair Name, S3 Bucket Name, allowed SSH CIDR, etc.

2.  **Run the deployment script:**
    Navigate to the `deploy/aws` directory and execute the script.
    ```bash
    cd deploy/aws
    ./deploy-aws.sh <stack-name> <template-file> [parameter-file]
    # Example: ./deploy-aws.sh x-scheduler-prod x-scheduler-stack.yaml parameters-prod.json
    ```

3.  **What the script does (typically):**
    *   Creates or updates the CloudFormation stack defined in the template file.
    *   Waits for the stack creation/update to complete.
    *   Outputs key information like the EC2 instance ID or public IP.

4.  **Post-Deployment Setup:**
    *   **Run OAuth Setup:** SSH into the newly created EC2 instance and run the OAuth setup command to authorize the application with your X account:
        ```bash
        # SSH into the instance first (using SSM or direct SSH)
        python /path/to/your/app/src/main.py --setup-oauth
        ```
        Follow the on-screen instructions and complete the browser authorization. The refresh token will be stored in DynamoDB.
    *   **Configure `systemd` (or other process manager):** Ensure the main scheduler (`scheduler.py`) and the OAuth web server (`oauth_web_server.py`) are configured to run as services and start automatically. The CloudFormation template's UserData section might handle this.

## Updating the Deployed Application

Updates typically involve:
1.  Pushing code changes to your Git repository.
2.  Using AWS CodeDeploy (if configured) or manually SSHing into the instance, pulling the latest code, installing/updating dependencies, and restarting the relevant services (`x-scheduler.service`, `x-scheduler-oauth-web.service`).
3.  Alternatively, update the CloudFormation stack if infrastructure changes (e.g., new UserData script, different instance type) are required.

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
- Consider using AWS CodeDeploy for automated, blue/green, or rolling updates.
- Implement robust health checks for both the scheduler and the OAuth web service.
- Centralize logging using CloudWatch Logs instead of just local files.
- Enhance security by using private subnets and potentially a load balancer for the OAuth web server.
- Automate S3 lifecycle rule creation within the CloudFormation template.

---

_This section is a living document. Add new learnings and troubleshooting tips as you continue to deploy and maintain X-Scheduler._ 
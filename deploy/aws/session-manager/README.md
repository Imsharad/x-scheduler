# AWS Session Manager Guide for X-Scheduler

This guide explains how to use AWS Systems Manager Session Manager to connect to your EC2 instance without SSH, avoiding IP-based restrictions.

## Prerequisites

- AWS CLI installed on your local machine
- Appropriate permissions in your AWS account
- EC2 instance with:
  - SSM Agent installed and running
  - IAM role with AmazonSSMManagedInstanceCore policy attached
  - Network access to SSM endpoints (internet access via NAT or IGW)

## Connection Methods

### 1. Connect via AWS Console (Browser)

1. Go to [AWS Management Console](https://console.aws.amazon.com/)
2. Navigate to **AWS Systems Manager** service
3. Click on **Session Manager** in the left sidebar
4. Click **Start session**
5. Select your instance (`i-04aca3ec6f9a95b52`)
6. Click **Start session**
7. A terminal window will open in your browser

### 2. Connect via AWS CLI

Install the Session Manager plugin for AWS CLI:

**On macOS (using Homebrew):**
```bash
brew install session-manager-plugin
```

**On Linux:**
```bash
curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" -o "session-manager-plugin.deb"
sudo dpkg -i session-manager-plugin.deb
```

**On Windows:**
```
Download from: https://s3.amazonaws.com/session-manager-downloads/plugin/latest/windows/SessionManagerPluginSetup.exe
Run the installer
```

**Start a session:**
```bash
aws ssm start-session --target i-04aca3ec6f9a95b52 --region us-east-1
```

## Common Tasks

### Check Application Logs

Once connected via Session Manager:

```bash
# Navigate to application directory
cd /home/ec2-user/x-scheduler

# Check systemd service logs
sudo journalctl -u x-scheduler.service -f

# Or check application log file directly
tail -f src/log/pipeline.log
```

### Restart Application

```bash
sudo systemctl restart x-scheduler.service
```

### Update Application Code

```bash
cd /home/ec2-user/x-scheduler
git pull origin main
```

## Troubleshooting

### Instance Not Appearing in Session Manager

1. Verify the IAM role has the AmazonSSMManagedInstanceCore policy
2. Check SSM Agent status: `sudo systemctl status amazon-ssm-agent`
3. Check agent logs: `sudo tail -f /var/log/amazon/ssm/amazon-ssm-agent.log`
4. Ensure the instance has internet access to reach AWS SSM endpoints

### Connection Issues

If Session Manager shows "Failed to connect" errors:

1. Restart the SSM Agent: `sudo systemctl restart amazon-ssm-agent`
2. Check that the instance has outbound internet access
3. Verify the instance is in a "running" state

## Security Benefits

- No need to open port 22 (SSH) to the public internet
- No need to manage SSH keys
- Authentication and authorization handled by AWS IAM
- All session activity can be logged to CloudWatch Logs or S3
- Integration with AWS CloudTrail for auditing 
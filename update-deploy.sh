#!/bin/bash

# --- Configuration ---
# Update these values to match your setup from DEPLOYMENT.md

EC2_IP="54.226.70.194"                                       # Your EC2 instance Public IP
SSH_USER="ec2-user"                                          # Your SSH user (usually ec2-user for Amazon Linux)
SSH_KEY_FILE="deploy/keys/x-scheduler-key-1746111370.pem"     # Path to your SSH private key (.pem file)
REMOTE_APP_DIR="/home/ec2-user/x-scheduler"                  # Application directory on the EC2 instance
GIT_BRANCH="main"                                            # The Git branch to pull updates from

# --- Script Logic ---

echo "--- Starting X-Scheduler Update Deployment ---"

# 1. Check SSH Key Permissions (Basic Check)
if [ ! -f "$SSH_KEY_FILE" ]; then
    echo "ERROR: SSH Key file not found at '$SSH_KEY_FILE'"
    exit 1
fi
# Optional: More robust permission check if needed
# key_perms=$(stat -c %a "$SSH_KEY_FILE") # Linux
# key_perms=$(stat -f %A "$SSH_KEY_FILE") # macOS
# if [[ "$key_perms" != "400" && "$key_perms" != "600" ]]; then # 600 is also often acceptable
#     echo "WARNING: SSH Key file permissions might be too open. Should be 400 or 600."
#     # Consider exiting here if strict permissions are required: exit 1
# fi

# 2. Prerequisites Check (Reminders)
echo "INFO: Make sure you have committed and pushed your latest code to the '$GIT_BRANCH' branch."
echo "INFO: Ensure your 'config/google-credentials.json' is present and up-to-date in the '$REMOTE_APP_DIR/config/' directory on the EC2 instance (if not managed by Git)."
read -p "Proceed with deployment? (y/N): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# 3. Connect via SSH and Execute Update Commands
echo "INFO: Connecting to $EC2_IP..."
echo "INFO: Executing update commands remotely..."

ssh -i "$SSH_KEY_FILE" "$SSH_USER@$EC2_IP" "
    set -e # Exit immediately if a command exits with a non-zero status.
    echo 'INFO: Navigating to application directory: $REMOTE_APP_DIR'
    cd '$REMOTE_APP_DIR'

    echo 'INFO: Pulling latest code from Git branch: $GIT_BRANCH...'
    git checkout '$GIT_BRANCH' # Ensure we are on the correct branch
    git pull origin '$GIT_BRANCH'

    echo 'INFO: Rebuilding and restarting Docker containers...'
    docker-compose up -d --build

    echo 'INFO: Deployment commands completed.'
"

# Check if SSH command was successful
if [ $? -ne 0 ]; then
    echo "ERROR: Remote update commands failed. Check the output above."
    exit 1
fi

echo "--- X-Scheduler Update Deployment Finished Successfully ---"
echo "INFO: You may want to monitor logs manually:"
echo "ssh -i \"$SSH_KEY_FILE\" \"$SSH_USER@$EC2_IP\" \"cd '$REMOTE_APP_DIR' && docker-compose logs -f\""

exit 0 
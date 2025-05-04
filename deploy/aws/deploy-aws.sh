#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
CONFIG_FILE="deploy/aws/deploy.config"
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Error: Deployment configuration file not found: $CONFIG_FILE"
    echo "Please create it based on deploy/aws/deploy.config.example"
            exit 1
fi
source "$CONFIG_FILE"

# --- AWS & Stack Configuration ---
REGION=${AWS_REGION:?"AWS_REGION must be set in $CONFIG_FILE"}
STACK_NAME=${STACK_NAME:-"x-scheduler-stack"}
TEMPLATE_FILE="deploy/aws/cloudformation.yaml"
# Parameters required by cloudformation.yaml (ensure they are in deploy.config)
KEY_PAIR_NAME=${KEY_PAIR_NAME:?"KEY_PAIR_NAME must be set in $CONFIG_FILE"}
S3_BUCKET_NAME=${S3_BUCKET_NAME:?"S3_BUCKET_NAME must be set in $CONFIG_FILE"}
# Optional parameters with defaults from CFN template, can be overridden in deploy.config
EC2_INSTANCE_TYPE=${EC2_INSTANCE_TYPE:-"t2.micro"}
DYNAMODB_TABLE_NAME=${DYNAMODB_TABLE_NAME:-"XSchedulerUserTokens"}
FLASK_PORT=${FLASK_PORT:-5000}
SUBNET_ID=${SUBNET_ID:-""} # Optional subnet ID from config
VPC_ID=${VPC_ID:-""}     # Optional VPC ID from config

# --- Application Configuration ---
GIT_REPO_URL=${GIT_REPO_URL:?"GIT_REPO_URL must be set in $CONFIG_FILE"} # Your Git repo URL
PROJECT_DIR_ON_INSTANCE="/home/ec2-user/X-scheduler" # Adjust if needed
SSM_ENV_PARAM_NAME=${SSM_ENV_PARAM_NAME:-"/x-scheduler/env"} # Parameter Store name for .env content

# Helper function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for AWS CLI
if ! command_exists aws; then
    echo "Error: AWS CLI is not installed or not in PATH."
        exit 1
    fi
# Check for jq
if ! command_exists jq; then
    echo "Error: jq is not installed or not in PATH. Please install jq (e.g., 'brew install jq' or 'sudo apt-get install jq')."
        exit 1
fi

echo "--- Starting X-Scheduler AWS Deployment ---"
echo "Using configuration:"
echo "  Region: $REGION"
echo "  Stack Name: $STACK_NAME"
echo "  CFN Template: $TEMPLATE_FILE"
echo "  EC2 Instance Type: $EC2_INSTANCE_TYPE"
echo "  Key Pair Name: $KEY_PAIR_NAME"
echo "  S3 Bucket Name: $S3_BUCKET_NAME"
echo "  DynamoDB Table Name: $DYNAMODB_TABLE_NAME"
echo "  Flask Port: $FLASK_PORT"
echo "  Git Repo URL: $GIT_REPO_URL"
echo "  Project Dir on Instance: $PROJECT_DIR_ON_INSTANCE"
echo "  SSM Param for .env: $SSM_ENV_PARAM_NAME"
[ -n "$VPC_ID" ] && echo "  VPC ID: $VPC_ID"
[ -n "$SUBNET_ID" ] && echo "  Subnet ID: $SUBNET_ID"

# --- 1. Create/Update S3 Bucket for Video Storage (Sub-step 30.3) ---
echo "Checking/Creating S3 bucket: $S3_BUCKET_NAME..."
if ! aws s3api head-bucket --bucket "$S3_BUCKET_NAME" --region "$REGION" 2>/dev/null; then
    echo "Bucket does not exist. Creating..."
    if [ "$REGION" == "us-east-1" ]; then
        aws s3api create-bucket --bucket "$S3_BUCKET_NAME" --region "$REGION"
    else
        aws s3api create-bucket --bucket "$S3_BUCKET_NAME" --region "$REGION" --create-bucket-configuration LocationConstraint="$REGION"
    fi
    echo "Bucket $S3_BUCKET_NAME created."
    # Add lifecycle policy (example: delete objects after 7 days)
    LIFECYCLE_CONFIG='{
      "Rules": [
        {
          "ID": "DeleteOldVideos",
          "Status": "Enabled",
          "Prefix": "",
          "Expiration": {
            "Days": 7
          }
        }
      ]
    }'
    aws s3api put-bucket-lifecycle-configuration --bucket "$S3_BUCKET_NAME" --lifecycle-configuration "$LIFECYCLE_CONFIG"
    echo "Applied lifecycle policy to $S3_BUCKET_NAME."
else
    echo "Bucket $S3_BUCKET_NAME already exists."
fi


# --- 2. Create/Update DynamoDB Table for OAuth Tokens (Sub-step 30.1) ---
echo "Checking/Creating DynamoDB table: $DYNAMODB_TABLE_NAME..."
if ! aws dynamodb describe-table --table-name "$DYNAMODB_TABLE_NAME" --region "$REGION" > /dev/null 2>&1; then
    echo "Table does not exist. Creating..."
    aws dynamodb create-table \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --attribute-definitions AttributeName=user_id,AttributeType=S \
        --key-schema AttributeName=user_id,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region "$REGION" # Using On-Demand capacity
    echo "Waiting for table $DYNAMODB_TABLE_NAME to become active..."
    aws dynamodb wait table-exists --table-name "$DYNAMODB_TABLE_NAME" --region "$REGION"
    echo "Table $DYNAMODB_TABLE_NAME created and active."
else
    echo "Table $DYNAMODB_TABLE_NAME already exists."
    # Optional: Add logic here to update table if needed (e.g., GSI)
fi

# --- 3. Deploy/Update CloudFormation Stack (Core Infrastructure) ---
echo "Deploying/Updating CloudFormation stack: $STACK_NAME..."
# Build parameter overrides string dynamically
CFN_PARAMS="ParameterKey=KeyPairName,ParameterValue=$KEY_PAIR_NAME"
CFN_PARAMS="$CFN_PARAMS ParameterKey=InstanceTypeParameter,ParameterValue=$EC2_INSTANCE_TYPE"
CFN_PARAMS="$CFN_PARAMS ParameterKey=S3BucketNameParameter,ParameterValue=$S3_BUCKET_NAME"
CFN_PARAMS="$CFN_PARAMS ParameterKey=DynamoDBTableNameParameter,ParameterValue=$DYNAMODB_TABLE_NAME"
CFN_PARAMS="$CFN_PARAMS ParameterKey=FlaskPortParameter,ParameterValue=$FLASK_PORT"
[ -n "$VPC_ID" ] && CFN_PARAMS="$CFN_PARAMS ParameterKey=VpcIdParameter,ParameterValue=$VPC_ID"
[ -n "$SUBNET_ID" ] && CFN_PARAMS="$CFN_PARAMS ParameterKey=SubnetIdParameter,ParameterValue=$SUBNET_ID"

aws cloudformation deploy \
    --template-file "$TEMPLATE_FILE" \
    --stack-name "$STACK_NAME" \
    --parameter-overrides $CFN_PARAMS \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --no-fail-on-empty-changeset # Allow running even if no changes detected

echo "CloudFormation stack deployment initiated. Waiting for completion..."
# Wait for stack creation or update to complete
# Determine if stack exists to decide which 'wait' command to use
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].StackStatus" --output text --region "$REGION" 2>/dev/null || echo "DOES_NOT_EXIST")

if [[ "$STACK_STATUS" == "DOES_NOT_EXIST" || "$STACK_STATUS" == "DELETE_COMPLETE" ]]; then
    echo "Waiting for stack creation to complete..."
    aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME" --region "$REGION"
elif [[ "$STACK_STATUS" == "CREATE_FAILED" || "$STACK_STATUS" == "ROLLBACK_FAILED" || "$STACK_STATUS" == "ROLLBACK_COMPLETE" || "$STACK_STATUS" == "DELETE_FAILED" ]]; then
     echo "Error: Stack $STACK_NAME is in a failed/rolled back state ($STACK_STATUS)."
     # Optionally add cleanup logic here, e.g., aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
     exit 1
else
    echo "Waiting for stack update to complete..."
    aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME" --region "$REGION"
fi

echo "CloudFormation stack deployment complete."

# Retrieve outputs from the stack
INSTANCE_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text --region "$REGION")
INSTANCE_IP=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='PublicIp'].OutputValue" --output text --region "$REGION")
SECURITY_GROUP_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='SecurityGroupId'].OutputValue" --output text --region "$REGION")

if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" == "None" ]]; then
    echo "Error: Could not retrieve InstanceId output from CloudFormation stack $STACK_NAME."
    exit 1
fi
if [[ -z "$INSTANCE_IP" || "$INSTANCE_IP" == "None" ]]; then
    # Try fetching IP directly from EC2 as a fallback
    echo "Warning: Could not retrieve PublicIp output from CloudFormation stack $STACK_NAME. Trying EC2 API..."
    INSTANCE_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query "Reservations[0].Instances[0].PublicIpAddress" --output text --region "$REGION")
    if [[ -z "$INSTANCE_IP" || "$INSTANCE_IP" == "None" ]]; then
         echo "Error: Could not retrieve Public IP for instance $INSTANCE_ID even from EC2 API."
         exit 1
    fi
fi

echo "Instance ID: $INSTANCE_ID"
echo "Instance Public IP: $INSTANCE_IP"
echo "Security Group ID: $SECURITY_GROUP_ID"

# --- 4. Deploy Application Code (via SSM Run Command) ---
echo "Deploying/Updating application on instance $INSTANCE_ID via SSM Run Command..."

# a) Create systemd service file content for Flask app
SYSTEMD_SERVICE_CONTENT="[Unit]
Description=X-Scheduler Flask OAuth Helper
After=network.target docker.service # Ensure docker is running if flask needs it (likely not directly)
Requires=docker.service # Make dependency explicit if needed

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=${PROJECT_DIR_ON_INSTANCE} # Run from project root
# Load environment vars from .env file located in the working directory
EnvironmentFile=${PROJECT_DIR_ON_INSTANCE}/.env
ExecStart=/usr/bin/python3 ${PROJECT_DIR_ON_INSTANCE}/src/oauth_web_server.py # Use python3 explicit path
Restart=always
StandardOutput=append:/var/log/x-scheduler-flask.log
StandardError=append:/var/log/x-scheduler-flask-error.log

[Install]
WantedBy=multi-user.target"

# Escape content for SSM/Shell
ESCAPED_SYSTEMD_SERVICE_CONTENT=$(echo "$SYSTEMD_SERVICE_CONTENT" | sed 's/\\/\\\\/g; s/\$/\\$/g; s/"/\\"/g; s/`/\\`/g')

# b) Define commands to run on the instance via SSM
# Using HEREDOC for better readability of multiline commands
read -r -d '' SSM_COMMAND_SCRIPT << EOM || true
set -e # Exit script if any command fails
exec > >(tee /var/log/x-scheduler-deployment.log|logger -t user-data -s 2>/dev/console) 2>&1 # Log stdout/stderr

echo "--- Starting Application Deployment on Instance ---"
# Ensure project directory exists (UserData should have created it)
echo "Ensuring project directory exists: ${PROJECT_DIR_ON_INSTANCE}"
mkdir -p "${PROJECT_DIR_ON_INSTANCE}"
chown ec2-user:ec2-user "${PROJECT_DIR_ON_INSTANCE}"
cd "${PROJECT_DIR_ON_INSTANCE}"

# Clone or update repo
echo "Cloning or updating repository from ${GIT_REPO_URL}..."
if [ -d .git ]; then
    echo 'Repo exists, pulling changes...'
    git fetch --all
    # Consider a safer reset strategy if needed, e.g., stash local changes
    # git reset --hard origin/\$(git rev-parse --abbrev-ref HEAD) # Reset to remote branch head
    git pull
else
    echo 'Cloning repo...'
    git clone "${GIT_REPO_URL}" .
fi
chown -R ec2-user:ec2-user . # Ensure ownership after git operations

# Fetch .env content from Parameter Store
echo "Fetching .env from Parameter Store: ${SSM_ENV_PARAM_NAME}"
aws ssm get-parameter --name "${SSM_ENV_PARAM_NAME}" --with-decryption --query Parameter.Value --output text --region "${REGION}" > .env
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to fetch .env from Parameter Store: ${SSM_ENV_PARAM_NAME}"
    exit 1
fi
chown ec2-user:ec2-user .env # Ensure user owns the .env file
chmod 600 .env              # Restrict permissions

# Install Python dependencies (consider using a virtualenv)
echo 'Installing/Updating Python requirements...'
if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt
else
    echo "WARNING: requirements.txt not found in repository."
fi

# Build and run Docker containers for the main scheduler
echo 'Checking for docker-compose.yml...'
if [ -f docker-compose.yml ]; then
    echo 'Stopping existing Docker containers (if any)...'
    # Use the full path to docker-compose found by 'which' or default location
    DOCKER_COMPOSE_PATH=\$(which docker-compose || echo "/usr/local/bin/docker-compose")
    \$DOCKER_COMPOSE_PATH down || true # Stop existing containers if running
    echo 'Building and starting Docker containers...'
    \$DOCKER_COMPOSE_PATH up -d --build # Build and start in detached mode
else
    echo "WARNING: docker-compose.yml not found in repository."
fi

# Setup systemd service for Flask OAuth (Sub-step 30.7)
echo 'Setting up systemd service for Flask...'
echo "${ESCAPED_SYSTEMD_SERVICE_CONTENT}" | sudo tee /etc/systemd/system/x-scheduler-flask.service > /dev/null
sudo chmod 644 /etc/systemd/system/x-scheduler-flask.service
sudo systemctl daemon-reload
sudo systemctl enable x-scheduler-flask.service
sudo systemctl restart x-scheduler-flask.service
echo 'Checking Flask service status...'
sleep 5 # Give service a moment to start
sudo systemctl status x-scheduler-flask.service || echo "Warning: Flask service status check failed, check logs manually."

echo "--- Application Deployment on Instance Complete ---"
EOM

# c) Send command via SSM
echo "Sending SSM command..."
COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters commands="$SSM_COMMAND_SCRIPT" \
    --query "Command.CommandId" \
    --output text \
    --region "$REGION")

echo "SSM Command sent (ID: $COMMAND_ID). Waiting for completion..."

# d) Wait for the command to complete
while true; do
    # Fetch specific invocation for the target instance
    INVOCATION_INFO=$(aws ssm list-command-invocations --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" --details --region "$REGION" --output json)
    # Check if invocation exists (command might be pending)
    if [[ $(echo "$INVOCATION_INFO" | jq '.CommandInvocations | length') -eq 0 ]]; then
        echo "  Waiting for invocation details..."
        sleep 5
        continue
    fi
    STATUS=$(echo "$INVOCATION_INFO" | jq -r '.CommandInvocations[0].Status')
    echo "  Command Status: $STATUS"
    if [[ "$STATUS" == "Success" || "$STATUS" == "Failed" || "$STATUS" == "Cancelled" || "$STATUS" == "TimedOut" || "$STATUS" == "Cancelling" || "$STATUS" == "Undeliverable" ]]; then
            break
    fi
    sleep 10
done

echo "SSM Command finished with status: $STATUS"

# e) Display output/errors from SSM command
echo "--- SSM Command Output (Instance: $INSTANCE_ID) ---"
# Get the standard output and error streams
STD_OUT=$(echo "$INVOCATION_INFO" | jq -r '.CommandInvocations[0].CommandPlugins[] | select(.Name=="aws:runShellScript") | .Output')
STD_ERR=$(echo "$INVOCATION_INFO" | jq -r '.CommandInvocations[0].CommandPlugins[] | select(.Name=="aws:runShellScript") | .StandardErrorContent')

echo "--- Standard Output ---"
echo "$STD_OUT"
echo "--- Standard Error ---"
echo "$STD_ERR"
echo "--------------------------"

if [[ "$STATUS" != "Success" ]]; then
    echo "Error: SSM command execution failed with status $STATUS."
    echo "Check the output above and logs on the instance:"
    echo "  Deployment Log: /var/log/x-scheduler-deployment.log"
    echo "  Flask Log: /var/log/x-scheduler-flask.log"
    echo "  Flask Error Log: /var/log/x-scheduler-flask-error.log"
    exit 1
fi

# --- 5. Final Steps ---
echo "--- Deployment Script Completed Successfully ---"
echo "Instance ID: $INSTANCE_ID"
echo "Instance Public IP: $INSTANCE_IP"
echo "Flask OAuth App URL: http://$INSTANCE_IP:$FLASK_PORT"
echo "SSH Access: ssh -i <your-key.pem> ec2-user@$INSTANCE_IP"
echo "------------------------------------------------"
echo "IMPORTANT:"
echo "1. Ensure your X App Redirect URI is configured to: http://$INSTANCE_IP:$FLASK_PORT/callback"
echo "2. Check CloudWatch Logs and instance logs for application output."
echo "   Deployment Log: /var/log/x-scheduler-deployment.log"
echo "   Flask Log: /var/log/x-scheduler-flask.log"
echo "   Flask Error Log: /var/log/x-scheduler-flask-error.log"
echo "3. For production, restrict SSH (port 22) and Flask (port $FLASK_PORT) access in the Security Group ('$STACK_NAME-SG')."
echo "4. Ensure the SSM Parameter '${SSM_ENV_PARAM_NAME}' contains the necessary .env file content."
echo "------------------------------------------------"

exit 0 
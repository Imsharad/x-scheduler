 #!/bin/bash

# --- CONFIGURATION ---
AWS_REGION="us-east-1" # Change to your desired AWS region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text) # Gets account ID automatically
APP_NAME="x-scheduler"
GIT_REPO_URL="https://github.com/YOUR_USERNAME/X-scheduler.git" # IMPORTANT: Set your repo URL 
EC2_INSTANCE_TYPE="t2.micro" # Free tier eligible instance type
EC2_AMI_ID="" # Leave blank to fetch latest Amazon Linux 2 AMI automatically
KEY_PAIR_NAME="${APP_NAME}-key-$(date +%s)" # Creates a unique key pair name
# --- END CONFIGURATION ---

# --- Helper Functions ---
check_command() {
    if [ $? -ne 0 ]; then
        echo "Error: $1 failed."
        exit 1
    fi
}

get_latest_amazon_linux_2_ami() {
    echo "Fetching latest Amazon Linux 2 AMI ID for region $AWS_REGION..."
    AMI_ID=$(aws ec2 describe-images \
        --owners amazon \
        --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" "Name=state,Values=available" \
        --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
        --region "$AWS_REGION" \
        --output text)
    check_command "Fetching AMI ID"
    if [ -z "$AMI_ID" ]; then
        echo "Error: Could not find latest Amazon Linux 2 AMI ID."
        exit 1
    fi
    EC2_AMI_ID=$AMI_ID
    echo "Using AMI ID: $EC2_AMI_ID"
}

# --- Main Script ---
set -e # Exit immediately if a command exits with a non-zero status.

echo "Starting AWS deployment for $APP_NAME..."
echo "Using Region: $AWS_REGION, Account ID: $AWS_ACCOUNT_ID"

# 1. Create IAM Policy for SSM Access
echo "Step 1: Creating IAM Policy..."
POLICY_NAME="${APP_NAME}-SSM-Read-Policy"
POLICY_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:policy/$POLICY_NAME"
PARAM_ARN_PREFIX="arn:aws:ssm:$AWS_REGION:$AWS_ACCOUNT_ID:parameter/$APP_NAME"

POLICY_DOC=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters"
            ],
            "Resource": "$PARAM_ARN_PREFIX/*"
        }
    ]
}
EOF
)

# Check if policy exists, create if not
if ! aws iam get-policy --policy-arn "$POLICY_ARN" --region "$AWS_REGION" > /dev/null 2>&1; then
    aws iam create-policy --policy-name "$POLICY_NAME" --policy-document "$POLICY_DOC" --region "$AWS_REGION" > /dev/null
    check_command "Creating IAM Policy"
    echo "IAM Policy '$POLICY_NAME' created."
else
    echo "IAM Policy '$POLICY_NAME' already exists."
fi

# 2. Create IAM Role & Instance Profile
echo "Step 2: Creating IAM Role and Instance Profile..."
ROLE_NAME="${APP_NAME}-EC2-Role"
INSTANCE_PROFILE_NAME="${APP_NAME}-EC2-Instance-Profile"

TRUST_POLICY_DOC=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

# Check if role exists, create if not
if ! aws iam get-role --role-name "$ROLE_NAME" --region "$AWS_REGION" > /dev/null 2>&1; then
    aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document "$TRUST_POLICY_DOC" --region "$AWS_REGION" > /dev/null
    check_command "Creating IAM Role"
    echo "IAM Role '$ROLE_NAME' created."
else
    echo "IAM Role '$ROLE_NAME' already exists."
fi

# Check if instance profile exists, create if not
if ! aws iam get-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" --region "$AWS_REGION" > /dev/null 2>&1; then
    aws iam create-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" --region "$AWS_REGION" > /dev/null
    check_command "Creating Instance Profile"
    echo "Instance Profile '$INSTANCE_PROFILE_NAME' created."
else
     echo "Instance Profile '$INSTANCE_PROFILE_NAME' already exists."
fi

# Add role to instance profile (safe to run even if already added)
aws iam add-role-to-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" --role-name "$ROLE_NAME" --region "$AWS_REGION" 2>/dev/null || true
check_command "Adding Role to Instance Profile"

# Attach policy to role (safe to run even if already attached)
aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "$POLICY_ARN" --region "$AWS_REGION" > /dev/null
check_command "Attaching Policy to Role"

echo "Waiting for IAM changes to propagate..."
sleep 15 # Allow time for IAM changes

# 3. Create Security Group & Add Rule
echo "Step 3: Creating Security Group..."
SG_NAME="${APP_NAME}-sg"
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION")
check_command "Getting Default VPC ID"

# Check if security group exists
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" --query 'SecurityGroups[0].GroupId' --output text --region "$AWS_REGION")

if [ "$SG_ID" == "None" ] || [ -z "$SG_ID" ]; then
    SG_ID=$(aws ec2 create-security-group --group-name "$SG_NAME" --description "Security group for $APP_NAME" --vpc-id "$VPC_ID" --query 'GroupId' --output text --region "$AWS_REGION")
    check_command "Creating Security Group"
    echo "Security Group '$SG_NAME' created with ID: $SG_ID"

    MY_IP=$(curl -s http://checkip.amazonaws.com)
    check_command "Getting public IP address"
    echo "Authorizing SSH access from your IP: $MY_IP"
    aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 --cidr "$MY_IP/32" --region "$AWS_REGION" > /dev/null
    check_command "Authorizing SSH Ingress"
else
     echo "Security Group '$SG_NAME' already exists with ID: $SG_ID"
fi


# 4. Store Secrets in SSM Parameter Store
echo "Step 4: Storing Secrets in SSM Parameter Store..."
echo "Please enter your X API credentials:"
read -sp 'API Key: ' X_API_KEY; echo
read -sp 'API Key Secret: ' X_API_KEY_SECRET; echo
read -sp 'Access Token: ' X_ACCESS_TOKEN; echo
read -sp 'Access Token Secret: ' X_ACCESS_TOKEN_SECRET; echo
# Add prompt for Bearer Token if needed

aws ssm put-parameter --name "/$APP_NAME/api-key" --value "$X_API_KEY" --type SecureString --overwrite --region "$AWS_REGION" > /dev/null
aws ssm put-parameter --name "/$APP_NAME/api-key-secret" --value "$X_API_KEY_SECRET" --type SecureString --overwrite --region "$AWS_REGION" > /dev/null
aws ssm put-parameter --name "/$APP_NAME/access-token" --value "$X_ACCESS_TOKEN" --type SecureString --overwrite --region "$AWS_REGION" > /dev/null
aws ssm put-parameter --name "/$APP_NAME/access-token-secret" --value "$X_ACCESS_TOKEN_SECRET" --type SecureString --overwrite --region "$AWS_REGION" > /dev/null
# Add put-parameter for Bearer Token if needed

check_command "Storing secrets in SSM"
echo "Secrets stored securely in SSM Parameter Store."

# 5. Create EC2 Key Pair
echo "Step 5: Creating EC2 Key Pair..."
KEY_FILE="${KEY_PAIR_NAME}.pem"
aws ec2 create-key-pair --key-name "$KEY_PAIR_NAME" --query 'KeyMaterial' --output text --region "$AWS_REGION" > "$KEY_FILE"
check_command "Creating Key Pair"
chmod 400 "$KEY_FILE"
echo "EC2 Key Pair '$KEY_PAIR_NAME' created and saved to $KEY_FILE. Keep this file secure!"

# 6. Prepare EC2 User Data Script
echo "Step 6: Preparing EC2 User Data..."
# Fetch AMI ID if not set
if [ -z "$EC2_AMI_ID" ]; then
    get_latest_amazon_linux_2_ami
fi

# Define User Data Script (Amazon Linux 2)
# Ensure GIT_REPO_URL is correctly set above!
USER_DATA=$(cat <<EOF
#!/bin/bash -xe
# Update system and install packages
yum update -y
yum install git python3 python3-pip python3-venv jq -y # Added jq

# Get user home directory (assuming ec2-user)
USER_HOME="/home/ec2-user"
APP_DIR="\$USER_HOME/$APP_NAME"
VENV_DIR="\$APP_DIR/venv"
LOG_FILE="\$APP_DIR/src/log/pipeline.log" # Ensure log dir exists if needed by logger

# Clone the repository as the ec2-user
sudo -u ec2-user git clone $GIT_REPO_URL \$APP_DIR

# Create virtual environment and install dependencies as ec2-user
sudo -u ec2-user python3 -m venv \$VENV_DIR
sudo -u ec2-user \$VENV_DIR/bin/pip install -r \$APP_DIR/requirements.txt boto3

# Ensure log directory exists and has correct permissions
sudo -u ec2-user mkdir -p \$(dirname \$LOG_FILE)
sudo -u ec2-user touch \$LOG_FILE

# Create systemd service file
cat << EOFF > /etc/systemd/system/$APP_NAME.service
[Unit]
Description=$APP_NAME Service
After=network.target

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=\$APP_DIR
# Use full path for python executable within the virtual environment
ExecStart=\$VENV_DIR/bin/python \$APP_DIR/src/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOFF

# Reload systemd, enable and start the service
systemctl daemon-reload
systemctl enable $APP_NAME.service
systemctl start $APP_NAME.service
EOF
)

# 7. Launch EC2 Instance
echo "Step 7: Launching EC2 Instance..."
INSTANCE_INFO=$(aws ec2 run-instances \
    --image-id "$EC2_AMI_ID" \
    --instance-type "$EC2_INSTANCE_TYPE" \
    --key-name "$KEY_PAIR_NAME" \
    --security-group-ids "$SG_ID" \
    --iam-instance-profile Name="$INSTANCE_PROFILE_NAME" \
    --user-data "$USER_DATA" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${APP_NAME}-instance}]" \
    --region "$AWS_REGION")

check_command "Launching EC2 Instance"

INSTANCE_ID=$(echo "$INSTANCE_INFO" | jq -r '.Instances[0].InstanceId')
echo "EC2 Instance '$INSTANCE_ID' launched successfully."
echo "Waiting for instance to initialize and get public IP..."

# Wait for instance to be running and get Public IP
while true; do
    INSTANCE_STATE=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].State.Name' --output text --region "$AWS_REGION")
    if [ "$INSTANCE_STATE" == "running" ]; then
        PUBLIC_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text --region "$AWS_REGION")
        if [ "$PUBLIC_IP" != "None" ] && [ -n "$PUBLIC_IP" ]; then
            echo "Instance is running. Public IP: $PUBLIC_IP"
            break
        fi
    fi
    echo -n "."
    sleep 5
done

echo "--- Deployment Summary ---"
echo "Instance ID: $INSTANCE_ID"
echo "Instance Type: $EC2_INSTANCE_TYPE"
echo "Region: $AWS_REGION"
echo "Public IP: $PUBLIC_IP"
echo "Key Pair File: $KEY_FILE"
echo "SSH Command: ssh -i $KEY_FILE ec2-user@$PUBLIC_IP" # Adjust user based on AMI
echo "Application should be running. Check logs with:"
echo "  journalctl -u $APP_NAME.service -f  (via SSH)"
echo "  tail -f $APP_DIR/src/log/pipeline.log (via SSH)"
echo "--------------------------"
echo "Deployment script finished." 
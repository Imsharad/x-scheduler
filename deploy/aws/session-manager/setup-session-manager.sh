#!/bin/bash

# AWS Session Manager Setup Script for X-Scheduler
# This script configures Session Manager access to the EC2 instance

# --- Configuration ---
AWS_REGION="us-east-1"
ROLE_NAME="x-scheduler-EC2-Role"
INSTANCE_ID="i-04aca3ec6f9a95b52"  # Update this to your EC2 instance ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)

if [ -z "$ACCOUNT_ID" ]; then
    echo "ERROR: Unable to get AWS account ID. Please ensure you're authenticated with AWS CLI."
    exit 1
fi

echo "====== AWS Session Manager Setup ======"
echo "  Region: $AWS_REGION"
echo "  Account: $ACCOUNT_ID"
echo "  Instance: $INSTANCE_ID"
echo "  Role: $ROLE_NAME"
echo "======================================="

# Create a detailed policy document with all required SSM permissions
echo "Creating SSM policy document..."
cat > ssm-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:UpdateInstanceInformation",
                "ssm:ListInstanceAssociations",
                "ssm:DescribeInstanceProperties",
                "ssm:DescribeDocumentParameters",
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:GetDocument",
                "ssm:DescribeDocument",
                "ssm:GetManifest",
                "ssm:PutInventory",
                "ssm:PutConfigurePackageResult",
                "ssm:GetDeployablePatchSnapshotForInstance",
                "ssm:DescribeAssociation",
                "ssmmessages:CreateControlChannel",
                "ssmmessages:CreateDataChannel",
                "ssmmessages:OpenControlChannel",
                "ssmmessages:OpenDataChannel",
                "ec2messages:AcknowledgeMessage",
                "ec2messages:DeleteMessage",
                "ec2messages:FailMessage",
                "ec2messages:GetEndpoint",
                "ec2messages:GetMessages",
                "ec2messages:SendReply"
            ],
            "Resource": "*"
        }
    ]
}
EOF

# Create policy
POLICY_NAME="x-scheduler-SSM-Policy"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

# Check if policy already exists
if aws iam get-policy --policy-arn "$POLICY_ARN" --region "$AWS_REGION" 2>/dev/null; then
    echo "Policy $POLICY_NAME already exists."
else
    echo "Creating policy $POLICY_NAME..."
    aws iam create-policy --policy-name "$POLICY_NAME" --policy-document file://ssm-policy.json --region "$AWS_REGION"
    check_result=$?
    if [ $check_result -ne 0 ]; then
        echo "ERROR: Failed to create policy."
        exit 1
    fi
fi

# Attach policies to role
echo "Attaching policies to role $ROLE_NAME..."
aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "$POLICY_ARN" --region "$AWS_REGION"
aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore" --region "$AWS_REGION"

echo "Waiting for permissions to propagate (10 seconds)..."
sleep 10

echo "Session Manager setup complete."
echo ""
echo "To connect to your instance:"
echo "1. Ensure the SSM Agent is running on your instance"
echo "2. Run: aws ssm start-session --target $INSTANCE_ID --region $AWS_REGION"
echo ""
echo "See README.md for more details on using Session Manager."

# Clean up
rm ssm-policy.json

exit 0 
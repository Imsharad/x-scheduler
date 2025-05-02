# Creating IAM Policy for x-scheduler Application

## Overview

This document provides instructions for creating the IAM policy required by the x-scheduler application to read parameters from AWS Systems Manager Parameter Store. The policy needs to be created by a user with administrative privileges.

## Prerequisites

- An AWS account administrator with permissions to create IAM policies
- Access to AWS Management Console or AWS CLI
- The CloudFormation template file: `x-scheduler-iam-policy.yaml`

## Who Should Run This Template

The CloudFormation template must be executed by a user who has the following permissions:
- `cloudformation:CreateStack`
- `iam:CreatePolicy`
- `iam:GetPolicy`

Your current user (`sharad-x-scheduler`) does not have these permissions, so you'll need to contact your AWS account administrator to execute these steps.

## Option 1: Deploy Using AWS Management Console

1. **Log in to the AWS Management Console**
   - Sign in as a user with administrator privileges

2. **Navigate to CloudFormation**
   - Go to Services > CloudFormation

3. **Create a new Stack**
   - Click "Create stack" > "With new resources (standard)"
   
4. **Upload the Template**
   - Select "Upload a template file"
   - Click "Choose file"
   - Select the `x-scheduler-iam-policy.yaml` file from your computer
   - Click "Next"

5. **Specify Stack Details**
   - Stack name: `x-scheduler-iam-policy-stack` (or your preferred name)
   - Parameters:
     - PolicyName: `x-scheduler-SSM-Read-Policy` (default)
     - AccountId: `164638039016` (default)
     - Region: `us-east-1` (default)
   - Click "Next"

6. **Configure Stack Options**
   - Leave the default settings
   - Click "Next"

7. **Review**
   - Review your settings
   - Check the box acknowledging that AWS CloudFormation might create IAM resources
   - Click "Create stack"

8. **Wait for Completion**
   - The stack creation should complete in a few minutes
   - When the status shows "CREATE_COMPLETE", the IAM policy has been created successfully

## Option 2: Deploy Using AWS CLI

1. **Ensure AWS CLI is installed and configured**
   - The CLI should be configured with administrator credentials

2. **Deploy the CloudFormation template**
   ```bash
   aws cloudformation create-stack \
     --stack-name x-scheduler-iam-policy-stack \
     --template-body file://x-scheduler-iam-policy.yaml \
     --capabilities CAPABILITY_NAMED_IAM
   ```

3. **Check deployment status**
   ```bash
   aws cloudformation describe-stacks \
     --stack-name x-scheduler-iam-policy-stack \
     --query "Stacks[0].StackStatus"
   ```
   
   Wait until you see the output: `"CREATE_COMPLETE"`

## After the Policy is Created

Once the policy is created, it needs to be attached to the IAM role used by the x-scheduler EC2 instances. This can be done in two ways:

### Option 1: Attach Using the AWS Console

1. Go to IAM in the AWS Management Console
2. Navigate to Roles
3. Find the role used by your x-scheduler EC2 instances (typically `x-scheduler-EC2-Role`)
4. Click "Attach policies"
5. Search for `x-scheduler-SSM-Read-Policy`
6. Select the policy and click "Attach policy"

### Option 2: Attach Using the AWS CLI

```bash
aws iam attach-role-policy \
  --role-name x-scheduler-EC2-Role \
  --policy-arn arn:aws:iam::164638039016:policy/x-scheduler-SSM-Read-Policy
```

## Verifying the Policy

### Check Policy Exists

Using the AWS Console:
1. Go to IAM in the AWS Management Console
2. Navigate to Policies
3. Search for `x-scheduler-SSM-Read-Policy`
4. If the policy is listed, it was created successfully

Using the AWS CLI:
```bash
aws iam get-policy \
  --policy-arn arn:aws:iam::164638039016:policy/x-scheduler-SSM-Read-Policy
```

### Test Policy Functionality

After attaching the policy to the role and launching an EC2 instance with that role, you can verify the permissions work:

```bash
# Connect to your EC2 instance
ssh -i your-key.pem ec2-user@your-instance-ip

# On the EC2 instance, try to access a parameter
aws ssm get-parameter \
  --name /x-scheduler/api-key \
  --with-decryption \
  --region us-east-1
```

If the command returns the parameter value, the policy is working correctly.

## Resuming the Deployment

After the policy has been created and attached to the role, you can resume the deployment process by re-running the deployment script:

```bash
./deploy.sh
```

The script should proceed past the policy creation step and continue with the rest of the deployment.

## Troubleshooting

If you encounter issues:

1. Ensure the user executing the CloudFormation template has administrator privileges
2. Verify the CloudFormation template was not modified
3. Check CloudFormation events for detailed error messages:
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name x-scheduler-iam-policy-stack
   ```
4. Ensure you're operating in the correct AWS region (us-east-1)

For more assistance, contact your AWS administrator or review the AWS CloudFormation documentation.


# IAM Policies for X-Scheduler Application

## Overview

This document provides information about the IAM policies that are automatically created and attached to the EC2 instance role by the CloudFormation template during deployment. These policies grant the necessary permissions for the X-Scheduler application to interact with AWS services like S3, DynamoDB, SSM Parameter Store, and CloudWatch Logs.

## Automated Policy Management

The X-Scheduler deployment now uses a CloudFormation template (`deploy/aws/cloudformation.yaml`) that automatically creates and attaches all required IAM policies. **No manual policy creation is needed.**

## Permissions Included in the CloudFormation Template

The CloudFormation template creates an IAM role with the following permission sets:

### 1. SSM Parameter Store Access
- Allows the EC2 instance to read parameters from the Parameter Store
- Used for storing configuration and secrets

### 2. S3 Bucket Access
- Allows the EC2 instance to upload, download, and delete video files from the S3 bucket
- Essential for handling video content in tweets

### 3. DynamoDB Access
- Allows the EC2 instance to read and write to the DynamoDB table for OAuth token storage
- Required for the OAuth 2.0 PKCE flow with Twitter

### 4. CloudWatch Logs Access
- Allows the EC2 instance to create log groups, log streams, and write log events
- Critical for monitoring and troubleshooting

### 5. SSM Run Command Access
- Allows the instance to receive and execute SSM commands
- Used for remote configuration and management

## Deployment Process

To deploy the X-Scheduler application with all required IAM policies:

1. Create and configure the `deploy/aws/deploy.config` file based on `deploy/aws/deploy.config.example`
2. Run the deployment script:
   ```bash
   ./deploy-to-aws.sh
   ```

The script will:
1. Create the S3 bucket for video storage
2. Create the DynamoDB table for OAuth tokens
3. Deploy the CloudFormation stack that includes the EC2 instance with appropriate IAM role and policies
4. Configure the application on the EC2 instance

## Verifying the Policies

After deployment, you can verify the policies were created correctly:

1. Go to the AWS Management Console
2. Navigate to CloudFormation and select the X-Scheduler stack
3. Go to the "Resources" tab
4. Find the EC2InstanceRole resource and click on its Physical ID to view the role in IAM
5. On the role page, you can see all attached policies

## Troubleshooting

If you encounter permission-related issues:

1. Check the CloudFormation stack's "Events" tab for deployment errors
2. Verify that the EC2 instance has the correct instance profile attached
3. Check the CloudWatch Logs for permission-denied errors
4. Ensure your AWS account has sufficient privileges to create IAM roles and policies

For assistance, contact your AWS administrator or refer to the CloudFormation documentation.


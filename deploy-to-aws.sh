#!/bin/bash

# Simple wrapper script for AWS deployment

echo "Starting X-Scheduler AWS Deployment..."
./deploy/aws/deploy-aws.sh

exit $? 
# Setting Up Monitoring and Notifications for X-Scheduler

This guide will help you set up basic monitoring and notifications for your X-Scheduler EC2 instance.

## 1. CloudWatch Alarms with SNS Notifications

### Step 1: Create an SNS Topic

1. Go to the AWS SNS Console
2. Click "Create topic"
3. Select "Standard" type
4. Name it "x-scheduler-alerts"
5. Click "Create topic"
6. After creation, click "Create subscription"
7. Choose protocol:
   - Email: For email notifications
   - SMS: For text messages
   - HTTP/HTTPS: For webhook integrations
8. Enter your email or phone number
9. Click "Create subscription"
10. Confirm the subscription (check your email if using email)

### Step 2: Create Basic CloudWatch Alarms

#### CPU Usage Alarm

1. Go to the CloudWatch console
2. Click "Alarms" → "All alarms" → "Create alarm"
3. Click "Select metric" → "EC2" → "Per-Instance Metrics"
4. Find your instance (i-04aca3ec6f9a95b52) and select "CPUUtilization"
5. Click "Select metric"
6. Configure the alarm:
   - Statistic: Average
   - Period: 5 minutes
   - Threshold type: Static
   - Condition: Greater than 80%
   - Datapoints to alarm: 3 out of 3
7. Click "Next"
8. Select your SNS topic: "x-scheduler-alerts"
9. Add a name: "X-Scheduler-CPU-Alert"
10. Click "Create alarm"

#### Status Check Alarm

1. Similarly, create another alarm for "StatusCheckFailed"
2. Set it to alert when value is ≥ 1 for 2 consecutive periods of 5 minutes
3. This will notify you if the instance becomes unreachable or unhealthy

## 2. Application Health Check (Optional)

You can create a simple HTTP health check endpoint in your application:

1. Add a route to your application that returns a 200 OK status if everything is working
2. Use Route53 Health Checks or a service like UptimeRobot to monitor this endpoint
3. Configure notifications when the endpoint becomes unavailable

## 3. Mobile Apps for AWS Monitoring

Several mobile apps allow you to monitor your AWS resources:

- AWS Console Mobile Application (official)
- CloudWatch mobile apps (third-party)
- Datadog (if you want more comprehensive monitoring)

## 4. WhatsApp Notifications (via Twilio)

Although AWS doesn't directly integrate with WhatsApp Business API, you can set up:

1. AWS SNS → AWS Lambda → Twilio → WhatsApp
2. CloudWatch Alarm → SNS → Lambda function → Twilio API → WhatsApp message

For a quick setup, services like Twilio can forward SMS notifications to WhatsApp.

## Implementation Notes

- Start with the essential CloudWatch alarms and email/SMS notifications
- Consider more advanced monitoring as your needs grow
- For WhatsApp integration, you'll need a separate Lambda function to handle the Twilio API 
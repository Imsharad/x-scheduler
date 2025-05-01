# X Automation

A minimal Python-based Twitter/X automation pipeline that posts tweets from a simple CSV file.

## Features

- **Minimalist Design**: Extremely lean codebase focused on the essentials
- **CSV Content Source**: Uses a simple CSV file with two columns (tweet, is_posted)
- **Direct Posting**: Posts tweets without additional formatting
- **Flexible Scheduling**: Post at regular intervals or specific times
- **API Compliant**: Respects Twitter API rate limits and terms of service

## Project Structure

```
x-automation/
├── src/                 # All code and data
│   ├── main.py          # Entry point
│   ├── config.py        # Config loader
│   ├── scheduler.py     # Scheduling logic
│   ├── source.py        # CSV content source
│   ├── processor.py     # Content processor
│   ├── poster.py        # Twitter API handler
│   ├── utils.py         # Utilities
│   ├── cfg/             # Configuration files
│   │   └── config.yaml  # Main config
│   ├── dat/             # Data files
│   │   └── curated_content.csv # Content file
│   └── log/             # Log files
├── .gitignore           # Git ignore file
├── README.md            # Documentation
├── run.sh               # Run script
├── deploy.sh            # AWS deployment script
└── requirements.txt     # Dependencies
```

## Local Setup

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the project root with your Twitter API credentials:
   ```
   X_API_KEY=YOUR_API_KEY_HERE
   X_API_KEY_SECRET=YOUR_API_KEY_SECRET_HERE
   X_ACCESS_TOKEN=YOUR_ACCESS_TOKEN_HERE
   X_ACCESS_TOKEN_SECRET=YOUR_ACCESS_TOKEN_SECRET_HERE
   X_BEARER_TOKEN=YOUR_BEARER_TOKEN_HERE
   ```
5. Configure `src/cfg/config.yaml` to set up scheduling
6. Add content to `src/dat/curated_content.csv`

## AWS Deployment

The project includes an automated deployment script for AWS that sets up all necessary infrastructure to run the scheduler 24/7 using:

- **EC2**: Runs the Python application continuously
- **SSM Parameter Store**: Securely stores API credentials
- **IAM Roles**: Properly configured permissions for security

### Prerequisites for AWS Deployment

1. **AWS CLI**: Install and configure with appropriate credentials 
   ```
   pip install awscli
   aws configure
   ```
2. **jq**: Required for JSON parsing in the deployment script
   ```
   # MacOS
   brew install jq
   
   # Ubuntu/Debian
   sudo apt install jq
   
   # Amazon Linux/RHEL/CentOS
   sudo yum install jq
   ```
3. **Git Repository**: Push your code to a Git repository that EC2 can access
   - Make sure your code uses the updated version of `config.py` that supports SSM

### Deployment Steps

1. **Customize deployment configuration:**
   Edit the beginning of `deploy.sh` to set your AWS region, repository URL, and other parameters:
   ```bash
   # --- CONFIGURATION ---
   AWS_REGION="us-east-1" # Change to your desired AWS region
   GIT_REPO_URL="https://github.com/YOUR_USERNAME/X-scheduler.git" # Set your repo URL
   # ... other configurations
   ```

2. **Run the deployment script:**
   ```bash
   ./deploy.sh
   ```
   
   The script will:
   - Create necessary IAM policies and roles
   - Configure security groups
   - Securely store your Twitter API credentials in SSM Parameter Store
   - Launch an EC2 instance with proper permissions
   - Set up a systemd service to keep your application running 24/7
   - Output connection information when complete

3. **Connect to the EC2 instance if needed:**
   ```bash
   ssh -i x-scheduler-key-[timestamp].pem ec2-user@[instance-ip]
   ```

4. **Monitor the application logs:**
   ```bash
   # View systemd service logs
   sudo journalctl -u x-scheduler.service -f
   
   # View application logs
   tail -f /home/ec2-user/x-scheduler/src/log/pipeline.log
   ```

### Updating the Deployed Application

When you need to update the application:

1. Push changes to your Git repository
2. SSH into the EC2 instance
3. Run the following commands:
   ```bash
   cd /home/ec2-user/x-scheduler
   git pull
   sudo systemctl restart x-scheduler.service
   ```

## Configuration

The `src/cfg/config.yaml` file controls the application:

```yaml
# Content source
content_csv_path: "src/dat/curated_content.csv"
content_format: "csv"

# Scheduling
schedule:
  mode: "interval"  # interval or specific_times
  interval_minutes: 240  # post every 4 hours
  specific_times:  # used when mode is specific_times
    - "09:00"
    - "17:00"
    - "21:00"

# Logging
logging:
  file_path: "src/log/pipeline.log"
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Content CSV Format

The curated content CSV file has a minimal structure:
- `tweet`: The content to be tweeted
- `is_posted`: Set to 'true' if already posted (updated automatically)

Example:
```csv
tweet,is_posted
Five Ways to Improve Your Workflow,false
The Future of AI in Marketing,false
```

## Local Usage

Run the pipeline locally:

```bash
./run.sh
# OR with debug logging:
./run.sh --debug
```

## Running Locally in the Background

### Linux/Mac:
```
nohup ./run.sh > /dev/null 2>&1 &
```

### Windows:
Use Task Scheduler to run the script at system startup.

## Important Notes

- This is a minimal project designed for simplicity
- Make sure your Twitter API credentials have the necessary permissions
- Always respect Twitter's terms of service and rate limits
- The AWS deployment uses the free tier for the first 12 months ($0), then costs approximately $8-12/month after that period 
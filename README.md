# X-Scheduler: Automated Twitter/X Content Publishing

X-Scheduler is a Python-based tool for automated content curation and scheduled posting to X (formerly Twitter). It allows you to set up scheduled tweets from various content sources including Google Sheets integration for easy content management. Now supports video uploads with OAuth 2.0 authentication!

## Features

- Schedule tweets at specific times or intervals
- Support for multiple content sources (Google Sheets, local files)
- **Video upload support:** Handles chunked uploads, downloads from URLs (`video_url`), and uses AWS S3 for temporary storage.
- **OAuth 2.0 PKCE authentication:** Securely connects to the X API for video uploads and other v2 endpoints.
- Customizable content templates
- Automatic hashtag generation
- Rate limiting and retry logic
- AWS deployment support (EC2, CloudFormation, S3, DynamoDB)
- Session Manager integration for secure instance access

## Project Structure

```
x-scheduler/
├── src/                     # Core source code
│   ├── main.py              # Main execution script
│   ├── scheduler.py         # Sets up and runs the scheduling logic
│   ├── poster.py            # Handles interaction with the X API
│   ├── oauth.py             # OAuth 2.0 authentication for video uploads
│   ├── google_sheet_source.py # Google Sheets integration
│   ├── source.py            # Content source base and implementations
│   ├── processor.py         # Content processing utilities
│   ├── utils.py             # Utility functions (logging, retry logic)
│   └── cfg/                 # Configuration directory
├── config/                  # Configuration files
│   └── google-credentials.json # Google API credentials
├── deploy/                  # Deployment tools
│   ├── aws/                 # AWS deployment scripts
│   │   ├── deploy-aws.sh    # Main AWS deployment script
│   │   ├── update-aws-deployment.sh # Update existing deployment
│   │   └── session-manager/ # Session Manager setup tools
│   └── keys/                # Directory for deployment keys
├── deploy-to-aws.sh         # Simple wrapper for AWS deployment
├── requirements.txt         # Python dependencies
├── Dockerfile               # Docker container definition
├── docker-compose.yml       # Docker composition for local development
└── README.md               # Documentation
```

## Installation and Setup

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/x-scheduler.git
   cd x-scheduler
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Configure your X API credentials by creating a `.env` file based on the provided example.

4. Run the application:
   ```bash
   python src/main.py
   ```

### Docker Deployment

1. Build and run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

### AWS Deployment

For AWS deployment, use the provided deployment script:

```bash
./deploy-to-aws.sh
```

This will:
1. Set up required AWS infrastructure (EC2, IAM roles, etc.)
2. Deploy your application to an EC2 instance
3. Configure AWS Systems Manager for secure instance access

## Configuration

### X (Twitter) API Credentials

You'll need to obtain API credentials from the [X Developer Portal](https://developer.twitter.com):
- API Key and Secret
- Access Token and Secret
- OAuth 2.0 Client ID and Secret (for video uploads)

These can be stored in your `.env` file or as AWS SSM parameters for secure deployment.

### Content Sources

X-Scheduler supports multiple content sources:

1. **Google Sheets** (Recommended)
   - Easy to manage content collaboratively
   - Set up by providing Google Sheet ID and credentials (`config/google-credentials.json`).
   - Supports video content by providing:
       - An S3 path to a pre-uploaded video (`s3://bucket-name/path/to/video.mp4`).
       - A direct URL to a video (`video_url` column) which will be downloaded using `yt-dlp`, validated, and uploaded.
   - Requires columns like `text`, `scheduled_time`, and optionally `video_path` or `video_url`.

2. **Local File**
   - CSV format with content entries (e.g., `data/curated_content.csv`).
   - Suitable for simpler use cases or testing.
   - Supports video content via a `video_path` column specifying a local file path accessible to the script/container.

## Video Upload Feature

X-Scheduler now supports uploading videos to Twitter using the chunked upload process via the X API v2:

1. **Authentication:** Video uploads require OAuth 2.0 PKCE authentication. You must run the one-time setup:
    ```bash
    # If running locally
    python -m src.main --setup-oauth

    # If running in Docker (ensure port 5000 is mapped)
    docker exec <container_id_or_name> python -m src.main --setup-oauth
    ```
    This starts a temporary web server (usually on port 5000) to guide you through the browser-based X authorization flow. Follow the prompts in your terminal and browser. Credentials (refresh tokens) are securely stored (e.g., in DynamoDB for AWS deployments).
    
    > **Important**: The OAuth flow must request the `media.write` scope in addition to the standard scopes. This is critical for video uploads and prevents 403 Forbidden errors. The application handles this automatically, but custom implementations must include this scope.

2. **Providing Videos:**
    * **Direct Upload (Testing):** Use the `--upload-video` flag with a local path:
        ```bash
        python -m src.main --upload-video /path/to/video.mp4 --video-tweet "Check out this test video!"
        ```
    * **Google Sheets:** Add a `video_url` column with a link (e.g., YouTube, Twitter) or a `video_path` column with an S3 URI (`s3://...`). The scheduler will automatically download (if URL), validate, upload to S3 (if needed), and then post the video with the associated text.
    * **Local File Source:** Add a `video_path` column with the path to the video file (must be accessible within the execution environment/container).

3. **Workflow:**
    * If a `video_url` is provided, `yt-dlp` downloads the video.
    * The video is validated against X's requirements (format, size, duration).
    * The validated video is uploaded to a configured AWS S3 bucket for temporary storage.
    * The chunked upload process (INIT, APPEND, FINALIZE) posts the video from S3 to X.
    * The tweet is posted with the attached `media_id`.
    * The temporary video file is cleaned up from S3.

### Video Requirements
(Refer to X API documentation for the most up-to-date limits)
- Generally supports MP4 and MOV on web.
- Max file size: 512MB (though often lower limits like 15MB apply depending on client/API version used - the code *should* handle larger files via chunking, but X may impose other limits).
- Max duration: 140 seconds (2 minutes and 20 seconds).

## Accessing Your Deployed Instance

After deployment to AWS, access your instance through AWS Systems Manager Session Manager:

```bash
aws ssm start-session --target i-xxxxxxxxxxxxxxxxx --region us-east-1
```

For more details, see the [Session Manager documentation](deploy/aws/session-manager/README.md).

## License

[MIT License](LICENSE) 
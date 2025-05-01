**MEGA-PROMPT START**

**Project Goal:** Create a complete Python-based Twitter (X) automation pipeline designed for organic, low-cost, continuous operation focused on maximizing reach and generating leads. This is an MVP ("Minimum Viable Product") project embodying the "move fast and break things" philosophy, meaning prioritize core functionality, use simple and readily available tools, iterate quickly, and avoid over-engineering initially. However, **strict adherence to the X API's Terms of Service, usage policies, and rate limits is non-negotiable.** The entire output should be a well-structured project repository with functional Python code.

**Core Philosophy:**
1.  **Cost Optimization:** Utilize free or very low-cost services and libraries. Avoid paid APIs (beyond potential basic X API access if required) or expensive hosting solutions for the MVP. Think local execution, cron jobs on existing servers, or potentially free tiers of serverless functions.
2.  **Reach Maximization (Organic):** Focus on consistent posting of valuable content, potentially leveraging relevant hashtags, and structuring tweets for engagement. Interaction features (likes, replies) are secondary for MVP but can be considered for future expansion.
3.  **Lead Generation:** Integrate mechanisms to drive traffic to a target destination (website, landing page, profile) through calls-to-action (CTAs) within the tweets. Tracking is basic for MVP (e.g., UTM parameters).
4.  **Automation & Continuous Operation:** The system should run autonomously based on a schedule, requiring minimal manual intervention once set up.
5.  **MVP Focus ("Move Fast"):** Implement the essential features first: content sourcing, basic processing, scheduling, and posting. Get it working, then iterate.

**Target Audience for Generated Tweets:** (You might want to specify this more, but let's assume a general tech/marketing/entrepreneur audience for now). The system should be configurable for different target audiences later.

**Key Functionality Requirements (MVP):**

1.  **Configuration Management:**
    * Use environment variables (`.env` file) for sensitive data (X API Keys/Tokens: API Key, API Key Secret, Access Token, Access Token Secret, Bearer Token if needed). Provide a `.env.example` file.
    * Use a configuration file (e.g., `config.yaml` or `config.py`) for non-sensitive settings: RSS feed URLs, keyword lists for content filtering/hashtag generation, scheduling frequency/times, target URLs for CTAs, tweet templates, etc.
2.  **Content Sourcing:**
    * Implement modular content sources.
    * **MVP Source 1: RSS Feeds:** Read specified RSS feeds, extract article titles and links. Handle potential errors during feed fetching/parsing.
    * **MVP Source 2: Curated Content File:** Read from a simple file (e.g., `data/curated_content.csv` or `data/curated_content.json`) containing pre-written tweet text or links/ideas. The script should pick one entry, use it, and potentially mark it as used or remove it.
    * *Structure:* Create an abstract base class or clear interface for content sources, making it easy to add new types later (e.g., scraping, AI generation).
3.  **Content Processing & Formatting:**
    * **Templating:** Use basic templates to structure tweets. Example: "[Content Title/Snippet] [Link] #[RelevantHashtag1] #[RelevantHashtag2] [Optional CTA]".
    * **Text Shortening/Summarization (Basic):** If content (like an article title) is too long for a tweet (considering URL length and hashtags), implement a *simple* truncation method (e.g., truncate to a certain character limit, add "..."). Advanced summarization is out of scope for MVP.
    * **Hashtag Generation (Basic):** Append 1-3 relevant hashtags. These could be predefined in `config`, potentially chosen based on keywords found in the content title, or a mix.
    * **URL Handling:** Ensure URLs are included. Consider integrating a simple URL shortener *if* a free, reliable API exists (e.g. bit.ly has free tier but requires setup) - otherwise, just use the full URL. X automatically shortens URLs with t.co, so this might be unnecessary complexity for MVP. Ensure UTM parameters (defined in `config`) are appended to URLs for basic tracking.
    * **Call-to-Action (CTA):** Optionally append a predefined CTA from the configuration file to some tweets (e.g., "Read more on our blog:", "Check out our tool:").
4.  **Scheduling:**
    * Implement a robust scheduling mechanism. Use libraries like `schedule` or `APScheduler`.
    * Allow configuration of posting frequency (e.g., "every 4 hours", "at 9:00 AM and 5:00 PM daily").
    * Implement a simple queue mechanism (even an in-memory list or a temporary file is fine for MVP) to hold generated tweets ready for posting. This prevents generating the exact same tweet repeatedly if content sources are slow to update and helps manage rate limits.
    * Ensure the scheduler runs persistently (guidance in README on how to run it - e.g., `python scheduler.py` potentially within `screen` or `nohup`, or via cron).
5.  **Posting to X (Twitter):**
    * Use a reliable Python library for interacting with the X API v2 (preferred). `tweepy` is a common choice, but ensure compatibility with the latest API version and authentication methods (OAuth 1.0a or OAuth 2.0).
    * Handle API authentication securely using keys from the `.env` file.
    * Implement the function to post a tweet (text content).
    * Include basic error handling: Log API errors, handle rate limits gracefully (e.g., wait and retry if appropriate, log the issue, skip the tweet if fatal). Do **NOT** violate rate limits.
6.  **Logging:**
    * Implement logging using Python's built-in `logging` module.
    * Log key events: script startup/shutdown, fetching content (success/failure), generating tweets, posting tweets (success/failure), API errors, rate limit warnings.
    * Configure logging to output to both the console and a file (e.g., `logs/pipeline.log`).
7.  **Basic Lead/Reach Tracking (Conceptual for MVP):**
    * The core mechanism is UTM parameters added to URLs.
    * The README should mention that tracking effectiveness requires analyzing website analytics (e.g., Google Analytics) filtered by these UTM parameters. No in-pipeline analytics needed for MVP.

**Technology Stack:**

* **Language:** Python 3.9+
* **Key Libraries:**
    * `requests` (for fetching RSS/web content)
    * `feedparser` (for parsing RSS feeds)
    * `tweepy` (or alternative stable X API v2 library)
    * `python-dotenv` (for loading `.env` files)
    * `PyYAML` (if using YAML for config) or standard Python modules if using `.py` config.
    * `schedule` or `APScheduler` (for scheduling tasks)
    * Standard libraries: `logging`, `json`, `csv`, `datetime`, `os`, `time`.
* **Data Storage (MVP):** Simple files (JSON, CSV) for curated content, potentially a text file for queue/state if needed. No database required for MVP.

**Project Structure (Directory Tree):**

```
twitter-automation-pipeline/
├── src/                     # Core source code
│   ├── __init__.py
│   ├── main.py              # Main execution script (can be triggered by scheduler)
│   ├── config_loader.py     # Loads config from .env and config file
│   ├── content_sources/     # Module for different content sources
│   │   ├── __init__.py
│   │   ├── base_source.py   # (Optional) Abstract base class for sources
│   │   ├── rss_source.py    # Implementation for RSS feeds
│   │   └── file_source.py   # Implementation for curated file source
│   ├── content_processor.py # Handles templating, hashtagging, shortening, CTAs, UTMs
│   ├── scheduler.py         # Sets up and runs the scheduling logic (using main.py or directly calling functions)
│   ├── twitter_poster.py    # Handles interaction with the X API (posting tweets)
│   └── utils.py             # Utility functions (e.g., logging setup, simple retry logic)
├── config/                  # Configuration files
│   ├── config.yaml          # Main configuration (or config.py)
│   └── .env.example         # Example environment variables file
├── data/                    # Data files used/generated by the pipeline
│   ├── curated_content.csv  # Example curated content file (or .json)
│   └── processed_log.txt    # (Optional) Simple log of processed items to avoid duplicates
├── logs/                    # Log files generated by the application
│   └── pipeline.log         # Main log file (ensure .gitignore includes this dir)
├── scripts/                 # Helper scripts (optional, e.g., setup, initial config)
│   └── setup_env.sh         # (Optional) Script to help create .env
├── tests/                   # Unit/Integration tests (Basic structure, implementation optional for strict MVP)
│   ├── __init__.py
│   └── test_content_processor.py # Example test file
├── .gitignore               # Git ignore file (include .env, logs/, __pycache__, venv/, etc.)
├── README.md                # Project documentation
└── requirements.txt         # Python dependencies
```

**Detailed Instructions for AI:**

1.  **Generate the Project Structure:** Create all the directories and empty files (`__init__.py`, etc.) as specified above.
2.  **Generate `requirements.txt`:** List all the Python libraries mentioned in the Technology Stack with reasonable version specifiers (e.g., `requests>=2.25.0`).
3.  **Generate `.gitignore`:** Create a standard Python `.gitignore` file, making sure to include `.env`, `logs/`, `data/` (if generated data shouldn't be committed), `__pycache__/`, `*.pyc`, and any virtual environment directories (like `venv/`, `.venv/`).
4.  **Generate `.env.example`:** Create this file listing the required environment variables for X API keys/tokens without actual values (e.g., `X_API_KEY=YOUR_API_KEY_HERE`).
5.  **Generate `config/config.yaml` (or `config.py`):** Create a sample configuration file. Include sections for:
    * `rss_feeds`: A list of URLs.
    * `curated_content_file`: Path to the data file.
    * `schedule_settings`: Posting frequency/times (e.g., `post_interval_minutes: 240` or specific times `post_times: ["09:00", "17:00"]`).
    * `tweet_templates`: A list of template strings (e.g., `"{title} {url} #Tech #News {cta}"`).
    * `hashtags`: Default hashtags, maybe keywords for dynamic hashtag selection.
    * `cta_messages`: A list of call-to-action strings.
    * `utm_parameters`: Dictionary of UTM tags (e.g., `utm_source: twitter_pipeline`, `utm_medium: social_organic`).
    * `character_limit`: Max characters for generated text part of the tweet.
6.  **Generate `src/config_loader.py`:** Write Python code to load settings from `.env` using `python-dotenv` and from `config.yaml` (using `PyYAML`) or `config.py`. Provide easy access to configuration values.
7.  **Generate `src/utils.py`:** Include a function to set up the `logging` module as described (console and file output). Maybe include a simple decorator or function for retrying actions (like API calls) with delays.
8.  **Generate `src/content_sources/` files:**
    * `rss_source.py`: Implement a class/functions to fetch feeds using `requests` and parse them using `feedparser`. Return a list of potential content items (e.g., dicts with `title` and `link`). Include error handling.
    * `file_source.py`: Implement reading from the specified CSV/JSON file. Handle reading, selecting an item, and potentially marking it as used (simplest: just read sequentially or randomly; slightly better: keep track of used indices/items in a separate state file or remove from the source file - choose a simple MVP approach).
    * (Optional `base_source.py`: Define an abstract class if you want to enforce a common interface).
9.  **Generate `src/content_processor.py`:** Write a function/class that takes raw content (e.g., title, link) and applies the processing logic: selects a template, inserts content, truncates if necessary, adds hashtags (based on config/keywords), adds UTM parameters to the URL, potentially adds a CTA. Return the final tweet text ready for posting. Ensure it respects character limits (approximating t.co URL length).
10. **Generate `src/twitter_poster.py`:**
    * Implement a class `TwitterPoster`.
    * In its `__init__`, handle authentication using `tweepy` and API keys loaded via `config_loader`.
    * Implement a `post_tweet(text)` method. This method should use the `tweepy` client to post the tweet.
    * Include `try...except` blocks to catch API errors (e.g., `TweepyException`). Log errors. Implement basic rate limit handling logic (e.g., check headers if possible, or catch specific rate limit exceptions and wait/log).
11. **Generate `src/scheduler.py`:**
    * Use the `schedule` library (or `APScheduler`).
    * Load the schedule configuration from the config file.
    * Define the main job function(s) that will:
        * Call content source modules to get potential content.
        * Select one piece of content (avoiding immediate duplicates if possible - maybe check a small in-memory cache or the log file).
        * Call the `content_processor` to generate the tweet text.
        * (Optional Queue): Add the generated tweet to a simple queue.
        * Have another scheduled job (or the same one) pull from the queue and call `twitter_poster.post_tweet()`.
    * Include the standard `while True: schedule.run_pending(); time.sleep(1)` loop (for `schedule` library) or the `scheduler.start()` logic (for `APScheduler`).
    * Ensure logging is used throughout.
12. **Generate `src/main.py`:** This could be a simple entry point that perhaps orchestrates a single run of fetching, processing, and posting (useful for testing or manual runs), or it could be the script that the `scheduler.py` imports functions from. Alternatively, `scheduler.py` itself can be the main runnable script. Choose the simpler approach: make `scheduler.py` the main entry point to run the pipeline continuously. `main.py` could remain minimal or be used for single-shot test runs.
13. **Generate `README.md`:** Create a comprehensive README explaining:
    * Project purpose.
    * How to set up (clone repo, create virtual environment, install requirements, create `.env` from `.env.example` and fill in keys, configure `config.yaml`).
    * How to run the pipeline (`python src/scheduler.py`).
    * How to run in the background (suggestions like `nohup`, `screen`, `systemd`, or `cron`).
    * Explanation of the configuration options.
    * How lead tracking works (via UTM and external analytics).
    * Mentioning the importance of respecting X API rules and rate limits.
    * Potential future enhancements (AI content gen, interaction bots, advanced analytics, web UI).
14. **Code Quality:** Ensure generated Python code follows basic PEP 8 style guidelines, includes docstrings for major functions/classes, and comments where logic is complex. Prioritize functionality and clarity over complex design patterns for MVP.

**Final Output:** Provide the complete file structure and the full code content for each specified `.py`, `.yaml`, `.md`, `.txt`, `.gitignore`, and `.env.example` file. Ensure the code is runnable assuming the user installs requirements and provides API keys.

**MEGA-PROMPT END**
# Project Configuration (LTM)

*This file contains the stable, long-term context for the project.*
*It should be updated infrequently, primarily when core goals, tech, or patterns change.*

---

## Core Goal

Create a minimal Python-based Twitter (X) automation pipeline that posts tweets based on a simple curated CSV file. Follows an extremely lean design philosophy while strictly adhering to X API's Terms of Service, usage policies, and rate limits.

---

## Tech Stack

*   **Language:** Python 3.9+
*   **Twitter API:** tweepy
*   **Configuration:** python-dotenv, PyYAML
*   **Scheduling:** schedule
*   **Standard Libraries:** logging, csv, os, time
*   **Data Storage:** Simple CSV file for curated content

---

## Critical Patterns & Conventions

*   **Project Structure:** Flat, minimal organization with essential files only
*   **Content Source:** Direct CSV file handling with two columns (tweet, is_posted)
*   **Error Handling:** Basic try-except blocks with logging
*   **Configuration:** Environment variables for sensitive data, YAML for application settings
*   **Rate Limiting:** Adherence to Twitter API rate limits
*   **Logging:** Basic logging throughout the application

---

## Key Constraints

*   **Simplicity:** Keep the codebase as lean and minimal as possible
*   **API Compliance:** Strict adherence to X API's Terms of Service, usage policies, and rate limits
*   **Minimal Dependencies:** Minimal external libraries
*   **Local Execution:** Design for running on local machines or existing servers

---

## Tokenization Settings

*   **Estimation Method:** Character-based
*   **Characters Per Token (Estimate):** 4 
"""
Main entry point for the X Automation Scheduler.
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import scheduler
from src.scheduler import TweetScheduler


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='X Automation Scheduler')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    return parser.parse_args()


def main():
    """Run the scheduler."""
    args = parse_args()
    scheduler = TweetScheduler(debug=args.debug)
    scheduler.run()


if __name__ == "__main__":
    main() 
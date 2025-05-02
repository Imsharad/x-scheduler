#!/bin/bash

# Simple Twitter Automation Run Script

# Default settings
DEBUG_MODE="false"

# Help function
show_help() {
    echo "X Automation Run Script"
    echo
    echo "Usage: ./run.sh [options]"
    echo
    echo "Options:"
    echo "  --debug      Enable debug logging"
    echo "  --help       Show this help message"
    echo
    echo "Example: ./run.sh --debug"
    echo
}

# Parse arguments
for arg in "$@"; do
    case $arg in
        --debug)
            DEBUG_MODE="true"
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            # Unknown option
            echo "Unknown option: $arg"
            show_help
            exit 1
            ;;
    esac
done

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then # Support for Windows Git Bash/WSL
    source venv/Scripts/activate
else
    echo "Error: Virtual environment not found. Please create it first."
    exit 1
fi

# Run the application scheduler
if [ "$DEBUG_MODE" = "true" ]; then
    echo "Running in debug mode"
    python src/main.py --debug
else
    echo "Running scheduler"
    python src/main.py
fi

# Deactivate virtual environment
deactivate 
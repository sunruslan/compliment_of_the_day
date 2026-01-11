#!/usr/bin/env python3
"""
Simple test script to generate a compliment for a given date and language.
Usage:
    python test_compliment.py --date 2024-01-15 --language en
    python test_compliment.py --date 2024-01-15 --language ru
    python test_compliment.py --language en  # Uses today's date
"""

import argparse
from setup import setup_application, get_logger
from compliment import ComplimentGenerator
from news import FreshHeadlinesRetriever

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a compliment for a given date and language"
    )
    parser.add_argument(
        "--language",
        type=str,
        choices=["en", "ru"],
        default="en",
        help="Language code (default: en)",
    )

    args = parser.parse_args()

    # Setup application
    setup_application()

    logger.info(f"Generating compliment for language: {args.language}")

    # Initialize components
    news_client = FreshHeadlinesRetriever()
    generator = ComplimentGenerator(news_client, language=args.language)

    # Generate compliment
    compliment = generator.generate_compliment_for_date()

    if compliment:
        print(f"\n{'=' * 60}")
        print(f"Language: {args.language}")
        print(f"{'=' * 60}")
        print(f"Compliment:\n{compliment}")
        print(f"{'=' * 60}\n")

    else:
        logger.error("Failed to generate compliment")
        print("Failed to generate compliment. Check logs for details.")


if __name__ == "__main__":
    main()

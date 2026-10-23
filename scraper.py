"""v2's entry point (spec §4): python scraper.py (--live | --offline DIR) --out DIR …;
see elections_calendar.__main__.
"""

import sys

from elections_calendar.__main__ import main

if __name__ == "__main__":
    sys.exit(main())

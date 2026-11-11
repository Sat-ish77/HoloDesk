"""Start the always-on HoloDesk daemon:  python run_daemon.py"""

import sys

from service.daemon import main

if __name__ == "__main__":
    sys.exit(main())

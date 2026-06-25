from __future__ import annotations

import sys

from catchup.server.debug import search_probe as _search_probe

# Compatibility module for tests and callers that still patch
# catchup.server.debug.api while the implementation lives in search_probe.
sys.modules[__name__] = _search_probe

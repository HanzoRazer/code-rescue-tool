"""Import all checker modules so that ``__init_subclass__`` auto-registration fires."""

from . import structural      # noqa: F401
from . import components       # noqa: F401
from . import patterns         # noqa: F401
from . import runtime          # noqa: F401
from . import security         # noqa: F401
from . import quality          # noqa: F401
from . import frontend         # noqa: F401

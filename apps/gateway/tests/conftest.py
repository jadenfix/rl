"""Keep gateway tests independent of production inference credentials."""
import os

os.environ["GATEWAY_USE_STUB_BACKEND"] = "true"

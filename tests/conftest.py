import os
import tempfile

# TEST_DATABASE_URL permite probar contra Postgres; por defecto usa SQLite temporal.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["MCP_TOKEN"] = "t" * 32

import os
import pathlib
import tempfile

os.environ["LLM_PROVIDER"] = "fake"
os.environ["USE_MOCK"] = "true"
os.environ["USE_EMBEDDINGS"] = "false"
os.environ["INDEX_DIR"] = tempfile.mkdtemp(prefix="dam_index_")
os.environ["ADMIN_TOKEN"] = ""
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

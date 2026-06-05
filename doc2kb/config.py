import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent

# Load .env from the project root (silently ignored if absent)
load_dotenv(BASE_DIR / ".env")

# Output root: override with DOC2KB_OUTPUT_DIR in .env or as env var.
# Default: <repo>/output
OUTPUT_DIR = Path(os.environ.get("DOC2KB_OUTPUT_DIR", BASE_DIR / "output"))

VAULT_DIR = OUTPUT_DIR / "obsidian_vault"
ATTACHMENTS_DIR = VAULT_DIR / "attachments"
CHROMA_DIR = OUTPUT_DIR / "chroma_db"

COLLECTION_NAME = "knowledge_base"
EMBED_MODEL = "all-MiniLM-L6-v2"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
OCR_CONFIDENCE_THRESHOLD = 0.75
OCR_DEFAULT_LANGS = ["en"]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".gif", ".webp"}

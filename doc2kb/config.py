from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
VAULT_DIR = BASE_DIR / "output" / "obsidian_vault"
ATTACHMENTS_DIR = VAULT_DIR / "attachments"
CHROMA_DIR = BASE_DIR / "output" / "chroma_db"

COLLECTION_NAME = "knowledge_base"
EMBED_MODEL = "all-MiniLM-L6-v2"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
OCR_CONFIDENCE_THRESHOLD = 0.75
OCR_DEFAULT_LANGS = ["en"]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".gif", ".webp"}

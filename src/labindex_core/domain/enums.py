"""
Enumerations for LabIndex domain.
"""

from enum import Enum, auto


class FileCategory(str, Enum):
    """Categories for file classification."""
    DATA = "data"           # ABF, SMRX, EDF, MAT, NPZ, etc.
    DOCUMENTS = "documents"  # DOCX, PDF, TXT, MD
    SPREADSHEETS = "spreadsheets"  # XLSX, CSV
    IMAGES = "images"       # PNG, JPG, TIFF
    CODE = "code"           # PY, M, R, IPYNB
    SLIDES = "slides"       # PPTX, PPT
    VIDEO = "video"         # MP4, AVI
    ARCHIVES = "archives"   # ZIP, TAR, GZ
    OTHER = "other"

    @classmethod
    def from_extension(cls, ext: str) -> "FileCategory":
        """Determine category from file extension."""
        ext = ext.lower().lstrip(".")

        CATEGORY_MAP = {
            # Data files
            "abf": cls.DATA, "smrx": cls.DATA, "smr": cls.DATA,
            "edf": cls.DATA, "mat": cls.DATA, "npz": cls.DATA,
            "npy": cls.DATA, "h5": cls.DATA, "hdf5": cls.DATA,
            "nwb": cls.DATA, "tdms": cls.DATA,
            # Documents
            "docx": cls.DOCUMENTS, "doc": cls.DOCUMENTS,
            "pdf": cls.DOCUMENTS, "txt": cls.DOCUMENTS,
            "md": cls.DOCUMENTS, "rtf": cls.DOCUMENTS,
            # Spreadsheets
            "xlsx": cls.SPREADSHEETS, "xls": cls.SPREADSHEETS,
            "csv": cls.SPREADSHEETS,
            # Images
            "png": cls.IMAGES, "jpg": cls.IMAGES, "jpeg": cls.IMAGES,
            "tif": cls.IMAGES, "tiff": cls.IMAGES, "gif": cls.IMAGES,
            "bmp": cls.IMAGES, "svg": cls.IMAGES,
            # Code
            "py": cls.CODE, "m": cls.CODE, "r": cls.CODE,
            "ipynb": cls.CODE, "js": cls.CODE, "json": cls.CODE,
            # Slides
            "pptx": cls.SLIDES, "ppt": cls.SLIDES,
            # Video
            "mp4": cls.VIDEO, "avi": cls.VIDEO, "mov": cls.VIDEO,
            "mkv": cls.VIDEO, "wmv": cls.VIDEO,
            # Archives
            "zip": cls.ARCHIVES, "tar": cls.ARCHIVES, "gz": cls.ARCHIVES,
            "7z": cls.ARCHIVES, "rar": cls.ARCHIVES,
        }

        return CATEGORY_MAP.get(ext, cls.OTHER)


class IndexStatus(str, Enum):
    """Status of a file's indexing progress."""
    PENDING = "pending"         # Not yet processed
    INVENTORY_OK = "inventory_ok"  # Tier 0 complete
    EXTRACT_OK = "extract_ok"   # Tier 1/2 complete
    LLM_OK = "llm_ok"           # Tier 3 complete
    ERROR = "error"             # Processing failed
    SKIPPED = "skipped"         # Intentionally not processed


class EdgeType(str, Enum):
    """Types of relationships between files."""
    NOTES_FOR = "notes_for"       # Document describes a data file
    ANALYSIS_OF = "analysis_of"   # Analysis/figure from data
    SAME_ANIMAL = "same_animal"   # Same animal ID
    SAME_SESSION = "same_session" # Same recording session
    HISTOLOGY_FOR = "histology_for"  # Histology image for animal
    SURGERY_NOTES = "surgery_notes"  # Surgery notes for animal
    SIBLING = "sibling"           # Same parent folder
    MENTIONS = "mentions"         # Soft link (text mentions)


class JobStatus(str, Enum):
    """Status of a background job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CandidateStatus(str, Enum):
    """Status of a candidate edge in the review workflow."""
    PENDING = "pending"       # Awaiting review
    ACCEPTED = "accepted"     # User/auditor accepted, promoted to edge
    REJECTED = "rejected"     # User/auditor rejected
    NEEDS_AUDIT = "needs_audit"  # Flagged for LLM auditor review


class AuditVerdict(str, Enum):
    """Verdict from LLM link auditor."""
    ACCEPT = "accept"         # Link is valid
    REJECT = "reject"         # Link is invalid
    NEEDS_MORE_INFO = "needs_more_info"  # Inconclusive, needs context


class ArtifactType(str, Enum):
    """Types of sub-document artifacts for evidence anchoring."""
    TEXT_SPAN = "text_span"       # Line range in text file
    TABLE_CELL = "table_cell"     # Specific cell in spreadsheet
    TABLE_ROW = "table_row"       # Entire row in spreadsheet
    PPT_SLIDE = "ppt_slide"       # Slide in PowerPoint
    IPYNB_CELL = "ipynb_cell"     # Cell in Jupyter notebook
    PDF_PAGE = "pdf_page"         # Page in PDF document

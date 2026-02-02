"""
Context-Aware File Reader.

This service provides intelligent file reading with context windows
around found references. It combines:
1. Handler-based reference detection
2. Configurable context windows (N lines before/after)
3. Metadata extraction from surrounding context
4. Optional LLM-assisted context understanding

Key Concept: When a reference is found (e.g., "000.abf"), we don't just
note the reference - we capture and analyze the surrounding text to
understand the relationship between files.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

from .handlers import (
    HandlerRegistry,
    ReferenceContext,
    create_default_registry,
)
from ..domain.models import FileRecord, ContentRecord
from ..domain.enums import IndexStatus
from ..ports.db_port import DBPort
from ..ports.llm_port import LLMPort


@dataclass
class LinkVerification:
    """Result of verifying a potential link between files."""
    is_valid: bool
    confidence: float
    rationale: str
    extracted_metadata: Dict[str, Any] = field(default_factory=dict)
    evidence_snippets: List[str] = field(default_factory=list)


@dataclass
class FileContext:
    """
    Complete context for a file, including all references it makes.
    """
    file: FileRecord
    content: Optional[ContentRecord]
    handler_name: str
    metadata: Dict[str, Any]
    references: List[ReferenceContext]
    relationship_hints: List[str]


class ContextReader:
    """
    Context-aware file reader service.

    Provides methods for:
    1. Finding references in files with surrounding context
    2. Verifying relationships between files
    3. Extracting metadata from context
    4. LLM-assisted context understanding (optional, budget-limited)
    """

    # Default context window size
    DEFAULT_CONTEXT_LINES = 20

    # LLM prompt for context understanding
    CONTEXT_UNDERSTANDING_PROMPT = """You are analyzing context around a file reference to understand the relationship.

## Source File
**Name**: {src_name}
**Path**: {src_path}

## Reference Found
**Reference Text**: {reference}
**Reference Type**: {ref_type}

## Context (lines around the reference)
```
{context}
```

## Extracted Metadata (from pattern matching)
{metadata}

## Task
Analyze this context and answer:
1. Is this a genuine reference to a data file, or noise (page number, coincidental match)?
2. What is the relationship being described? (notes about, protocol for, analysis of, etc.)
3. What additional metadata can you extract from the context?

Return ONLY a valid JSON object:
{{
    "is_genuine_reference": true/false,
    "relationship_type": "notes_for" | "protocol_for" | "analysis_of" | "mentions" | "unrelated",
    "confidence": 0.0-1.0,
    "rationale": "brief explanation",
    "additional_metadata": {{"key": "value", ...}}
}}
"""

    def __init__(
        self,
        db: DBPort,
        llm: Optional[LLMPort] = None,
        registry: Optional[HandlerRegistry] = None,
        llm_budget: int = 50,
    ):
        """
        Initialize the context reader.

        Args:
            db: Database port for file access
            llm: Optional LLM port for assisted understanding
            registry: Handler registry (creates default if None)
            llm_budget: Maximum LLM calls per session (default 50)
        """
        self.db = db
        self.llm = llm
        self.registry = registry or create_default_registry()
        self.llm_budget = llm_budget
        self._llm_calls_made = 0

    @property
    def llm_calls_remaining(self) -> int:
        """Get remaining LLM call budget."""
        return max(0, self.llm_budget - self._llm_calls_made)

    def reset_llm_budget(self, new_budget: Optional[int] = None) -> None:
        """Reset LLM call counter."""
        self._llm_calls_made = 0
        if new_budget is not None:
            self.llm_budget = new_budget

    def get_file_context(
        self,
        file: FileRecord,
        context_lines: int = DEFAULT_CONTEXT_LINES,
    ) -> FileContext:
        """
        Get complete context for a file including all references.

        Args:
            file: File record to analyze
            context_lines: Lines of context around each reference

        Returns:
            FileContext with handler info, metadata, and references
        """
        # Get content
        content = None
        if file.status == IndexStatus.EXTRACT_OK:
            content = self.db.get_content(file.file_id)

        # Find handler
        handler = self.registry.get_handler(file, content)
        handler_name = handler.name if handler else "none"

        # Extract metadata
        metadata = {}
        references = []
        relationship_hints = []

        if handler and content:
            metadata = handler.extract_metadata(file, content)
            references = handler.find_references(file, content, context_lines)
            relationship_hints = handler.get_relationship_hints(file, content)

        return FileContext(
            file=file,
            content=content,
            handler_name=handler_name,
            metadata=metadata,
            references=references,
            relationship_hints=relationship_hints,
        )

    def find_references_with_context(
        self,
        file: FileRecord,
        context_lines: int = DEFAULT_CONTEXT_LINES,
    ) -> List[ReferenceContext]:
        """
        Find all references in a file with surrounding context.

        Args:
            file: File record to analyze
            context_lines: Number of lines before/after to include

        Returns:
            List of ReferenceContext objects
        """
        ctx = self.get_file_context(file, context_lines)
        return ctx.references

    def find_references_in_root(
        self,
        root_id: int,
        context_lines: int = DEFAULT_CONTEXT_LINES,
        file_filter: Optional[callable] = None,
        limit: int = 1000,
    ) -> Dict[int, List[ReferenceContext]]:
        """
        Find all references across files in a root.

        Args:
            root_id: Root ID to search
            context_lines: Context window size
            file_filter: Optional filter function (file -> bool)
            limit: Maximum files to process

        Returns:
            Dict mapping file_id to list of references found
        """
        files = self.db.list_files(root_id, limit=limit)
        results: Dict[int, List[ReferenceContext]] = {}

        for file in files:
            if file.is_dir:
                continue

            if file_filter and not file_filter(file):
                continue

            refs = self.find_references_with_context(file, context_lines)
            if refs:
                results[file.file_id] = refs

        return results

    def verify_relationship(
        self,
        src_file: FileRecord,
        dst_file: FileRecord,
        use_llm: bool = True,
    ) -> LinkVerification:
        """
        Verify if src_file describes/references dst_file.

        Args:
            src_file: Source file (e.g., notes document)
            dst_file: Destination file (e.g., data file)
            use_llm: Whether to use LLM for verification

        Returns:
            LinkVerification with confidence and rationale
        """
        # Get contexts for both files
        src_ctx = self.get_file_context(src_file)
        dst_ctx = self.get_file_context(dst_file)

        # Check if any reference in src matches dst
        matching_refs = self._find_matching_references(src_ctx, dst_file)

        if not matching_refs:
            # No direct reference found - check path similarity
            return self._verify_by_path_similarity(src_file, dst_file)

        # We have matching references - verify them
        best_ref = max(matching_refs, key=lambda r: r.confidence)

        # Start with pattern-based verification
        verification = self._pattern_based_verification(
            src_file, dst_file, best_ref, src_ctx, dst_ctx
        )

        # Optionally enhance with LLM
        if use_llm and self.llm and self._llm_calls_made < self.llm_budget:
            # Only use LLM for ambiguous cases
            if 0.4 < verification.confidence < 0.8:
                llm_verification = self._llm_verify_context(
                    src_file, dst_file, best_ref
                )
                if llm_verification:
                    # Blend results
                    verification = self._blend_verifications(
                        verification, llm_verification
                    )

        return verification

    def _find_matching_references(
        self,
        src_ctx: FileContext,
        dst_file: FileRecord,
    ) -> List[ReferenceContext]:
        """Find references in src that match dst."""
        matches = []
        dst_name_lower = dst_file.name.lower()
        dst_stem_lower = Path(dst_file.name).stem.lower()

        # Also check for suffix pattern (e.g., "000" matching "20240115000.abf")
        dst_suffix = None
        suffix_match = re.search(r'(\d{3})\.(?:abf|smrx?)$', dst_file.name, re.IGNORECASE)
        if suffix_match:
            dst_suffix = suffix_match.group(1)

        for ref in src_ctx.references:
            ref_lower = ref.reference.lower()

            # Exact name match
            if ref_lower == dst_name_lower:
                ref.confidence = max(ref.confidence, 0.95)
                matches.append(ref)
                continue

            # Stem match (without extension)
            if ref_lower == dst_stem_lower:
                ref.confidence = max(ref.confidence, 0.9)
                matches.append(ref)
                continue

            # Reference is filename, matches dst
            if ref_lower in dst_name_lower or dst_name_lower in ref_lower:
                ref.confidence = max(ref.confidence, 0.8)
                matches.append(ref)
                continue

            # Short reference matches suffix
            if dst_suffix and ref.reference == dst_suffix:
                # Only count if they're in similar paths
                path_sim = self._calculate_path_similarity(
                    src_ctx.file.path, dst_file.path
                )
                if path_sim > 0.3:
                    ref.confidence = max(ref.confidence, 0.6 + path_sim * 0.2)
                    matches.append(ref)

        return matches

    def _pattern_based_verification(
        self,
        src_file: FileRecord,
        dst_file: FileRecord,
        reference: ReferenceContext,
        src_ctx: FileContext,
        dst_ctx: FileContext,
    ) -> LinkVerification:
        """
        Verify relationship using pattern matching.
        """
        confidence = reference.confidence
        rationale_parts = []
        metadata = {}

        # Factor 1: Reference type
        if reference.reference_type == "filename":
            confidence += 0.1
            rationale_parts.append("Explicit filename reference")
        elif reference.reference_type == "cell_filename":
            confidence += 0.15
            rationale_parts.append("Filename in spreadsheet cell")

        # Factor 2: Context metadata agreement
        ref_meta = reference.extracted_metadata
        dst_meta = dst_ctx.metadata

        # Check animal ID agreement
        if "animal_id" in ref_meta and "animal_id" in dst_meta:
            if ref_meta["animal_id"] == dst_meta["animal_id"]:
                confidence += 0.1
                rationale_parts.append(f"Matching animal ID: {ref_meta['animal_id']}")
                metadata["animal_id"] = ref_meta["animal_id"]

        # Check date agreement
        src_dates = set(ref_meta.get("dates", []))
        dst_date = dst_meta.get("recording_date")
        if dst_date and dst_date in src_dates:
            confidence += 0.1
            rationale_parts.append(f"Matching date: {dst_date}")
            metadata["date"] = dst_date

        # Factor 3: Path similarity
        path_sim = self._calculate_path_similarity(src_file.path, dst_file.path)
        if path_sim > 0.6:
            confidence += 0.05
            rationale_parts.append(f"Files in similar location ({path_sim:.0%})")
        elif path_sim > 0.8:
            confidence += 0.1
            rationale_parts.append("Files in same/nearby folder")

        # Factor 4: Evidence snippet quality
        evidence_snippets = []
        if reference.full_context:
            # Look for key phrases in context
            context_lower = reference.full_context.lower()
            if any(kw in context_lower for kw in ["recorded", "recording", "data file"]):
                confidence += 0.05
                evidence_snippets.append(reference.full_context[:300])

        return LinkVerification(
            is_valid=confidence > 0.5,
            confidence=min(confidence, 1.0),
            rationale="; ".join(rationale_parts) if rationale_parts else "Pattern match",
            extracted_metadata=metadata,
            evidence_snippets=evidence_snippets,
        )

    def _verify_by_path_similarity(
        self,
        src_file: FileRecord,
        dst_file: FileRecord,
    ) -> LinkVerification:
        """Verify relationship when no direct reference is found."""
        path_sim = self._calculate_path_similarity(src_file.path, dst_file.path)

        if path_sim > 0.8:
            return LinkVerification(
                is_valid=True,
                confidence=0.4,
                rationale="No explicit reference, but files in same folder",
            )
        elif path_sim > 0.5:
            return LinkVerification(
                is_valid=False,
                confidence=0.3,
                rationale="No explicit reference, files in similar location",
            )
        else:
            return LinkVerification(
                is_valid=False,
                confidence=0.1,
                rationale="No explicit reference found",
            )

    def _llm_verify_context(
        self,
        src_file: FileRecord,
        dst_file: FileRecord,
        reference: ReferenceContext,
    ) -> Optional[LinkVerification]:
        """
        Use LLM to verify the context around a reference.
        """
        if not self.llm:
            return None

        self._llm_calls_made += 1

        prompt = self.CONTEXT_UNDERSTANDING_PROMPT.format(
            src_name=src_file.name,
            src_path=src_file.path,
            reference=reference.reference,
            ref_type=reference.reference_type,
            context=reference.full_context[:2000],  # Limit context length
            metadata=str(reference.extracted_metadata),
        )

        try:
            response = self.llm.simple_chat(prompt)
            return self._parse_llm_verification(response)
        except Exception as e:
            print(f"[ContextReader] LLM error: {e}")
            return None

    def _parse_llm_verification(self, response: str) -> Optional[LinkVerification]:
        """Parse LLM response into LinkVerification."""
        import json

        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            return None

        try:
            data = json.loads(json_match.group())
            return LinkVerification(
                is_valid=data.get("is_genuine_reference", False) and
                         data.get("relationship_type") != "unrelated",
                confidence=float(data.get("confidence", 0.5)),
                rationale=data.get("rationale", "LLM analysis"),
                extracted_metadata=data.get("additional_metadata", {}),
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def _blend_verifications(
        self,
        pattern: LinkVerification,
        llm: LinkVerification,
    ) -> LinkVerification:
        """Blend pattern-based and LLM verifications."""
        # Weighted average: 60% pattern, 40% LLM
        blended_confidence = 0.6 * pattern.confidence + 0.4 * llm.confidence

        # Merge metadata
        merged_metadata = {**pattern.extracted_metadata, **llm.extracted_metadata}

        return LinkVerification(
            is_valid=blended_confidence > 0.5,
            confidence=blended_confidence,
            rationale=f"{pattern.rationale} | LLM: {llm.rationale}",
            extracted_metadata=merged_metadata,
            evidence_snippets=pattern.evidence_snippets,
        )

    def _calculate_path_similarity(self, path1: str, path2: str) -> float:
        """Calculate path similarity (0.0 to 1.0)."""
        parts1 = Path(path1).parts
        parts2 = Path(path2).parts

        # Count common prefix
        common = 0
        for p1, p2 in zip(parts1, parts2):
            if p1.lower() == p2.lower():
                common += 1
            else:
                break

        if common == 0:
            return 0.0

        # Calculate similarity
        max_depth = max(len(parts1), len(parts2))
        similarity = common / max_depth

        # Boost if same folder
        if len(parts1) > 1 and len(parts2) > 1:
            if parts1[:-1] == parts2[:-1]:
                return 1.0
            if len(parts1) > 2 and len(parts2) > 2:
                if parts1[:-2] == parts2[:-2]:
                    return 0.8

        return min(similarity + 0.2, 0.6)

    def match_references_to_files(
        self,
        references: List[ReferenceContext],
        candidate_files: List[FileRecord],
    ) -> List[Tuple[ReferenceContext, FileRecord, float]]:
        """
        Match references to actual files.

        Args:
            references: References found in a source file
            candidate_files: Files that might be referenced

        Returns:
            List of (reference, file, confidence) tuples
        """
        matches = []

        # Build lookup structures
        files_by_name = {f.name.lower(): f for f in candidate_files if not f.is_dir}
        files_by_stem = {Path(f.name).stem.lower(): f for f in candidate_files if not f.is_dir}

        # Build suffix index for ABF files
        files_by_suffix: Dict[str, List[FileRecord]] = {}
        for f in candidate_files:
            if f.is_dir:
                continue
            suffix_match = re.search(r'(\d{3})\.(?:abf|smrx?)$', f.name, re.IGNORECASE)
            if suffix_match:
                suffix = suffix_match.group(1)
                if suffix not in files_by_suffix:
                    files_by_suffix[suffix] = []
                files_by_suffix[suffix].append(f)

        for ref in references:
            ref_lower = ref.reference.lower()

            # Try exact name match
            if ref_lower in files_by_name:
                matches.append((ref, files_by_name[ref_lower], ref.confidence))
                continue

            # Try stem match
            if ref_lower in files_by_stem:
                matches.append((ref, files_by_stem[ref_lower], ref.confidence * 0.95))
                continue

            # Try suffix match for short references
            if ref.reference_type == "short_ref" and ref.reference in files_by_suffix:
                for file in files_by_suffix[ref.reference]:
                    matches.append((ref, file, ref.confidence * 0.8))

        return matches

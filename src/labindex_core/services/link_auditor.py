"""
LLM Link Auditor - Bounded validation for ambiguous link candidates.

The auditor is called ONLY for marginal cases where rule-based scoring
is insufficient:
- Tie between top candidates (within delta threshold)
- No exact match (requires typo inference)
- One-to-one constraint violation
- Low evidence but high context agreement
- User explicitly requests verification

The auditor returns structured JSON verdicts, not free-form text.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from ..domain.models import CandidateEdge, FileRecord, Audit
from ..domain.enums import CandidateStatus
from ..ports.db_port import DBPort
from ..ports.llm_port import LLMPort


@dataclass
class AuditResult:
    """Result from auditing a candidate edge."""
    verdict: str  # accept, reject, needs_more_info
    confidence: float  # 0.0-1.0
    rationale: str  # Brief explanation
    recommended_next_steps: List[str] = field(default_factory=list)


class LinkAuditor:
    """
    LLM auditor for ambiguous link candidates.

    Implements bounded validation - the auditor only evaluates when
    specific gating conditions are met, keeping LLM costs low and
    decisions traceable.
    """

    # Gating conditions that trigger auditor
    GATING_CONDITIONS = {
        "tie": "Top two candidates within score delta",
        "no_exact": "No exact filename match, requires inference",
        "conflict": "Violates one-to-one constraint",
        "low_evidence": "Weak evidence type (proximity_only)",
        "user_request": "User explicitly requested verification",
    }

    # Score delta for tie detection
    TIE_DELTA = 0.15

    # Prompt template for auditing
    AUDIT_PROMPT = """You are a link verification assistant helping validate file relationships in a research lab's file index.

## Candidate Link
**Source File**: {src_name}
  - Path: {src_path}
  - Category: {src_category}

**Target File**: {dst_name}
  - Path: {dst_path}
  - Category: {dst_category}

**Proposed Relationship**: {relation_type}
**Initial Confidence**: {confidence:.0%}

## Evidence
{evidence_summary}

## Context
{context}

## Gating Reason
This candidate was flagged for review because: {gating_reason}

## Alternative Candidates (if any)
{alternatives}

## Task
Evaluate whether this link is correct. Consider:
1. Do the filenames/paths suggest a real relationship?
2. Does the evidence support this specific link?
3. Could this be a false positive (coincidental match)?
4. Are there better alternatives?

Return ONLY a valid JSON object:
{{
    "verdict": "accept" | "reject" | "needs_more_info",
    "confidence": 0.0-1.0,
    "rationale": "brief explanation (1-2 sentences)",
    "recommended_next_steps": ["optional tool suggestions"]
}}
"""

    def __init__(self, db: DBPort, llm: Optional[LLMPort] = None):
        """
        Initialize the link auditor.

        Args:
            db: Database port for file access
            llm: LLM port for auditing (required for full functionality)
        """
        self.db = db
        self.llm = llm
        self.prompt_version = "1.0"

    def should_audit(
        self,
        candidate: CandidateEdge,
        alternatives: Optional[List[CandidateEdge]] = None
    ) -> Tuple[bool, str]:
        """
        Determine if a candidate should be sent to the auditor.

        Args:
            candidate: The candidate to check
            alternatives: Other candidates for the same dst_file_id

        Returns:
            Tuple of (should_audit: bool, reason: str)
        """
        # Check for tie
        if alternatives:
            top_scores = sorted([c.confidence for c in alternatives], reverse=True)
            if len(top_scores) >= 2:
                if top_scores[0] - top_scores[1] < self.TIE_DELTA:
                    return True, "tie"

        # Check for no exact match
        if candidate.evidence.get("type") == "inferred_sequence":
            return True, "no_exact"

        # Check for one-to-one violation
        features = candidate.features
        if features.get("violates_one_to_one"):
            return True, "conflict"

        # Check for low evidence
        if candidate.evidence.get("type") == "proximity_only":
            return True, "low_evidence"

        # Check for explicit user request
        if candidate.status == CandidateStatus.NEEDS_AUDIT:
            return True, "user_request"

        return False, ""

    def audit(
        self,
        candidate: CandidateEdge,
        gating_reason: str = "user_request",
        alternatives: Optional[List[CandidateEdge]] = None
    ) -> Optional[AuditResult]:
        """
        Audit a candidate edge using the LLM.

        Args:
            candidate: Candidate to audit
            gating_reason: Why auditor was called
            alternatives: Other candidates for comparison

        Returns:
            AuditResult or None if LLM unavailable
        """
        if self.llm is None:
            return self._rule_based_audit(candidate, gating_reason, alternatives)

        # Get file records
        src_file = self.db.get_file(candidate.src_file_id)
        dst_file = self.db.get_file(candidate.dst_file_id)

        if not src_file or not dst_file:
            return AuditResult(
                verdict="reject",
                confidence=1.0,
                rationale="Source or destination file not found",
            )

        # Build prompt
        prompt = self._build_audit_prompt(
            candidate, src_file, dst_file, gating_reason, alternatives
        )

        try:
            response = self.llm.simple_chat(prompt)
            result = self._parse_audit_response(response)

            if result:
                # Store audit in database
                audit = Audit(
                    audit_id=0,
                    candidate_id=candidate.candidate_id,
                    auditor_model=self.llm.get_model_name() if hasattr(self.llm, 'get_model_name') else "unknown",
                    auditor_prompt_version=self.prompt_version,
                    verdict=result.verdict,
                    confidence=result.confidence,
                    rationale_excerpt=result.rationale[:500],
                    recommended_next_steps=result.recommended_next_steps,
                )
                self.db.add_audit(audit)

                # Update candidate status based on verdict
                if result.verdict == "accept":
                    self.db.update_candidate_status(
                        candidate.candidate_id,
                        CandidateStatus.ACCEPTED.value,
                        f"auditor:{audit.auditor_model}"
                    )
                elif result.verdict == "reject":
                    self.db.update_candidate_status(
                        candidate.candidate_id,
                        CandidateStatus.REJECTED.value,
                        f"auditor:{audit.auditor_model}"
                    )
                # needs_more_info keeps status as needs_audit

                return result

        except Exception as e:
            print(f"[LinkAuditor] Error: {e}")

        return self._rule_based_audit(candidate, gating_reason, alternatives)

    def audit_batch(
        self,
        candidates: List[CandidateEdge],
        max_audits: int = 10
    ) -> Dict[int, AuditResult]:
        """
        Audit multiple candidates, respecting LLM budget.

        Args:
            candidates: Candidates to audit
            max_audits: Maximum number of LLM calls

        Returns:
            Dict mapping candidate_id to AuditResult
        """
        results: Dict[int, AuditResult] = {}
        audited = 0

        # Group by dst_file_id to find alternatives
        by_dst: Dict[int, List[CandidateEdge]] = {}
        for c in candidates:
            if c.dst_file_id not in by_dst:
                by_dst[c.dst_file_id] = []
            by_dst[c.dst_file_id].append(c)

        for candidate in candidates:
            if audited >= max_audits:
                break

            alternatives = by_dst.get(candidate.dst_file_id, [])
            should_audit, reason = self.should_audit(candidate, alternatives)

            if should_audit or candidate.status == CandidateStatus.NEEDS_AUDIT:
                result = self.audit(candidate, reason, alternatives)
                if result:
                    results[candidate.candidate_id] = result
                    audited += 1

        return results

    def _build_audit_prompt(
        self,
        candidate: CandidateEdge,
        src_file: FileRecord,
        dst_file: FileRecord,
        gating_reason: str,
        alternatives: Optional[List[CandidateEdge]]
    ) -> str:
        """Build the audit prompt from candidate data."""
        # Evidence summary
        evidence = candidate.evidence
        evidence_summary = f"Type: {evidence.get('type', 'unknown')}\n"
        if "matched_text" in evidence:
            evidence_summary += f"Matched text: '{evidence['matched_text']}'\n"
        if "matched_suffix" in evidence:
            evidence_summary += f"Matched suffix: '{evidence['matched_suffix']}' ({evidence.get('mention_count', 0)} mentions)\n"
        if "shared_animal_id" in evidence:
            evidence_summary += f"Shared animal ID: {evidence['shared_animal_id']}\n"
        if "evidence_text" in evidence:
            evidence_summary += f"Excerpt: {evidence['evidence_text'][:200]}...\n"

        # Context from features
        features = candidate.features
        context_parts = []
        if features.get("date_token_agreement", 0) > 0:
            context_parts.append(f"Date agreement: {features['date_token_agreement']:.0%}")
        if features.get("animal_id_agreement", 0) > 0:
            context_parts.append(f"Animal ID agreement: {features['animal_id_agreement']:.0%}")
        if features.get("same_folder"):
            context_parts.append("Files are in same folder")
        if features.get("parent_folder"):
            context_parts.append("Files share parent folder")
        context = "\n".join(context_parts) if context_parts else "No additional context"

        # Alternative candidates
        alt_text = "None"
        if alternatives and len(alternatives) > 1:
            alt_parts = []
            for alt in alternatives:
                if alt.candidate_id != candidate.candidate_id:
                    alt_src = self.db.get_file(alt.src_file_id)
                    if alt_src:
                        alt_parts.append(
                            f"- {alt_src.name}: {alt.confidence:.0%} confidence, "
                            f"evidence type: {alt.evidence.get('type', 'unknown')}"
                        )
            alt_text = "\n".join(alt_parts[:5]) if alt_parts else "None"

        return self.AUDIT_PROMPT.format(
            src_name=src_file.name,
            src_path=src_file.path,
            src_category=src_file.category.value,
            dst_name=dst_file.name,
            dst_path=dst_file.path,
            dst_category=dst_file.category.value,
            relation_type=candidate.relation_type.value,
            confidence=candidate.confidence,
            evidence_summary=evidence_summary,
            context=context,
            gating_reason=self.GATING_CONDITIONS.get(gating_reason, gating_reason),
            alternatives=alt_text,
        )

    def _parse_audit_response(self, response: str) -> Optional[AuditResult]:
        """Parse LLM response into AuditResult."""
        # Try to find JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            response = json_match.group(1)

        # Try to parse as JSON
        try:
            data = json.loads(response.strip())
            return AuditResult(
                verdict=data.get("verdict", "needs_more_info"),
                confidence=float(data.get("confidence", 0.5)),
                rationale=data.get("rationale", ""),
                recommended_next_steps=data.get("recommended_next_steps", []),
            )
        except json.JSONDecodeError:
            # Try to find JSON object
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return AuditResult(
                        verdict=data.get("verdict", "needs_more_info"),
                        confidence=float(data.get("confidence", 0.5)),
                        rationale=data.get("rationale", ""),
                        recommended_next_steps=data.get("recommended_next_steps", []),
                    )
                except json.JSONDecodeError:
                    pass

        return None

    def _rule_based_audit(
        self,
        candidate: CandidateEdge,
        gating_reason: str,
        alternatives: Optional[List[CandidateEdge]]
    ) -> AuditResult:
        """Fallback rule-based audit when LLM unavailable."""
        features = candidate.features
        evidence = candidate.evidence

        # Start with base confidence
        confidence = candidate.confidence

        # Adjust based on features
        if evidence.get("type") == "explicit_mention":
            return AuditResult(
                verdict="accept",
                confidence=min(confidence + 0.1, 1.0),
                rationale="Explicit filename mention provides strong evidence",
            )

        if features.get("exact_basename_match"):
            return AuditResult(
                verdict="accept",
                confidence=min(confidence + 0.1, 1.0),
                rationale="Exact basename match supports this link",
            )

        if features.get("violates_one_to_one"):
            # Check if this is the best alternative
            if alternatives:
                best = max(alternatives, key=lambda c: c.confidence)
                if candidate.candidate_id == best.candidate_id:
                    return AuditResult(
                        verdict="accept",
                        confidence=confidence,
                        rationale="Best candidate despite one-to-one violation",
                        recommended_next_steps=["Review alternatives manually"],
                    )
                else:
                    return AuditResult(
                        verdict="reject",
                        confidence=1.0 - confidence,
                        rationale="Better alternative exists",
                    )

        if evidence.get("type") == "proximity_only":
            if candidate.confidence < 0.5:
                return AuditResult(
                    verdict="reject",
                    confidence=1.0 - confidence,
                    rationale="Weak proximity-only evidence with low confidence",
                )

        return AuditResult(
            verdict="needs_more_info",
            confidence=0.5,
            rationale="Insufficient evidence for automated decision",
            recommended_next_steps=["Manual review recommended"],
        )

    def get_audit_history(self, candidate_id: int) -> List[Audit]:
        """Get all audits for a candidate."""
        return self.db.get_audits_for_candidate(candidate_id)

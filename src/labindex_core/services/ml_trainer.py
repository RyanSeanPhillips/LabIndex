"""
ML Training Pipeline for Link Prediction.

This service manages:
1. Exporting labeled candidates to training data
2. Training classifiers (RandomForest, XGBoost, MLP)
3. Evaluating model performance
4. Using trained models for inference
5. Model persistence (save/load)

The trained model can replace rule-based scoring with learned
weights, improving link prediction over time as more labels
are collected.
"""

import json
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from ..domain.models import CandidateEdge, ScoringResult, SoftScore
from ..domain.enums import CandidateStatus
from ..ports.db_port import DBPort

# Optional ML dependencies
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        precision_score, recall_score, f1_score,
        classification_report, confusion_matrix
    )
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False


@dataclass
class TrainingMetrics:
    """Metrics from model training/evaluation."""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    confusion_matrix: List[List[int]] = field(default_factory=list)
    feature_importances: Dict[str, float] = field(default_factory=dict)
    training_samples: int = 0
    test_samples: int = 0
    trained_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "confusion_matrix": self.confusion_matrix,
            "feature_importances": self.feature_importances,
            "training_samples": self.training_samples,
            "test_samples": self.test_samples,
            "trained_at": self.trained_at.isoformat(),
        }


@dataclass
class ModelInfo:
    """Information about a trained model."""
    model_type: str  # "random_forest", "xgboost", "mlp"
    version: str
    feature_names: List[str]
    metrics: TrainingMetrics
    created_at: datetime = field(default_factory=datetime.now)


class MLTrainer:
    """
    ML training pipeline for link prediction.

    Supports:
    - RandomForest (default, works well with small datasets)
    - XGBoost (better with larger datasets)
    - MLP (neural network, experimental)
    """

    # Feature columns to use for training
    FEATURE_COLUMNS = [
        # Path/name similarity
        "exact_basename_match",
        "normalized_basename_match",
        "edit_distance",
        "rapidfuzz_ratio",
        "same_folder",
        "parent_folder",
        "sibling_folder",
        "path_depth_difference",
        "common_ancestor_depth",
        # Evidence quality
        "evidence_strength",
        "has_canonical_column_match",
        "column_header_similarity",
        "evidence_span_length",
        # Context agreement
        "date_token_agreement",
        "animal_id_agreement",
        "chamber_agreement",
        # Context-aware features
        "context_mouse_id_match",
        "context_date_match",
        "context_channel_agreement",
        "context_explicit_reference",
        "context_confidence",
        # Uniqueness/conflict
        "num_candidates_for_src",
        "num_candidates_for_dst",
        "violates_one_to_one",
        "dst_already_linked",
    ]

    def __init__(self, db: DBPort, model_dir: Optional[Path] = None):
        """
        Initialize the trainer.

        Args:
            db: Database port for accessing candidates
            model_dir: Directory for model storage (default: ./models)
        """
        self.db = db
        self.model_dir = model_dir or Path("./models")
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self._model = None
        self._model_info: Optional[ModelInfo] = None

    @property
    def is_trained(self) -> bool:
        """Check if a model is loaded."""
        return self._model is not None

    @property
    def model_info(self) -> Optional[ModelInfo]:
        """Get info about the current model."""
        return self._model_info

    def get_labeled_candidates(
        self,
        min_confidence: float = 0.0,
    ) -> List[CandidateEdge]:
        """
        Get all labeled candidates for training.

        Args:
            min_confidence: Minimum original confidence threshold

        Returns:
            List of accepted and rejected candidates
        """
        candidates = []

        # Get accepted candidates
        accepted = self.db.list_candidate_edges(status="accepted", limit=10000)
        candidates.extend(accepted)

        # Get rejected candidates
        rejected = self.db.list_candidate_edges(status="rejected", limit=10000)
        candidates.extend(rejected)

        # Filter by confidence if specified
        if min_confidence > 0:
            candidates = [c for c in candidates if c.confidence >= min_confidence]

        return candidates

    def export_training_data(
        self,
        output_path: Optional[Path] = None,
        min_confidence: float = 0.0,
    ) -> Tuple[Path, int]:
        """
        Export labeled candidates to CSV for training.

        Args:
            output_path: Output CSV path (default: training_data_{timestamp}.csv)
            min_confidence: Minimum confidence threshold

        Returns:
            Tuple of (output_path, sample_count)
        """
        import csv

        candidates = self.get_labeled_candidates(min_confidence)

        if not candidates:
            raise ValueError("No labeled candidates found for training")

        # Generate output path if not specified
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.model_dir / f"training_data_{timestamp}.csv"

        # Write CSV
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["candidate_id", "label"] + self.FEATURE_COLUMNS
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for candidate in candidates:
                row = {
                    "candidate_id": candidate.candidate_id,
                    "label": 1 if candidate.status == CandidateStatus.ACCEPTED else 0,
                }

                # Add features
                features = candidate.features
                for col in self.FEATURE_COLUMNS:
                    value = features.get(col, 0)
                    # Handle None and convert to numeric
                    if value is None:
                        value = 0
                    elif isinstance(value, bool):
                        value = 1 if value else 0
                    elif isinstance(value, str):
                        value = 0  # Skip string features for now
                    row[col] = value

                writer.writerow(row)

        return output_path, len(candidates)

    def train(
        self,
        model_type: str = "random_forest",
        test_size: float = 0.2,
        random_state: int = 42,
        **model_params
    ) -> TrainingMetrics:
        """
        Train a classifier from labeled candidates.

        Args:
            model_type: "random_forest" or "xgboost"
            test_size: Fraction of data for testing
            random_state: Random seed for reproducibility
            **model_params: Additional parameters for the model

        Returns:
            TrainingMetrics with evaluation results
        """
        if not HAS_SKLEARN:
            raise RuntimeError("scikit-learn is required for training. Install with: pip install scikit-learn")

        if model_type == "xgboost" and not HAS_XGBOOST:
            raise RuntimeError("XGBoost is required. Install with: pip install xgboost")

        # Get labeled data
        candidates = self.get_labeled_candidates()
        if len(candidates) < 10:
            raise ValueError(f"Need at least 10 labeled samples, got {len(candidates)}")

        # Prepare feature matrix and labels
        X, y, sample_ids = self._prepare_training_data(candidates)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )

        # Create and train model
        if model_type == "random_forest":
            default_params = {
                "n_estimators": 100,
                "max_depth": 10,
                "min_samples_split": 5,
                "random_state": random_state,
                "class_weight": "balanced",
            }
            default_params.update(model_params)
            model = RandomForestClassifier(**default_params)

        elif model_type == "xgboost":
            # Calculate scale_pos_weight for class imbalance
            n_neg = sum(1 for label in y_train if label == 0)
            n_pos = sum(1 for label in y_train if label == 1)
            scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

            default_params = {
                "n_estimators": 100,
                "max_depth": 6,
                "learning_rate": 0.1,
                "scale_pos_weight": scale_pos_weight,
                "random_state": random_state,
            }
            default_params.update(model_params)
            model = xgb.XGBClassifier(**default_params)

        else:
            raise ValueError(f"Unknown model type: {model_type}")

        # Train
        model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)
        metrics = self._evaluate_model(y_test, y_pred, len(X_train), len(X_test))

        # Get feature importances
        if hasattr(model, "feature_importances_"):
            metrics.feature_importances = dict(zip(
                self.FEATURE_COLUMNS,
                [float(x) for x in model.feature_importances_]
            ))

        # Store model
        self._model = model
        self._model_info = ModelInfo(
            model_type=model_type,
            version="1.0",
            feature_names=self.FEATURE_COLUMNS.copy(),
            metrics=metrics,
        )

        return metrics

    def predict(self, candidate: CandidateEdge) -> Tuple[str, float]:
        """
        Predict label for a candidate.

        Args:
            candidate: Candidate to classify

        Returns:
            Tuple of (label: "accept"/"reject", probability)
        """
        if not self._model:
            raise RuntimeError("No model loaded. Call train() or load_model() first.")

        # Extract features
        features = self._extract_features(candidate)
        X = np.array([features])

        # Predict
        pred = self._model.predict(X)[0]
        proba = self._model.predict_proba(X)[0]

        label = "accept" if pred == 1 else "reject"
        confidence = float(proba[1]) if pred == 1 else float(proba[0])

        return label, confidence

    def predict_batch(
        self,
        candidates: List[CandidateEdge]
    ) -> List[Tuple[int, str, float]]:
        """
        Predict labels for multiple candidates.

        Args:
            candidates: List of candidates to classify

        Returns:
            List of (candidate_id, label, probability) tuples
        """
        if not self._model:
            raise RuntimeError("No model loaded. Call train() or load_model() first.")

        if not candidates:
            return []

        # Extract features for all candidates
        X = np.array([self._extract_features(c) for c in candidates])

        # Predict
        preds = self._model.predict(X)
        probas = self._model.predict_proba(X)

        results = []
        for i, candidate in enumerate(candidates):
            pred = preds[i]
            label = "accept" if pred == 1 else "reject"
            confidence = float(probas[i][1]) if pred == 1 else float(probas[i][0])
            results.append((candidate.candidate_id, label, confidence))

        return results

    def score_with_model(self, candidate: CandidateEdge) -> ScoringResult:
        """
        Score a candidate using the trained model.

        Returns a ScoringResult compatible with the soft scoring system.

        Args:
            candidate: Candidate to score

        Returns:
            ScoringResult with model-based scoring
        """
        from ..domain.models import ScoringResult, SoftScore

        if not self._model:
            raise RuntimeError("No model loaded")

        # Get prediction
        label, confidence = self.predict(candidate)

        # Build breakdown from feature importances
        breakdown = []
        if self._model_info and self._model_info.metrics.feature_importances:
            features = candidate.features
            importances = self._model_info.metrics.feature_importances

            for feature_name, importance in importances.items():
                raw_value = features.get(feature_name, 0)
                if raw_value is None:
                    raw_value = 0

                breakdown.append(SoftScore(
                    feature_name=feature_name,
                    raw_value=float(raw_value) if not isinstance(raw_value, str) else 0,
                    normalized_value=float(raw_value) if not isinstance(raw_value, str) else 0,
                    weight=importance,
                    contribution=importance * (float(raw_value) if not isinstance(raw_value, str) else 0),
                    explanation=f"Feature importance: {importance:.2%}"
                ))

            # Sort by contribution
            breakdown.sort(key=lambda x: abs(x.contribution), reverse=True)

        # Determine confidence level
        if confidence >= 0.8:
            confidence_level = "high"
        elif confidence >= 0.5:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        return ScoringResult(
            total_score=confidence if label == "accept" else 1 - confidence,
            score_breakdown=breakdown[:10],  # Top 10 features
            confidence_level=confidence_level,
            flags=["ml_scored"],
        )

    def save_model(self, path: Optional[Path] = None) -> Path:
        """
        Save the trained model to disk.

        Args:
            path: Output path (default: model_dir/link_model.pkl)

        Returns:
            Path where model was saved
        """
        if not self._model:
            raise RuntimeError("No model to save")

        if path is None:
            path = self.model_dir / "link_model.pkl"

        # Save model and info together
        data = {
            "model": self._model,
            "info": self._model_info,
        }

        with open(path, "wb") as f:
            pickle.dump(data, f)

        # Also save info as JSON for inspection
        info_path = path.with_suffix(".json")
        with open(info_path, "w") as f:
            json.dump({
                "model_type": self._model_info.model_type,
                "version": self._model_info.version,
                "feature_names": self._model_info.feature_names,
                "metrics": self._model_info.metrics.to_dict(),
            }, f, indent=2)

        return path

    def load_model(self, path: Optional[Path] = None) -> ModelInfo:
        """
        Load a trained model from disk.

        Args:
            path: Model path (default: model_dir/link_model.pkl)

        Returns:
            ModelInfo about the loaded model
        """
        if path is None:
            path = self.model_dir / "link_model.pkl"

        if not path.exists():
            raise FileNotFoundError(f"Model not found: {path}")

        with open(path, "rb") as f:
            data = pickle.load(f)

        self._model = data["model"]
        self._model_info = data["info"]

        return self._model_info

    def _prepare_training_data(
        self,
        candidates: List[CandidateEdge]
    ) -> Tuple[Any, Any, List[int]]:
        """Prepare feature matrix and labels."""
        X = []
        y = []
        sample_ids = []

        for candidate in candidates:
            features = self._extract_features(candidate)
            label = 1 if candidate.status == CandidateStatus.ACCEPTED else 0

            X.append(features)
            y.append(label)
            sample_ids.append(candidate.candidate_id)

        return np.array(X), np.array(y), sample_ids

    def _extract_features(self, candidate: CandidateEdge) -> List[float]:
        """Extract feature vector from candidate."""
        features = candidate.features
        result = []

        for col in self.FEATURE_COLUMNS:
            value = features.get(col, 0)
            if value is None:
                value = 0
            elif isinstance(value, bool):
                value = 1 if value else 0
            elif isinstance(value, str):
                value = 0
            result.append(float(value))

        return result

    def _evaluate_model(
        self,
        y_true,
        y_pred,
        train_size: int,
        test_size: int
    ) -> TrainingMetrics:
        """Evaluate model performance."""
        accuracy = float(sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp) / len(y_true))
        precision = float(precision_score(y_true, y_pred, zero_division=0))
        recall = float(recall_score(y_true, y_pred, zero_division=0))
        f1 = float(f1_score(y_true, y_pred, zero_division=0))
        cm = confusion_matrix(y_true, y_pred).tolist()

        return TrainingMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            confusion_matrix=cm,
            training_samples=train_size,
            test_samples=test_size,
        )

    def get_training_stats(self) -> Dict[str, Any]:
        """Get statistics about available training data."""
        accepted = self.db.count_candidate_edges("accepted")
        rejected = self.db.count_candidate_edges("rejected")

        return {
            "accepted_samples": accepted,
            "rejected_samples": rejected,
            "total_labeled": accepted + rejected,
            "class_balance": accepted / (accepted + rejected) if (accepted + rejected) > 0 else 0,
            "has_enough_data": (accepted + rejected) >= 10,
            "model_loaded": self.is_trained,
            "model_info": self._model_info.metrics.to_dict() if self._model_info else None,
        }

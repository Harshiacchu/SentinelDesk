"""Multi-task triage: type, queue, priority with calibrated confidence. Owner: P2."""
from . import config
from .contracts import Ticket, Triage

TARGETS = ("type", "queue", "priority")


def train(kb_df, kb_emb) -> None:
    """Fit one calibrated classifier per target and save them to artifacts/models/.

    TODO(P2): TF-IDF + LinearSVC baseline, then embeddings + LogisticRegression
    with CalibratedClassifierCV and class_weight='balanced'; tune the 'high' threshold.
    TODO(P2): fit on the KB minus the validation slice; calibrate and tune on validation only.
    In scikit-learn >= 1.6, cv="prefit" is deprecated: use CalibratedClassifierCV(FrozenEstimator(model)).
    """
    raise NotImplementedError


def predict(ticket: Ticket, language: str = "en") -> Triage:
    if config.USE_MOCKS:
        return {
            "type": {"label": "Request", "confidence": 0.82},
            "queue": {"label": "Technical Support", "confidence": 0.74},
            "priority": {"label": "medium", "confidence": 0.68},
            "language": language,
        }
    raise NotImplementedError("TODO(P2)")

"""Stage 7 configurable, evidence-backed marketing capability."""

from .feature_builder import CustomerFeatureBuilder
from .opportunity_detector import OpportunityDetector
from .segment_engine import SegmentEngine
from .strategy_engine import StrategyEngine
from .tag_engine import TagEngine

__all__ = ["CustomerFeatureBuilder", "TagEngine", "SegmentEngine", "OpportunityDetector", "StrategyEngine"]

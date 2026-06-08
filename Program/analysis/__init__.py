"""Shared analysis snapshots used by GUI, exports, reports, and plots."""

from .comparison_snapshot import (
    ComparisonSnapshot,
    ComparisonSnapshotOptions,
    DatasetAnalysisInput,
    GrainAggregationReport,
    GrainAggregateStats,
    GrainMetricStats,
    build_comparison_snapshot,
    dataset_analysis_from_tab,
)

__all__ = [
    "ComparisonSnapshot",
    "ComparisonSnapshotOptions",
    "DatasetAnalysisInput",
    "GrainAggregationReport",
    "GrainAggregateStats",
    "GrainMetricStats",
    "build_comparison_snapshot",
    "dataset_analysis_from_tab",
]

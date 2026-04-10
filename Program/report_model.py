"""
Structured report model shared across renderers.

This module is the foundation for moving report generation away from raw HTML
string assembly and toward a renderer-agnostic document model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


AppendixLabelMode = Literal["auto", "manual"]
AppendixLabelScheme = Literal["alpha", "numeric", "alpha_numeric"]
AppendixLayout = Literal["separate", "single"]
SectionKind = Literal["section", "appendix"]


def _index_to_alpha(index: int) -> str:
    """Convert a 1-based index to A, B, ... Z, AA, AB, ..."""
    if index < 1:
        raise ValueError("Appendix indices must be 1-based.")

    label = ""
    current = index
    while current > 0:
        current -= 1
        label = chr(ord("A") + (current % 26)) + label
        current //= 26
    return label


@dataclass(slots=True)
class MetadataItem:
    key: str
    value: str


@dataclass(slots=True)
class HeadingBlock:
    level: int
    text: str


@dataclass(slots=True)
class ParagraphBlock:
    text: str


@dataclass(slots=True)
class TableBlock:
    columns: list[str]
    rows: list[list[str]]
    caption: str = ""


@dataclass(slots=True)
class HtmlBlock:
    html: str


@dataclass(slots=True)
class ImageBlock:
    source: str
    caption: str = ""
    alt_text: str = ""


@dataclass(slots=True)
class PageBreakBlock:
    pass


ReportBlock = HeadingBlock | ParagraphBlock | TableBlock | HtmlBlock | ImageBlock | PageBreakBlock


@dataclass(slots=True)
class ReportSection:
    section_id: str
    title: str
    kind: SectionKind = "section"
    blocks: list[ReportBlock] = field(default_factory=list)
    include: bool = True
    notes: str = ""


@dataclass(slots=True)
class AppendixLabelConfig:
    mode: AppendixLabelMode = "auto"
    scheme: AppendixLabelScheme = "alpha"
    layout: AppendixLayout = "separate"
    prefix: str = "Appendix "
    alpha_numeric_root: str = "A"
    single_label: str = ""
    manual_labels: dict[str, str] = field(default_factory=dict)

    def resolve_label(self, section_id: str, order_index: int) -> str:
        """
        Resolve the visible label for an appendix section.

        `order_index` is the 1-based visible appendix order after filtering.
        """
        if order_index < 1:
            raise ValueError("Appendix order_index must be 1-based.")

        if self.mode == "manual":
            manual = self.manual_labels.get(section_id, "").strip()
            if manual:
                return manual

        if self.scheme == "alpha":
            return f"{self.prefix}{_index_to_alpha(order_index)}"
        if self.scheme == "numeric":
            return f"{self.prefix}{order_index}"
        if self.scheme == "alpha_numeric":
            return f"{self.alpha_numeric_root}{order_index}"

        raise ValueError(f"Unsupported appendix label scheme: {self.scheme}")


@dataclass(slots=True)
class ReportDocument:
    title: str
    subtitle: str = ""
    metadata: list[MetadataItem] = field(default_factory=list)
    sections: list[ReportSection] = field(default_factory=list)
    appendix_label_config: AppendixLabelConfig = field(default_factory=AppendixLabelConfig)

    def add_section(self, section: ReportSection) -> None:
        self.sections.append(section)

    def iter_sections(self, include_hidden: bool = False) -> list[ReportSection]:
        if include_hidden:
            return list(self.sections)
        return [section for section in self.sections if section.include]

    def appendix_sections(self, include_hidden: bool = False) -> list[ReportSection]:
        return [
            section
            for section in self.iter_sections(include_hidden=include_hidden)
            if section.kind == "appendix"
        ]

    def single_appendix_enabled(self) -> bool:
        return self.appendix_label_config.layout == "single"

    def appendix_label_map(self) -> dict[str, str]:
        labels: dict[str, str] = {}
        for order_index, section in enumerate(self.appendix_sections(), start=1):
            labels[section.section_id] = self.appendix_label_config.resolve_label(
                section.section_id,
                order_index,
            )
        return labels

    def single_appendix_label(self) -> str:
        appendix_sections = self.appendix_sections()
        if not appendix_sections:
            return ""

        config = self.appendix_label_config
        if config.mode == "manual":
            manual = config.single_label.strip()
            if manual:
                return manual

        first_section = appendix_sections[0]
        return config.resolve_label(first_section.section_id, 1)

    def appendix_display_title(self, section: ReportSection) -> str:
        if section.kind != "appendix":
            return section.title

        label = self.appendix_label_map().get(section.section_id, "").strip()
        if not label:
            return section.title
        if not section.title:
            return label
        return f"{label}: {section.title}"

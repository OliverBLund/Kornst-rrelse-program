"""
Report generator for creating professional analysis reports
"""

from typing import List, Dict, Optional, Any
import numpy as np
from datetime import datetime
import base64
import io
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.colors import ListedColormap
from data_loader import GrainSizeData
from k_calculations import KCalculationResult


class ReportGenerator:
    """
    Generates professional reports for grain size analysis and K-value calculations
    """

    def __init__(self):
        # Ultra-clean minimalistic styling - Professional engineering report format
        self.report_style = """
        <style>
            /* ============================================
               PROFESSIONAL REPORT STYLING - VERSION 3.0
               Ultra-clean minimalistic design
               Inspired by ASTM/ISO standard reports
               ============================================ */

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }

            @media print {
                body {
                    margin: 0;
                    padding: 20mm;
                }

                .page-break {
                    page-break-before: always;
                }

                .no-break {
                    page-break-inside: avoid;
                }

                h1, h2 {
                    page-break-after: avoid;
                }

                table {
                    page-break-inside: avoid;
                }
            }

            body {
                font-family: 'Calibri', 'Arial', sans-serif;
                line-height: 1.5;
                color: #000000;
                background-color: #ffffff;
                max-width: 800px;
                margin: 0 auto;
                padding: 40px 50px;
                font-size: 11pt;
            }

            /* ==================== COVER PAGE ==================== */
            .cover-page {
                text-align: center;
                padding: 80px 40px;
                min-height: 600px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                border-bottom: 3px solid #2c3e50;
                margin-bottom: 40px;
            }

            .cover-title {
                font-size: 42px;
                font-weight: 300;
                color: #2c3e50;
                margin-bottom: 20px;
                letter-spacing: -1px;
                text-transform: uppercase;
            }

            .cover-subtitle {
                font-size: 20px;
                color: #7f8c8d;
                font-weight: 300;
                margin-bottom: 60px;
            }

            .cover-meta {
                font-size: 14px;
                color: #34495e;
                line-height: 2;
                margin-top: 40px;
            }

            /* ==================== TYPOGRAPHY ==================== */
            h1 {
                font-size: 20pt;
                font-weight: bold;
                color: #000000;
                margin: 0 0 30px 0;
                padding: 0;
                border: none;
                letter-spacing: 0;
                text-transform: none;
            }

            h2 {
                font-size: 14pt;
                font-weight: bold;
                color: #000000;
                margin: 30px 0 15px 0;
                padding: 0;
                border: none;
            }

            h3 {
                font-size: 12pt;
                font-weight: bold;
                color: #000000;
                margin: 20px 0 10px 0;
            }

            h4 {
                font-size: 11pt;
                font-weight: bold;
                color: #000000;
                margin: 15px 0 8px 0;
            }

            p {
                margin: 8px 0;
                line-height: 1.5;
                text-align: left;
            }

            /* ==================== APPENDIX STYLING ==================== */
            .appendix-section {
                margin-top: 50px;
                padding-top: 30px;
                border-top: 3px double #95a5a6;
            }

            .appendix-title {
                font-size: 24px;
                font-weight: 300;
                color: #2c3e50;
                margin-bottom: 15px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }

            .appendix-item {
                margin: 30px 0;
                padding: 20px;
                background-color: #fafafa;
                border-left: 3px solid #3498db;
                border-radius: 3px;
            }

            .appendix-item-title {
                font-size: 14px;
                font-weight: 600;
                color: #34495e;
                margin-bottom: 15px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            /* ==================== METADATA & INFO BOXES ==================== */
            .metadata {
                background-color: #ffffff;
                border: 1px solid #000000;
                border-radius: 0;
                padding: 15px;
                margin: 20px 0;
                font-size: 10pt;
            }

            .metadata-grid {
                display: grid;
                grid-template-columns: 140px 1fr;
                gap: 8px 15px;
                line-height: 1.6;
            }

            .metadata-label {
                font-weight: bold;
                color: #000000;
            }

            .metadata-value {
                color: #000000;
            }

            .info-box {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                padding: 15px;
                margin: 15px 0;
                border-radius: 0;
            }

            .info-box h3 {
                margin-top: 0;
                color: #000000;
                font-size: 11pt;
            }

            .info-box p {
                margin: 6px 0;
                color: #000000;
            }

            .warning-box {
                background-color: #fff9e6;
                border: 1px solid #ffcc00;
                padding: 15px;
                margin: 15px 0;
                border-radius: 0;
            }

            .success-box {
                background-color: #f0f8f0;
                border: 1px solid #66cc66;
                padding: 15px;
                margin: 15px 0;
                border-radius: 0;
            }

            .error-box {
                background-color: #fff0f0;
                border: 1px solid #cc6666;
                padding: 15px;
                margin: 15px 0;
                border-radius: 0;
            }

            /* ==================== TABLES ==================== */
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
                background-color: #ffffff;
                border: none;
                font-size: 10pt;
            }

            thead {
                background-color: #ffffff;
                border-bottom: 2px solid #000000;
            }

            th {
                color: #000000;
                padding: 8px 10px;
                text-align: left;
                font-weight: bold;
                font-size: 10pt;
                text-transform: none;
                letter-spacing: 0;
                border-bottom: 2px solid #000000;
            }

            td {
                padding: 6px 10px;
                border-bottom: 1px solid #cccccc;
                font-size: 10pt;
                vertical-align: top;
            }

            tr:nth-child(even) {
                background-color: #ffffff;
            }

            tr:hover {
                background-color: #f9f9f9;
            }

            tbody tr:last-child td {
                border-bottom: 1px solid #000000;
            }

            /* Compact table style for appendix */
            .table-compact {
                font-size: 9pt;
            }

            .table-compact th {
                padding: 6px 8px;
                font-size: 9pt;
            }

            .table-compact td {
                padding: 4px 8px;
            }

            /* ==================== STAT CARDS ==================== */
            .summary-stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                gap: 10px;
                margin: 20px 0;
            }

            .stat-card {
                background-color: #ffffff;
                padding: 12px;
                border: 1px solid #000000;
                border-radius: 0;
                text-align: center;
                box-shadow: none;
            }

            .stat-card:hover {
                box-shadow: none;
            }

            .stat-label {
                font-size: 9pt;
                color: #000000;
                text-transform: none;
                letter-spacing: 0;
                font-weight: bold;
                margin-bottom: 6px;
            }

            .stat-value {
                font-size: 18pt;
                font-weight: bold;
                color: #000000;
                margin-top: 4px;
                font-family: 'Calibri', 'Arial', sans-serif;
            }

            .stat-unit {
                font-size: 9pt;
                color: #666666;
                margin-top: 2px;
            }

            /* ==================== PLOTS & FIGURES ==================== */
            .plot-container {
                text-align: center;
                margin: 25px 0;
                padding: 15px;
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }

            .plot-container img {
                max-width: 100%;
                height: auto;
                border-radius: 2px;
            }

            .figure-caption {
                font-size: 10pt;
                color: #6c757d;
                font-style: italic;
                margin-top: 10px;
                text-align: center;
            }

            /* ==================== LISTS ==================== */
            ul, ol {
                margin: 12px 0;
                padding-left: 25px;
            }

            li {
                margin: 6px 0;
                line-height: 1.6;
            }

            /* ==================== FOOTER & HEADERS ==================== */
            .footer {
                margin-top: 60px;
                padding-top: 20px;
                border-top: 1px solid #dee2e6;
                text-align: center;
                color: #6c757d;
                font-size: 9pt;
                line-height: 1.5;
            }

            .page-header {
                display: none; /* Hidden in web view, shown in print */
                font-size: 9pt;
                color: #6c757d;
                padding-bottom: 10px;
                border-bottom: 1px solid #dee2e6;
                margin-bottom: 20px;
            }

            @media print {
                .page-header {
                    display: block;
                }
            }

            /* ==================== DIVIDERS ==================== */
            .section-divider {
                height: 1px;
                background-color: #dee2e6;
                margin: 35px 0;
                border: none;
            }

            hr {
                border: none;
                height: 1px;
                background-color: #dee2e6;
                margin: 20px 0;
            }

            /* ==================== UTILITY CLASSES ==================== */
            .text-center {
                text-align: center;
            }

            .text-right {
                text-align: right;
            }

            .text-muted {
                color: #6c757d;
            }

            .highlight {
                background-color: #fff3cd;
                padding: 2px 5px;
                border-radius: 2px;
            }

            .badge {
                display: inline-block;
                padding: 2px 6px;
                font-size: 9pt;
                font-weight: normal;
                border-radius: 0;
                text-transform: none;
                letter-spacing: 0;
                border: 1px solid #000000;
                background-color: #ffffff;
            }

            .badge-success {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #000000;
            }

            .badge-warning {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #000000;
            }

            .badge-danger {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #000000;
            }

            .badge-info {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #000000;
            }

            .badge-secondary {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #000000;
            }

            strong, b {
                font-weight: 600;
                color: #212529;
            }

            code {
                font-family: 'Roboto Mono', 'Courier New', monospace;
                background-color: #f8f9fa;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 10pt;
            }

            /* ==================== RESPONSIVE ==================== */
            @media (max-width: 768px) {
                body {
                    padding: 15px;
                }

                .summary-stats {
                    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                    gap: 10px;
                }

                .stat-value {
                    font-size: 20px;
                }

                h1 {
                    font-size: 24px;
                }

                h2 {
                    font-size: 18px;
                }
            }
        </style>
        """

    def _create_cover_page(self, title: str, subtitle: str, metadata: Dict[str, str]) -> str:
        """Create a professional cover page"""
        html = '<div class="cover-page page-break">'
        html += f'<div class="cover-title">{title}</div>'
        html += f'<div class="cover-subtitle">{subtitle}</div>'

        html += '<div class="cover-meta">'
        if metadata.get('project_name'):
            html += f'<div><strong>Project:</strong> {metadata["project_name"]}</div>'
        if metadata.get('location'):
            html += f'<div><strong>Location:</strong> {metadata["location"]}</div>'
        if metadata.get('client'):
            html += f'<div><strong>Client:</strong> {metadata["client"]}</div>'
        if metadata.get('analyst'):
            html += f'<div><strong>Analyst:</strong> {metadata["analyst"]}</div>'
        html += f'<div><strong>Date:</strong> {datetime.now().strftime("%B %d, %Y")}</div>'
        html += '</div>'
        html += '</div>'

        return html

    def _fig_to_base64(self, fig: Figure) -> str:
        """Convert a matplotlib figure to base64 encoded PNG"""
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)
        return f'data:image/png;base64,{image_base64}'

    def _create_grain_size_plot(self, dataset: GrainSizeData) -> str:
        """Create grain size distribution curve and return as base64"""
        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot cumulative distribution
        ax.semilogx(dataset.particle_sizes, dataset.percent_passing,
                   'o-', linewidth=2, markersize=6, color='#6b8e23',
                   markerfacecolor='white', markeredgewidth=2)

        ax.set_xlabel('Grain Size (mm)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Percent Passing (%)', fontsize=12, fontweight='bold')
        ax.set_title(f'Grain Size Distribution - {dataset.sample_name}',
                    fontsize=14, fontweight='bold', color='#2c5530')
        ax.grid(True, which='both', alpha=0.3, linestyle='--')
        ax.set_xlim(left=min(dataset.particle_sizes)*0.8, right=max(dataset.particle_sizes)*1.2)
        ax.set_ylim(0, 100)

        # Add characteristic grain size markers
        d10 = dataset.get_d10()
        d50 = dataset.get_d50()
        d60 = dataset.get_d60()

        for d_val, label, color in [(d10, 'D₁₀', '#ff6b6b'),
                                      (d50, 'D₅₀', '#4ecdc4'),
                                      (d60, 'D₆₀', '#95e1d3')]:
            if d_val:
                ax.axvline(d_val, color=color, linestyle='--', linewidth=1.5, alpha=0.7)
                ax.text(d_val, 95, label, rotation=0, verticalalignment='bottom',
                       fontweight='bold', color=color, fontsize=10)

        return self._fig_to_base64(fig)

    def _create_k_value_bar_chart(self, k_results: List[KCalculationResult]) -> str:
        """Create K-value comparison bar chart with error indication"""
        valid_results = [r for r in k_results if r.k_value is not None and r.k_value > 0]

        if not valid_results:
            return ""

        fig, ax = plt.subplots(figsize=(12, 6))

        methods = [r.method_name for r in valid_results]
        k_values = [r.k_value for r in valid_results]

        # Color code by status
        colors = []
        for r in valid_results:
            if "OK" in str(r.status):
                colors.append('#6bcf7f')  # Green
            elif "WARNING" in str(r.status):
                colors.append('#ffd93d')  # Yellow
            else:
                colors.append('#ff6b6b')  # Red

        bars = ax.bar(range(len(methods)), k_values, color=colors,
                     edgecolor='#333', linewidth=1.5, alpha=0.8)

        ax.set_yscale('log')
        ax.set_ylabel('Hydraulic Conductivity (m/s)', fontsize=12, fontweight='bold')
        ax.set_xlabel('Method', fontsize=12, fontweight='bold')
        ax.set_title('Hydraulic Conductivity Estimates by Method',
                    fontsize=14, fontweight='bold', color='#2c5530')
        ax.set_xticks(range(len(methods)))
        ax.set_xticklabels(methods, rotation=45, ha='right', fontsize=9)
        ax.grid(True, axis='y', alpha=0.3, linestyle='--')

        # Add mean line
        mean_k = np.mean(k_values)
        ax.axhline(mean_k, color='red', linestyle='--', linewidth=2,
                  label=f'Mean: {mean_k:.2e} m/s', alpha=0.7)
        ax.legend(loc='best')

        plt.tight_layout()
        return self._fig_to_base64(fig)

    def _create_method_applicability_heatmap(self, k_results: List[KCalculationResult]) -> str:
        """Create method applicability status heatmap"""
        if not k_results:
            return ""

        fig, ax = plt.subplots(figsize=(10, max(4, len(k_results) * 0.4)))

        # Create status matrix: 0 = N/A, 1 = Error, 2 = Warning, 3 = OK
        methods = [r.method_name for r in k_results]
        status_values = []
        status_labels = []

        for r in k_results:
            if r.k_value is None or r.k_value <= 0:
                status_values.append(0)
                status_labels.append('N/A')
            elif "OK" in str(r.status):
                status_values.append(3)
                status_labels.append('OK')
            elif "WARNING" in str(r.status):
                status_values.append(2)
                status_labels.append('Warning')
            else:
                status_values.append(1)
                status_labels.append('Error')

        # Reshape for heatmap
        data = np.array(status_values).reshape(-1, 1)

        # Create custom colormap
        colors_map = ['#cccccc', '#ff6b6b', '#ffd93d', '#6bcf7f']
        cmap = ListedColormap(colors_map)

        # Plot heatmap
        im = ax.imshow(data, cmap=cmap, aspect='auto', vmin=0, vmax=3)

        # Set ticks and labels
        ax.set_yticks(range(len(methods)))
        ax.set_yticklabels(methods, fontsize=10)
        ax.set_xticks([0])
        ax.set_xticklabels(['Status'], fontsize=11, fontweight='bold')
        ax.set_title('Method Applicability Status', fontsize=14, fontweight='bold', color='#2c5530')

        # Add text annotations
        for i, (val, label) in enumerate(zip(status_values, status_labels)):
            ax.text(0, i, label, ha='center', va='center',
                   fontweight='bold', fontsize=10,
                   color='white' if val in [1, 3] else 'black')

        plt.tight_layout()
        return self._fig_to_base64(fig)

    def _create_comparison_grain_size_plot(self, datasets: List[GrainSizeData]) -> str:
        """Create side-by-side grain size curves for comparison"""
        fig, ax = plt.subplots(figsize=(12, 7))

        colors = plt.cm.tab10(np.linspace(0, 1, len(datasets)))

        for dataset, color in zip(datasets, colors):
            ax.semilogx(dataset.particle_sizes, dataset.percent_passing,
                       'o-', linewidth=2, markersize=4, label=dataset.sample_name,
                       color=color, markerfacecolor='white', markeredgewidth=1.5)

        ax.set_xlabel('Grain Size (mm)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Percent Passing (%)', fontsize=12, fontweight='bold')
        ax.set_title('Grain Size Distribution Comparison',
                    fontsize=14, fontweight='bold', color='#2c5530')
        ax.grid(True, which='both', alpha=0.3, linestyle='--')
        ax.set_ylim(0, 100)
        ax.legend(loc='best', fontsize=9, framealpha=0.9)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    def _create_k_value_boxplot(self, k_results_dict: Dict[str, List[KCalculationResult]]) -> str:
        """Create box plots for K-value comparison across samples"""
        fig, ax = plt.subplots(figsize=(12, 7))

        data_for_plot = []
        labels = []

        for sample_name, results in k_results_dict.items():
            k_values = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]
            if k_values:
                data_for_plot.append(k_values)
                labels.append(sample_name)

        if not data_for_plot:
            plt.close(fig)
            return ""

        bp = ax.boxplot(data_for_plot, labels=labels, patch_artist=True,
                       showmeans=True, meanline=True,
                       boxprops=dict(facecolor='#d2b48c', alpha=0.7),
                       medianprops=dict(color='red', linewidth=2),
                       meanprops=dict(color='green', linewidth=2, linestyle='--'))

        ax.set_yscale('log')
        ax.set_ylabel('Hydraulic Conductivity (m/s)', fontsize=12, fontweight='bold')
        ax.set_xlabel('Sample', fontsize=12, fontweight='bold')
        ax.set_title('K-Value Distribution Comparison',
                    fontsize=14, fontweight='bold', color='#2c5530')
        ax.grid(True, axis='y', alpha=0.3, linestyle='--')

        # Rotate x-labels if needed
        if len(labels) > 5:
            ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    def _create_method_reliability_matrix(self, k_results_dict: Dict[str, List[KCalculationResult]]) -> str:
        """Create method reliability matrix for comparison report"""
        if not k_results_dict:
            return ""

        # Collect all unique methods
        all_methods = set()
        for results in k_results_dict.values():
            for r in results:
                all_methods.add(r.method_name)

        methods = sorted(list(all_methods))
        sample_names = list(k_results_dict.keys())

        if not methods or not sample_names:
            return ""

        fig, ax = plt.subplots(figsize=(max(10, len(sample_names) * 0.8),
                                        max(6, len(methods) * 0.5)))

        # Create status matrix
        matrix = np.zeros((len(methods), len(sample_names)))

        for j, sample_name in enumerate(sample_names):
            results = k_results_dict[sample_name]
            for i, method in enumerate(methods):
                # Find result for this method
                result = next((r for r in results if r.method_name == method), None)
                if result is None or result.k_value is None or result.k_value <= 0:
                    matrix[i, j] = 0  # N/A
                elif "OK" in str(result.status):
                    matrix[i, j] = 3  # OK
                elif "WARNING" in str(result.status):
                    matrix[i, j] = 2  # Warning
                else:
                    matrix[i, j] = 1  # Error

        # Create custom colormap
        colors_map = ['#cccccc', '#ff6b6b', '#ffd93d', '#6bcf7f']
        cmap = ListedColormap(colors_map)

        # Plot heatmap
        im = ax.imshow(matrix, cmap=cmap, aspect='auto', vmin=0, vmax=3)

        # Set ticks and labels
        ax.set_xticks(range(len(sample_names)))
        ax.set_xticklabels(sample_names, rotation=45, ha='right', fontsize=10)
        ax.set_yticks(range(len(methods)))
        ax.set_yticklabels(methods, fontsize=9)
        ax.set_title('Method Applicability Matrix - All Samples',
                    fontsize=14, fontweight='bold', color='#2c5530')

        # Add text annotations
        for i in range(len(methods)):
            for j in range(len(sample_names)):
                val = matrix[i, j]
                label = ['N/A', 'ERR', 'WARN', 'OK'][int(val)]
                ax.text(j, i, label, ha='center', va='center',
                       fontweight='bold', fontsize=8,
                       color='white' if val in [1, 3] else 'black')

        plt.tight_layout()
        return self._fig_to_base64(fig)

    def _format_metadata_section(self, metadata: Dict[str, str]) -> str:
        """Format project metadata section with modern grid layout"""
        html = '<div class="metadata"><div class="metadata-grid">'

        if metadata.get('project_name'):
            html += '<div class="metadata-label">Project:</div>'
            html += f'<div class="metadata-value">{metadata["project_name"]}</div>'
        if metadata.get('location'):
            html += '<div class="metadata-label">Location:</div>'
            html += f'<div class="metadata-value">{metadata["location"]}</div>'
        if metadata.get('client'):
            html += '<div class="metadata-label">Client:</div>'
            html += f'<div class="metadata-value">{metadata["client"]}</div>'
        if metadata.get('analyst'):
            html += '<div class="metadata-label">Analyst:</div>'
            html += f'<div class="metadata-value">{metadata["analyst"]}</div>'

        html += '<div class="metadata-label">Report Date:</div>'
        html += f'<div class="metadata-value">{datetime.now().strftime("%B %d, %Y at %H:%M")}</div>'
        html += '</div></div>'

        return html

    def generate_grain_size_report(self, dataset: GrainSizeData,
                                  metadata: Optional[Dict[str, str]] = None,
                                  sections: Optional[Dict[str, bool]] = None,
                                  report_template: str = "standard") -> str:
        """
        Generate a grain size analysis report for a single sample

        Args:
            dataset: GrainSizeData object containing the sample data
            metadata: Dictionary with project metadata (project_name, location, client, analyst, notes)
            sections: Dictionary controlling which sections to include
            report_template: Template style - "standard", "executive", "technical", "appendix"

        Returns:
            HTML string of the complete report
        """

        # Set defaults
        if metadata is None:
            metadata = {}
        if sections is None:
            # Default sections based on template
            if report_template == "executive":
                sections = {
                    'cover_page': True,
                    'executive_summary': True,
                    'methodology': False,
                    'results': True,
                    'plots': True,
                    'raw_data': False,
                    'interpretation': True,
                    'percentiles': False,
                    'gradation': True,
                    'data_quality': False
                }
            elif report_template == "technical":
                sections = {
                    'cover_page': True,
                    'executive_summary': True,
                    'methodology': True,
                    'results': True,
                    'plots': True,
                    'raw_data': False,
                    'interpretation': True,
                    'percentiles': True,
                    'gradation': True,
                    'data_quality': True
                }
            elif report_template == "appendix":
                sections = {
                    'cover_page': False,
                    'executive_summary': False,
                    'methodology': False,
                    'results': False,
                    'plots': True,
                    'raw_data': True,
                    'interpretation': False,
                    'percentiles': True,
                    'gradation': True,
                    'data_quality': True
                }
            else:  # standard
                sections = {
                    'cover_page': False,
                    'executive_summary': True,
                    'methodology': True,
                    'results': True,
                    'plots': True,
                    'raw_data': False,
                    'interpretation': True,
                    'percentiles': True,
                    'gradation': True,
                    'data_quality': False
                }

        # Get characteristic grain sizes
        d10 = dataset.get_d10()
        d20 = dataset.get_d20()
        d30 = dataset.get_d30()
        d50 = dataset.get_d50()
        d60 = dataset.get_d60()

        # Calculate coefficients
        cu = (d60 / d10) if (d10 and d60 and d10 > 0) else None
        cc = ((d30 * d30) / (d10 * d60)) if (d10 and d30 and d60 and d10 > 0 and d60 > 0) else None

        # Start HTML report
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grain Size Analysis Report - {dataset.sample_name}</title>
    {self.report_style}
</head>
<body>
"""

        # Cover Page (optional)
        if sections.get('cover_page', False):
            html += self._create_cover_page(
                "Grain Size Analysis",
                f"Sample: {dataset.sample_name}",
                metadata
            )

        # Main Title (if no cover page)
        if not sections.get('cover_page', False):
            html += f'<h1>Grain Size Analysis Report</h1>'
            html += self._format_metadata_section(metadata)

        # Sample Information
        html += f"""
<div class="metadata">
    <div class="metadata-grid">
        <div class="metadata-label">Sample Name:</div>
        <div class="metadata-value">{dataset.sample_name}</div>
        <div class="metadata-label">Soil Classification:</div>
        <div class="metadata-value"><strong>{dataset.classify_soil()}</strong></div>
        <div class="metadata-label">Temperature:</div>
        <div class="metadata-value">{dataset.temperature}°C</div>
        <div class="metadata-label">Porosity:</div>
        <div class="metadata-value">{dataset.porosity}</div>
        <div class="metadata-label">Data Points:</div>
        <div class="metadata-value">{len(dataset.particle_sizes)}</div>
    </div>
</div>
"""

        # Executive Summary
        if sections.get('executive_summary', True):
            html += f"""
<div class="no-break">
<h2>Executive Summary</h2>
<div class="success-box">
    <p>Sample <strong>{dataset.sample_name}</strong> has been analyzed and classified as <strong>{dataset.classify_soil()}</strong>.</p>
</div>
<div class="summary-stats">
    <div class="stat-card">
        <div class="stat-label">Median Size (D₅₀)</div>
        <div class="stat-value">{f'{d50:.3f}' if d50 else 'N/A'}</div>
        <div class="stat-unit">mm</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Uniformity (Cu)</div>
        <div class="stat-value">{f'{cu:.2f}' if cu else 'N/A'}</div>
        <div class="stat-unit">{self._classify_uniformity(cu)}</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Curvature (Cc)</div>
        <div class="stat-value">{f'{cc:.2f}' if cc else 'N/A'}</div>
        <div class="stat-unit">{self._classify_curvature(cc)}</div>
    </div>
</div>
</div>
"""

        # Methodology
        if sections.get('methodology', True):
            html += """
<div class="page-break">
<h2>Methodology</h2>
<div class="info-box">
    <h3>Grain Size Distribution Analysis</h3>
    <p>Grain size distribution was determined using sieve analysis and/or sedimentation methods following standard geotechnical procedures. The cumulative distribution curve plots percent passing versus grain size on a semi-logarithmic scale.</p>
</div>
<div class="info-box">
    <h3>Characteristic Diameters</h3>
    <p>Characteristic grain sizes represent specific percentiles of the grain size distribution:</p>
    <ul>
        <li><strong>D₁₀, D₃₀, D₅₀, D₆₀:</strong> Grain diameters at which 10%, 30%, 50%, and 60% of the soil mass is finer</li>
        <li><strong>D₅₀ (Median):</strong> The median grain size, representing the center of the distribution</li>
        <li>These values are fundamental for soil classification and hydraulic conductivity estimation</li>
    </ul>
</div>
<div class="info-box">
    <h3>Gradation Parameters</h3>
    <p><strong>Uniformity Coefficient:</strong> <code>Cu = D₆₀ / D₁₀</code></p>
    <ul>
        <li>Cu &lt; 4: Uniform gradation (narrow size range)</li>
        <li>4 ≤ Cu &lt; 6: Moderate gradation</li>
        <li>Cu ≥ 6: Well-graded soil (wide size range)</li>
    </ul>
    <p><strong>Coefficient of Curvature:</strong> <code>Cc = (D₃₀)² / (D₁₀ × D₆₀)</code></p>
    <ul>
        <li>1 ≤ Cc ≤ 3: Well-graded with good particle size distribution</li>
        <li>Outside this range: Gap-graded or uniform distribution</li>
    </ul>
</div>
</div>
"""

        # Results
        if sections.get('results', True):
            html += f"""
<div class="page-break">
<h2>Results & Analysis</h2>

<h3>Characteristic Grain Sizes</h3>
<div class="summary-stats">
    <div class="stat-card">
        <div class="stat-label">D₁₀</div>
        <div class="stat-value">{f'{d10:.3f}' if d10 else 'N/A'}</div>
        <div class="stat-unit">mm</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">D₃₀</div>
        <div class="stat-value">{f'{d30:.3f}' if d30 else 'N/A'}</div>
        <div class="stat-unit">mm</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">D₅₀</div>
        <div class="stat-value">{f'{d50:.3f}' if d50 else 'N/A'}</div>
        <div class="stat-unit">mm</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">D₆₀</div>
        <div class="stat-value">{f'{d60:.3f}' if d60 else 'N/A'}</div>
        <div class="stat-unit">mm</div>
    </div>
</div>

<h3>Soil Classification Parameters</h3>
<table>
    <thead>
        <tr>
            <th>Parameter</th>
            <th>Value</th>
            <th>Classification</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>Uniformity Coefficient</strong> (Cu = D₆₀/D₁₀)</td>
            <td class="text-center">{f'{cu:.2f}' if cu else 'N/A'}</td>
            <td><span class="badge badge-info">{self._classify_uniformity(cu)}</span></td>
        </tr>
        <tr>
            <td><strong>Coefficient of Curvature</strong> (Cc = D₃₀²/D₁₀·D₆₀)</td>
            <td class="text-center">{f'{cc:.2f}' if cc else 'N/A'}</td>
            <td><span class="badge badge-info">{self._classify_curvature(cc)}</span></td>
        </tr>
        <tr>
            <td><strong>Soil Classification</strong></td>
            <td colspan="2"><span class="badge badge-success">{dataset.classify_soil()}</span></td>
        </tr>
    </tbody>
</table>
"""

            if sections.get('gradation', True):
                html += f"<h3>Gradation Analysis</h3>{self._create_gradation_table(dataset)}"

            html += "</div>"

        # Visual Charts
        if sections.get('plots', True):
            grain_plot = self._create_grain_size_plot(dataset)
            html += f"""
<div class="page-break">
<h2>Grain Size Distribution Curve</h2>
<div class="plot-container">
    <img src="{grain_plot}" alt="Grain Size Distribution" />
    <div class="figure-caption">Figure 1: Cumulative grain size distribution curve for {dataset.sample_name}</div>
</div>
</div>
"""

        # Interpretation
        if sections.get('interpretation', True):
            html += f"""
<div class="page-break">
<h2>Interpretation & Discussion</h2>
<div class="info-box">
    <h3>Grain Size Distribution Analysis</h3>
    <p>{self._interpret_grain_distribution(dataset, cu, cc)}</p>
</div>
"""
            if metadata.get('notes'):
                html += f"""
<div class="info-box">
    <h3>Additional Notes</h3>
    <p>{metadata['notes'].replace(chr(10), '<br>')}</p>
</div>
"""
            html += "</div>"

        # APPENDIX SECTION - Clean, organized appendix
        appendix_items = []
        if sections.get('percentiles', True):
            appendix_items.append(('A', 'Detailed Percentile Data', self._create_percentiles_table(dataset)))
        if sections.get('data_quality', False):
            appendix_items.append(('B', 'Data Quality Assessment', self._create_data_quality_table(dataset)))
        if sections.get('raw_data', False):
            raw_data_table = '<table class="table-compact"><thead><tr><th>Grain Size (mm)</th><th>Percent Passing (%)</th><th>Percent Retained (%)</th></tr></thead><tbody>'
            for size, passing in zip(dataset.particle_sizes, dataset.percent_passing):
                retained = 100 - passing
                raw_data_table += f'<tr><td>{size:.4f}</td><td>{passing:.2f}</td><td>{retained:.2f}</td></tr>'
            raw_data_table += '</tbody></table>'
            appendix_items.append(('C', 'Raw Measurement Data', raw_data_table))

        if appendix_items:
            html += '<div class="appendix-section page-break">'
            html += '<h1 class="appendix-title">Appendices</h1>'

            for letter, title, content in appendix_items:
                html += f'''
<div class="appendix-item">
    <h3 class="appendix-item-title">Appendix {letter}: {title}</h3>
    {content}
</div>
'''
            html += '</div>'

        # Footer
        html += """
<div class="footer">
    <p><strong>Grain Size Analysis Report</strong></p>
    <p>Generated by Grain Size Analysis Tool - Hydraulic Conductivity Calculator</p>
    <p>© 2024 - Geotechnical Analysis Suite</p>
</div>
</body>
</html>
"""

        return html

    def generate_k_value_report(self, dataset: GrainSizeData,
                               k_results: List[KCalculationResult],
                               temperature: float,
                               porosity: float,
                               metadata: Optional[Dict[str, str]] = None,
                               sections: Optional[Dict[str, bool]] = None,
                               report_template: str = "standard") -> str:
        """
        Generate a hydraulic conductivity (K-value) report for a single sample

        Args:
            dataset: GrainSizeData object
            k_results: List of KCalculationResult objects from different methods
            temperature: Water temperature in °C
            porosity: Soil porosity
            metadata: Project metadata dictionary
            sections: Dictionary controlling which sections to include
            report_template: Template style - "standard", "executive", "technical", "appendix"

        Returns:
            HTML string of the complete report
        """

        # Set defaults
        if metadata is None:
            metadata = {}
        if sections is None:
            if report_template == "executive":
                sections = {
                    'cover_page': True,
                    'executive_summary': True,
                    'methodology': False,
                    'results': True,
                    'plots': True,
                    'interpretation': True,
                    'k_statistics': False
                }
            elif report_template == "technical":
                sections = {
                    'cover_page': True,
                    'executive_summary': True,
                    'methodology': True,
                    'results': True,
                    'plots': True,
                    'interpretation': True,
                    'k_statistics': True
                }
            elif report_template == "appendix":
                sections = {
                    'cover_page': False,
                    'executive_summary': False,
                    'methodology': False,
                    'results': False,
                    'plots': True,
                    'interpretation': False,
                    'k_statistics': True
                }
            else:  # standard
                sections = {
                    'cover_page': False,
                    'executive_summary': True,
                    'methodology': True,
                    'results': True,
                    'plots': True,
                    'interpretation': True,
                    'k_statistics': True
                }

        # Filter valid results
        valid_results = [r for r in k_results if r.k_value is not None and r.k_value > 0]

        if not valid_results:
            return self._generate_no_results_report(dataset.sample_name)

        # Calculate statistics
        k_values = [r.k_value for r in valid_results]
        mean_k = np.mean(k_values)
        median_k = np.median(k_values)
        std_k = np.std(k_values)
        min_k = np.min(k_values)
        max_k = np.max(k_values)
        variability_ratio = max_k / min_k if min_k > 0 else 0

        # Start HTML report
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hydraulic Conductivity Report - {dataset.sample_name}</title>
    {self.report_style}
</head>
<body>
"""

        # Cover Page (optional)
        if sections.get('cover_page', False):
            html += self._create_cover_page(
                "Hydraulic Conductivity Analysis",
                f"Sample: {dataset.sample_name}",
                metadata
            )

        # Main Title (if no cover page)
        if not sections.get('cover_page', False):
            html += f'<h1>Hydraulic Conductivity Analysis Report</h1>'
            html += self._format_metadata_section(metadata)

        # Sample Information
        html += f"""
<div class="metadata">
    <div class="metadata-grid">
        <div class="metadata-label">Sample Name:</div>
        <div class="metadata-value">{dataset.sample_name}</div>
        <div class="metadata-label">Temperature:</div>
        <div class="metadata-value">{temperature}°C</div>
        <div class="metadata-label">Porosity:</div>
        <div class="metadata-value">{porosity}</div>
        <div class="metadata-label">Methods Evaluated:</div>
        <div class="metadata-value">{len(k_results)} empirical methods</div>
        <div class="metadata-label">Valid Results:</div>
        <div class="metadata-value"><span class="badge badge-success">{len(valid_results)} / {len(k_results)}</span></div>
    </div>
</div>
"""

        # Executive Summary
        if sections.get('executive_summary', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Executive Summary</h2>
            <div class="info-box">
                <p><strong>Sample:</strong> {dataset.sample_name} hydraulic conductivity analysis using {len(k_results)} empirical methods.</p>
                <p><strong>Mean K-Value:</strong> {mean_k:.2e} m/s (from {len(valid_results)} valid methods)</p>
                <p><strong>Permeability Classification:</strong> {self._classify_permeability(mean_k)}</p>
                <p><strong>Variability:</strong> {max_k/min_k:.1f}x difference between minimum and maximum estimates</p>
            </div>
            </div>
            """

        # Methodology
        if sections.get('methodology', True):
            html += """
            <div style="page-break-before: auto;">
            <h2>Methodology</h2>
            <div class="info-box">
                <h3>Hydraulic Conductivity Estimation</h3>
                <p>Hydraulic conductivity (K) represents the ease with which water can move through pore spaces
                in soil. This analysis employs multiple empirical methods developed from various grain size
                parameters to estimate K-values for comparison and reliability assessment.</p>
                <h3>Empirical Methods</h3>
                <p>Each method has specific applicability ranges and underlying assumptions based on soil type,
                grain size distribution, and original calibration data. Methods include Hazen, Shepherd, Kozeny-Carman,
                Terzaghi, Breyer, Slichter, Sauerbrei, Kruger, Zunker, Zamarin, USBR, and Barr.</p>
                <h3>Quality Assessment</h3>
                <p>Each calculation is evaluated for applicability based on grain size parameters. Results are
                marked as OK (within recommended range), WARNING (outside optimal range), or ERROR (calculation failed).
                Statistical analysis of multiple methods provides confidence bounds on the estimated K-value.</p>
            </div>
            </div>
            """

        # Results
        if sections.get('results', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Results & Analysis</h2>

            <h3>Statistical Summary</h3>
            <div class="summary-stats">
                <div class="stat-card">
                    <div class="stat-label">Mean K</div>
                    <div class="stat-value">{mean_k:.2e} m/s</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Median K</div>
                    <div class="stat-value">{median_k:.2e} m/s</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Min K</div>
                    <div class="stat-value">{min_k:.2e} m/s</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Max K</div>
                    <div class="stat-value">{max_k:.2e} m/s</div>
                </div>
            </div>

            <h3>K-Value Calculations by Method</h3>
            <table>
                <tr>
                    <th>Method</th>
                    <th>K-Value (m/s)</th>
                    <th>Formula</th>
                    <th>Status</th>
                </tr>
            """

            for result in k_results:
                status_class = "success" if "OK" in str(result.status) else "warning"
                k_display = f"{result.k_value:.2e}" if result.k_value else "N/A"

                html += f"""
                <tr>
                    <td>{result.method_name}</td>
                    <td>{k_display}</td>
                    <td style="font-size: 11px;">{result.formula_used}</td>
                    <td><span class="{status_class}">{result.status_message or result.status}</span></td>
                </tr>
                """

            html += """
            </table>

            <h3>Permeability Classification</h3>
            <div class="info-box">
                <p><strong>Classification:</strong> {}</p>
                <p><strong>Typical Application:</strong> {}</p>
            </div>
            """.format(self._classify_permeability(mean_k), self._get_permeability_application(mean_k))

            # Add detailed K-value statistics
            if sections.get('k_statistics', True):
                html += f"<h3>Detailed K-Value Statistics</h3>{self._create_k_statistics_table(k_results)}"

            html += "</div>"

        # Visual Charts
        if sections.get('plots', True):
            k_bar_chart = self._create_k_value_bar_chart(k_results)
            method_heatmap = self._create_method_applicability_heatmap(k_results)

            if k_bar_chart:
                html += f"""
                <div style="page-break-before: auto;">
                <h2>K-Value Comparison Chart</h2>
                <div class="plot-container">
                    <img src="{k_bar_chart}" alt="K-Value Bar Chart" style="max-width: 100%; height: auto;">
                </div>
                </div>
                """

            if method_heatmap:
                html += f"""
                <div style="page-break-before: auto;">
                <h2>Method Applicability Status</h2>
                <div class="plot-container">
                    <img src="{method_heatmap}" alt="Method Applicability Heatmap" style="max-width: 100%; height: auto;">
                </div>
                </div>
                """

        # Interpretation
        if sections.get('interpretation', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Interpretation & Discussion</h2>
            <div class="info-box">
                <h3>Method Variability Analysis</h3>
                <p><strong>Variability:</strong> {max_k/min_k:.1f}x difference between min and max</p>
                <p><strong>Standard Deviation:</strong> {std_k:.2e} m/s</p>
                <p><strong>Coefficient of Variation:</strong> {(std_k/mean_k)*100:.1f}%</p>
                <p>{self._interpret_k_variability(max_k/min_k)}</p>
            </div>
            """

            # Add custom notes if provided
            if metadata.get('notes'):
                html += f"""
                <div class="info-box">
                    <h3>Additional Notes</h3>
                    <p>{metadata['notes'].replace(chr(10), '<br>')}</p>
                </div>
                """

            html += "</div>"

        # Add footer
        html += """
            <div class="footer">
                <p>Generated by Grain Size Analysis Tool - Hydraulic Conductivity Calculator</p>
                <p>© 2024 - Geotechnical Analysis Suite</p>
            </div>
        </body>
        </html>
        """

        return html

    def generate_combined_report(self, dataset: GrainSizeData,
                                k_results: List[KCalculationResult],
                                temperature: float,
                                porosity: float,
                                metadata: Optional[Dict[str, str]] = None,
                                sections: Optional[Dict[str, bool]] = None) -> str:
        """Generate a combined report with both grain size and K-value analysis"""

        # Set defaults
        if metadata is None:
            metadata = {}
        if sections is None:
            sections = {
                'executive_summary': True,
                'methodology': True,
                'results': True,
                'plots': True,
                'raw_data': False,
                'interpretation': True
            }

        # Generate both reports with shared metadata and sections
        grain_report = self.generate_grain_size_report(dataset, metadata=metadata, sections=sections)
        k_report = self.generate_k_value_report(dataset, k_results, temperature, porosity,
                                                metadata=metadata, sections=sections)

        # Extract body content from both reports
        grain_body = grain_report.split('<body>')[1].split('</body>')[0]
        k_body = k_report.split('<h1>Hydraulic Conductivity Analysis Report</h1>')[1].split('</body>')[0]

        # Create combined report with page break between sections
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Complete Analysis Report - {dataset.sample_name}</title>
            {self.report_style}
        </head>
        <body>
            {grain_body.replace('</body>', '').replace('</html>', '')}

            <div style="page-break-before: always;"></div>

            <h1>Hydraulic Conductivity Analysis</h1>
            {k_body}
        </body>
        </html>
        """

        return html

    def generate_comparison_report(self, datasets: List[GrainSizeData],
                                  k_results_dict: Dict[str, List[KCalculationResult]],
                                  temperature: float,
                                  porosity: float,
                                  metadata: Optional[Dict[str, str]] = None,
                                  sections: Optional[Dict[str, bool]] = None) -> str:
        """Generate a comparison report for multiple samples"""

        # Set defaults
        if metadata is None:
            metadata = {}
        if sections is None:
            sections = {
                'executive_summary': True,
                'methodology': True,
                'results': True,
                'plots': True,
                'interpretation': True,
                'grain_comparison': True,
                'k_statistics': True
            }

        # Calculate K-values for summary
        mean_k_by_sample = {}
        for name, results in k_results_dict.items():
            k_values = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]
            if k_values:
                mean_k_by_sample[name] = np.mean(k_values)

        # Start HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Multi-Sample Comparison Report</title>
            {self.report_style}
        </head>
        <body>
            <h1>Multi-Sample Comparison Report</h1>

            {self._format_metadata_section(metadata)}

            <div class="metadata">
                <p><strong>Number of Samples:</strong> {len(datasets)}</p>
                <p><strong>Temperature:</strong> {temperature}°C</p>
                <p><strong>Porosity:</strong> {porosity}</p>
            </div>
        """

        # Executive Summary
        if sections.get('executive_summary', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Executive Summary</h2>
            <div class="info-box">
                <p><strong>Comparison Analysis:</strong> This report compares {len(datasets)} soil samples
                based on grain size distribution and hydraulic conductivity estimates.</p>
            """

            if mean_k_by_sample:
                highest = max(mean_k_by_sample.items(), key=lambda x: x[1])
                lowest = min(mean_k_by_sample.items(), key=lambda x: x[1])
                html += f"""
                <p><strong>Key Findings:</strong></p>
                <ul>
                    <li>Highest permeability: {highest[0]} ({highest[1]:.2e} m/s)</li>
                    <li>Lowest permeability: {lowest[0]} ({lowest[1]:.2e} m/s)</li>
                    <li>Permeability range: {highest[1]/lowest[1]:.1f}x difference</li>
                </ul>
                """

            html += """
            </div>
            </div>
            """

        # Methodology
        if sections.get('methodology', True):
            html += """
            <div style="page-break-before: auto;">
            <h2>Methodology</h2>
            <div class="info-box">
                <h3>Comparative Analysis Approach</h3>
                <p>This comparison report presents a side-by-side analysis of multiple soil samples
                to identify patterns, variations, and relationships between grain size characteristics
                and hydraulic conductivity estimates.</p>
                <h3>Analysis Components</h3>
                <p><strong>Grain Size Comparison:</strong> Overlapping distribution curves allow visual
                assessment of particle size variations between samples.</p>
                <p><strong>K-Value Comparison:</strong> Box plots and statistical summaries reveal the
                range and reliability of hydraulic conductivity estimates across samples.</p>
                <p><strong>Method Reliability:</strong> A reliability matrix shows which empirical methods
                are applicable for each sample, helping identify the most suitable estimation approaches.</p>
            </div>
            </div>
            """

        # Results
        if sections.get('results', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Results & Analysis</h2>

            <h3>Sample Overview</h3>
            <table>
                <thead>
                    <tr>
                        <th>Sample</th>
                        <th>D₁₀ (mm)</th>
                        <th>D₅₀ (mm)</th>
                        <th>D₆₀ (mm)</th>
                        <th>Cu</th>
                        <th>Soil Type</th>
                        <th>Mean K (m/s)</th>
                    </tr>
                </thead>
                <tbody>
            """

            for dataset in datasets:
                d10 = dataset.get_d10()
                d50 = dataset.get_d50()
                d60 = dataset.get_d60()
                cu = (d60/d10) if (d10 and d60) else None

                # Get mean K if available
                mean_k = "N/A"
                if dataset.sample_name in mean_k_by_sample:
                    mean_k = f"{mean_k_by_sample[dataset.sample_name]:.2e}"

                html += f"""
                <tr>
                    <td>{dataset.sample_name}</td>
                    <td>{f'{d10:.3f}' if d10 else 'N/A'}</td>
                    <td>{f'{d50:.3f}' if d50 else 'N/A'}</td>
                    <td>{f'{d60:.3f}' if d60 else 'N/A'}</td>
                    <td>{f'{cu:.2f}' if cu else 'N/A'}</td>
                    <td>{dataset.classify_soil()}</td>
                    <td>{mean_k}</td>
                </tr>
                """

            html += "</tbody></table>"

            # Add comprehensive comparison tables
            if sections.get('grain_comparison', True):
                html += f"<h3>Grain Parameters Comparison</h3>{self._create_grain_parameters_comparison_table(datasets)}"

            if sections.get('k_statistics', True) and k_results_dict:
                html += f"<h3>Permeability Classification Summary</h3>{self._create_permeability_classification_table(k_results_dict)}"

            html += "</div>"

        # Visual Charts
        if sections.get('plots', True):
            comparison_plot = self._create_comparison_grain_size_plot(datasets)
            k_boxplot = self._create_k_value_boxplot(k_results_dict)
            reliability_matrix = self._create_method_reliability_matrix(k_results_dict)

            if comparison_plot:
                html += f"""
                <div style="page-break-before: auto;">
                <h2>Grain Size Distribution Comparison</h2>
                <div class="plot-container">
                    <img src="{comparison_plot}" alt="Grain Size Comparison" style="max-width: 100%; height: auto;">
                </div>
                </div>
                """

            if k_boxplot:
                html += f"""
                <div style="page-break-before: auto;">
                <h2>Hydraulic Conductivity Distribution</h2>
                <div class="plot-container">
                    <img src="{k_boxplot}" alt="K-Value Boxplot" style="max-width: 100%; height: auto;">
                </div>
                </div>
                """

            if reliability_matrix:
                html += f"""
                <div style="page-break-before: always;">
                <h2>Appendix: Method Reliability Matrix</h2>
                <div class="plot-container">
                    <img src="{reliability_matrix}" alt="Method Reliability Matrix" style="max-width: 100%; height: auto;">
                </div>
                </div>
                """

        # Interpretation
        if sections.get('interpretation', True):
            html += """
            <div style="page-break-before: auto;">
            <h2>Interpretation & Discussion</h2>
            <div class="info-box">
                <h3>Comparative Analysis</h3>
            """

            if mean_k_by_sample:
                highest = max(mean_k_by_sample.items(), key=lambda x: x[1])
                lowest = min(mean_k_by_sample.items(), key=lambda x: x[1])

                html += f"""
                <p><strong>Permeability Characteristics:</strong></p>
                <ul>
                    <li>The highest permeability sample is {highest[0]} with K = {highest[1]:.2e} m/s,
                    classified as {self._classify_permeability(highest[1])}.</li>
                    <li>The lowest permeability sample is {lowest[0]} with K = {lowest[1]:.2e} m/s,
                    classified as {self._classify_permeability(lowest[1])}.</li>
                    <li>The {highest[1]/lowest[1]:.1f}-fold difference in permeability reflects the
                    variability in grain size distribution among the samples.</li>
                </ul>
                """

                # Statistical analysis
                all_k_values = list(mean_k_by_sample.values())
                mean_all = np.mean(all_k_values)
                std_all = np.std(all_k_values)

                html += f"""
                <p><strong>Statistical Overview:</strong></p>
                <ul>
                    <li>Mean K-value across all samples: {mean_all:.2e} m/s</li>
                    <li>Standard deviation: {std_all:.2e} m/s</li>
                    <li>Coefficient of variation: {(std_all/mean_all)*100:.1f}%</li>
                </ul>
                """

            html += """
            </div>
            """

            # Add custom notes if provided
            if metadata.get('notes'):
                html += f"""
                <div class="info-box">
                    <h3>Additional Notes</h3>
                    <p>{metadata['notes'].replace(chr(10), '<br>')}</p>
                </div>
                """

            html += "</div>"

        # Add footer
        html += """
            <div class="footer">
                <p>Generated by Grain Size Analysis Tool - Hydraulic Conductivity Calculator</p>
                <p>© 2024 - Geotechnical Analysis Suite</p>
            </div>
        </body>
        </html>
        """

        return html

    # Helper methods
    def _classify_uniformity(self, cu: Optional[float]) -> str:
        if cu is None:
            return "Cannot calculate"
        elif cu < 4:
            return "Uniform (Cu < 4)"
        elif cu < 6:
            return "Moderately graded (4 ≤ Cu < 6)"
        else:
            return "Well-graded (Cu ≥ 6)"

    def _classify_curvature(self, cc: Optional[float]) -> str:
        if cc is None:
            return "Cannot calculate"
        elif 1 <= cc <= 3:
            return "Well-graded (1 ≤ Cc ≤ 3)"
        else:
            return "Gap-graded or Uniform"

    def _create_percentiles_table(self, dataset: GrainSizeData) -> str:
        """Generate HTML table with percentiles (D5, D10, D16, D20, D25, D30, D40, D50, D60, D75, D84, D90, D95)"""
        percentiles_list = [5, 10, 16, 20, 25, 30, 40, 50, 60, 75, 84, 90, 95]

        # Calculate percentiles using interpolation
        percentiles_dict = {}
        for p in percentiles_list:
            value = np.interp(p, dataset.percent_passing, dataset.particle_sizes)
            percentiles_dict[p] = value

        # Find max value for bar scaling
        max_val = max(percentiles_dict.values())

        html = """
        <table>
            <thead>
                <tr>
                    <th>Percentile</th>
                    <th>Size (mm)</th>
                    <th>Relative (%)</th>
                </tr>
            </thead>
            <tbody>
        """

        for p in percentiles_list:
            val = percentiles_dict[p]
            bar_width = int((val / max_val) * 100) if max_val > 0 else 0

            # Highlight key percentiles (D10, D30, D50, D60)
            is_key = p in [10, 30, 50, 60]

            html += f"""
            <tr>
                <td style="text-align: center;"><strong>D{p}{'*' if is_key else ''}</strong></td>
                <td style="text-align: right;">{val:.3f}</td>
                <td style="text-align: right;">{bar_width}%</td>
            </tr>
            """

        html += "</tbody></table>"
        return html

    def _create_gradation_table(self, dataset: GrainSizeData) -> str:
        """Generate HTML table showing gradation breakdown (Gravel %, Sand %, Fines %)"""
        # Gradation boundaries: Fines (<0.063mm), Sand (0.063-2mm), Gravel (>2mm)
        gravel_percent = 0
        sand_percent = 0
        fines_percent = 0

        # Calculate percentages based on percent passing
        for i, size in enumerate(dataset.particle_sizes):
            if i == 0:
                continue

            prev_size = dataset.particle_sizes[i-1]
            prev_passing = dataset.percent_passing[i-1]
            curr_passing = dataset.percent_passing[i]

            # Fraction retained in this interval
            retained = prev_passing - curr_passing

            # Classify based on size
            if prev_size > 2.0:
                gravel_percent += retained
            elif prev_size > 0.063:
                sand_percent += retained
            else:
                fines_percent += retained

        # Handle edge cases
        if dataset.particle_sizes[0] > 2.0:
            gravel_percent += 100 - dataset.percent_passing[0]
        elif dataset.particle_sizes[0] > 0.063:
            sand_percent += 100 - dataset.percent_passing[0]
        else:
            fines_percent += 100 - dataset.percent_passing[0]

        if dataset.particle_sizes[-1] < 0.063:
            fines_percent += dataset.percent_passing[-1]
        elif dataset.particle_sizes[-1] < 2.0:
            sand_percent += dataset.percent_passing[-1]
        else:
            gravel_percent += dataset.percent_passing[-1]

        html = """
        <table>
            <thead>
                <tr>
                    <th>Fraction</th>
                    <th>Size Range</th>
                    <th>Percentage</th>
                </tr>
            </thead>
            <tbody>
        """

        gradations = [
            ("Gravel", "> 2 mm", gravel_percent),
            ("Sand", "0.063 - 2 mm", sand_percent),
            ("Fines", "< 0.063 mm", fines_percent)
        ]

        for name, size_range, percent in gradations:
            html += f"""
            <tr>
                <td><strong>{name}</strong></td>
                <td>{size_range}</td>
                <td style="text-align: right;"><strong>{percent:.1f}%</strong></td>
            </tr>
            """

        html += "</tbody></table>"
        return html

    def _create_k_statistics_table(self, k_results: List[KCalculationResult]) -> str:
        """Generate HTML table with K-value statistics: Method, K-value, Status, Applicability Range"""
        html = """
        <table>
            <tr>
                <th>Method</th>
                <th>K-Value (m/s)</th>
                <th>Status</th>
                <th>Applicability Notes</th>
            </tr>
        """

        for result in k_results:
            # Determine status text
            status_str = str(result.status) if hasattr(result.status, 'value') else str(result.status)

            if "OK" in status_str or "WITHIN_RANGE" in status_str:
                status_text = "OK"
            elif "WARNING" in status_str or "OUTSIDE_RANGE" in status_str:
                status_text = "Warning"
            else:
                status_text = "Error"

            k_display = f"{result.k_value:.2e}" if result.k_value else "N/A"

            # Get status message or default text
            notes = result.status_message if hasattr(result, 'status_message') and result.status_message else status_str

            html += f"""
            <tr>
                <td><strong>{result.method_name}</strong></td>
                <td style="text-align: right;">{k_display}</td>
                <td style="text-align: center;">{status_text}</td>
                <td>{notes}</td>
            </tr>
            """

        html += "</table>"
        return html

    def _create_data_quality_table(self, dataset: GrainSizeData) -> str:
        """Generate HTML table showing data quality metrics"""
        n_points = len(dataset.particle_sizes)
        size_min = min(dataset.particle_sizes)
        size_max = max(dataset.particle_sizes)
        size_range = size_max / size_min if size_min > 0 else 0

        # Check monotonicity
        sorted_indices = np.argsort(dataset.particle_sizes)[::-1]
        sorted_passing = [dataset.percent_passing[i] for i in sorted_indices]

        monotonic = all(sorted_passing[i] >= sorted_passing[i+1] for i in range(len(sorted_passing)-1))
        monotonicity_score = "Excellent" if monotonic else "Good"

        # Data coverage (log scale)
        coverage_score = "Excellent" if size_range > 100 else "Good" if size_range > 10 else "Limited"

        # Point density
        avg_spacing = np.mean([abs(dataset.particle_sizes[i] - dataset.particle_sizes[i-1])
                               for i in range(1, len(dataset.particle_sizes))])
        density_score = "Excellent" if n_points > 20 else "Good" if n_points > 10 else "Adequate"

        # Interpolation confidence
        confidence_score = "High" if (n_points > 15 and size_range > 50) else "Moderate" if n_points > 8 else "Low"

        html = """
        <table>
            <tr>
                <th>Quality Metric</th>
                <th>Value</th>
                <th>Assessment</th>
            </tr>
        """

        metrics = [
            ("Number of Data Points", str(n_points), density_score),
            ("Size Range", f"{size_min:.3f} - {size_max:.1f} mm", coverage_score),
            ("Span Ratio", f"{size_range:.1f}x", coverage_score),
            ("Curve Monotonicity", "Monotonic" if monotonic else "Some variation", monotonicity_score),
            ("Interpolation Confidence", "", confidence_score)
        ]

        for metric, value, assessment in metrics:
            # Color code assessment
            if assessment in ["Excellent", "High"]:
                color = "#e8f5e9"
            elif assessment in ["Good", "Moderate"]:
                color = "#fff9e6"
            else:
                color = "#ffebee"

            html += f"""
            <tr>
                <td style="font-weight: bold;">{metric}</td>
                <td>{value}</td>
                <td style="background-color: {color}; text-align: center;">{assessment}</td>
            </tr>
            """

        html += "</table>"
        return html

    def _create_grain_parameters_comparison_table(self, datasets: List[GrainSizeData]) -> str:
        """Generate HTML comparison table with color-coded cells showing D10, D50, D60, Cu, Cc for all samples"""
        html = """
        <table>
            <thead>
                <tr>
                    <th>Parameter</th>
        """

        # Add column headers for each dataset
        for dataset in datasets:
            html += f"<th>{dataset.sample_name}</th>"

        # Add statistics column
        html += "<th>Statistics</th>"
        html += """
                </tr>
            </thead>
            <tbody>
        """

        # Parameters to compare
        params = ["D₁₀ (mm)", "D₅₀ (mm)", "D₆₀ (mm)", "Cu", "Cc"]

        for param in params:
            html += f"<tr><td style='font-weight: bold;'>{param}</td>"

            # Collect values for this parameter
            values = []
            for dataset in datasets:
                if param == "D₁₀ (mm)":
                    val = dataset.get_d10()
                elif param == "D₅₀ (mm)":
                    val = dataset.get_d50()
                elif param == "D₆₀ (mm)":
                    val = dataset.get_d60()
                elif param == "Cu":
                    d10 = dataset.get_d10()
                    d60 = dataset.get_d60()
                    val = (d60 / d10) if (d10 and d60 and d10 > 0) else None
                elif param == "Cc":
                    d10 = dataset.get_d10()
                    d30 = dataset.get_d30()
                    d60 = dataset.get_d60()
                    val = ((d30 * d30) / (d10 * d60)) if (d10 and d30 and d60 and d10 > 0 and d60 > 0) else None
                else:
                    val = None

                values.append(val)

            # Filter valid values for statistics and color-coding
            valid_values = [v for v in values if v is not None]

            # Calculate color scale
            if len(valid_values) > 1:
                min_val = min(valid_values)
                max_val = max(valid_values)
                val_range = max_val - min_val
            else:
                min_val = max_val = val_range = 0

            # Add cells without color-coding (clean and simple)
            for val in values:
                if val is None:
                    html += "<td style='text-align: center;'>—</td>"
                else:
                    display_val = f"{val:.3f}" if param.endswith("(mm)") else f"{val:.2f}"
                    html += f"<td style='text-align: center;'>{display_val}</td>"

            # Add statistics column
            if valid_values:
                mean = np.mean(valid_values)
                std = np.std(valid_values)

                stats_text = f"Mean: {mean:.2f}<br>Std: {std:.2f}"
                html += f"<td style='text-align: center; font-size: 9pt;'>{stats_text}</td>"
            else:
                html += "<td style='text-align: center;'>—</td>"

            html += "</tr>"

        html += "</tbody></table>"
        return html

    def _create_permeability_classification_table(self, k_results_dict: Dict[str, List[KCalculationResult]]) -> str:
        """Generate HTML table with sample name, mean K-value, classification, and color-coded background"""
        html = """
        <table>
            <thead>
                <tr>
                    <th>Sample Name</th>
                    <th>Mean K-Value (m/s)</th>
                    <th>Classification</th>
                </tr>
            </thead>
            <tbody>
        """

        for sample_name, results in k_results_dict.items():
            # Calculate mean K-value
            valid_k = [r.k_value for r in results if r.k_value and r.k_value > 0]

            if valid_k:
                mean_k = np.mean(valid_k)

                # Classify without color-coding
                if mean_k > 1e-2:
                    classification = "Very High (Gravel)"
                elif mean_k > 1e-4:
                    classification = "High (Clean Sand)"
                elif mean_k > 1e-5:
                    classification = "Moderate (Fine Sand)"
                elif mean_k > 1e-7:
                    classification = "Low (Silt)"
                else:
                    classification = "Very Low (Clay)"

                html += f"""
                <tr>
                    <td><strong>{sample_name}</strong></td>
                    <td style="text-align: right;">{mean_k:.2e}</td>
                    <td>{classification}</td>
                </tr>
                """
            else:
                html += f"""
                <tr>
                    <td><strong>{sample_name}</strong></td>
                    <td style="text-align: center;">—</td>
                    <td style="text-align: center;">—</td>
                </tr>
                """

        html += "</tbody></table>"
        return html

    def _classify_permeability(self, k: float) -> str:
        if k > 1e-2:
            return "Very High Permeability (Clean Gravel)"
        elif k > 1e-4:
            return "High Permeability (Clean Sand/Sand-Gravel Mix)"
        elif k > 1e-5:
            return "Moderate Permeability (Fine Sand)"
        elif k > 1e-7:
            return "Low Permeability (Silt/Silty Sand)"
        elif k > 1e-9:
            return "Very Low Permeability (Clay-Silt Mix)"
        else:
            return "Practically Impermeable (Clay)"

    def _get_permeability_application(self, k: float) -> str:
        if k > 1e-2:
            return "Excellent for drainage, unsuitable for water retention"
        elif k > 1e-4:
            return "Good for drainage systems, aquifers"
        elif k > 1e-5:
            return "Suitable for sand filters, moderate drainage"
        elif k > 1e-7:
            return "Poor drainage, may require improvement for construction"
        elif k > 1e-9:
            return "Natural barrier, suitable for liner with treatment"
        else:
            return "Excellent barrier material, natural aquitard"

    def _interpret_grain_distribution(self, dataset: GrainSizeData, cu: Optional[float], cc: Optional[float]) -> str:
        interpretation = f"The sample '{dataset.sample_name}' has been classified as {dataset.classify_soil()}. "

        if cu:
            if cu < 4:
                interpretation += "The uniform gradation (Cu < 4) indicates particles of similar size, "
                interpretation += "which typically results in higher void ratios and permeability. "
            elif cu < 6:
                interpretation += "The moderate gradation (4 ≤ Cu < 6) suggests a reasonable distribution of particle sizes. "
            else:
                interpretation += "The well-graded nature (Cu ≥ 6) indicates a wide range of particle sizes, "
                interpretation += "which typically results in better compaction and lower permeability. "

        if cc and cu and cu >= 6:
            if 1 <= cc <= 3:
                interpretation += "The coefficient of curvature confirms well-graded material with good particle size distribution. "
            else:
                interpretation += "However, the coefficient of curvature suggests some gap-grading in the distribution. "

        return interpretation

    def _interpret_k_variability(self, ratio: float) -> str:
        if ratio < 10:
            return "The relatively low variability between methods suggests consistent and reliable results."
        elif ratio < 100:
            return "Moderate variability between methods is typical for this type of analysis. Consider using the median value."
        else:
            return "High variability between methods indicates uncertainty. Review input parameters and consider site-specific calibration."

    def _generate_no_results_report(self, sample_name: str) -> str:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>K-Value Report - {sample_name}</title>
            {self.report_style}
        </head>
        <body>
            <h1>Hydraulic Conductivity Analysis Report</h1>
            <div class="warning-box">
                <h3>No Valid Results</h3>
                <p>No valid K-value calculations were obtained for sample '{sample_name}'.</p>
                <p>This may be due to:</p>
                <ul>
                    <li>Grain size parameters outside method applicability ranges</li>
                    <li>Missing required grain size data (D10, D60, etc.)</li>
                    <li>Invalid input parameters</li>
                </ul>
                <p>Please review the input data and ensure all required parameters are available.</p>
            </div>
        </body>
        </html>
        """

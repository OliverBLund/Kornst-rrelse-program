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
        self.report_style = """
        <style>
            * {
                box-sizing: border-box;
            }

            body {
                font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.7;
                color: #2c3e50;
                max-width: 900px;
                margin: 0 auto;
                padding: 40px 30px;
                background-color: #ffffff;
            }

            /* Typography Hierarchy */
            h1 {
                color: #2c5530;
                font-size: 32px;
                font-weight: 700;
                margin: 40px 0 25px 0;
                padding-bottom: 15px;
                border-bottom: 4px solid #6b8e23;
                letter-spacing: -0.5px;
            }

            h2 {
                color: #5d4e37;
                font-size: 24px;
                font-weight: 600;
                margin: 35px 0 20px 0;
                padding: 12px 0 12px 15px;
                border-left: 5px solid #8b7355;
                background: linear-gradient(to right, #f5f5f0 0%, transparent 100%);
            }

            h3 {
                color: #6b5b47;
                font-size: 18px;
                font-weight: 600;
                margin: 25px 0 15px 0;
                padding-bottom: 8px;
                border-bottom: 2px solid #e0d8cd;
            }

            p {
                margin: 12px 0;
                line-height: 1.8;
            }

            /* Metadata Sections */
            .metadata {
                background: linear-gradient(135deg, #fafaf7 0%, #f5f5f0 100%);
                border: 1px solid #d4c4a8;
                border-radius: 8px;
                padding: 20px 25px;
                margin: 25px 0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }

            .metadata p {
                margin: 10px 0;
                font-size: 14px;
                line-height: 1.6;
            }

            .metadata strong {
                color: #5d4e37;
                font-weight: 600;
                min-width: 140px;
                display: inline-block;
            }

            /* Info Boxes */
            .info-box {
                background-color: #f8f9fa;
                border-left: 5px solid #6b8e23;
                padding: 20px 25px;
                margin: 25px 0;
                border-radius: 0 6px 6px 0;
                box-shadow: 0 2px 6px rgba(0,0,0,0.06);
            }

            .info-box h3 {
                margin-top: 0;
                color: #2c5530;
                border: none;
            }

            .info-box p {
                margin: 10px 0;
                color: #34495e;
            }

            .warning-box {
                background-color: #fffbf0;
                border-left: 5px solid #ffc107;
                padding: 20px 25px;
                margin: 25px 0;
                border-radius: 0 6px 6px 0;
                box-shadow: 0 2px 6px rgba(255,193,7,0.15);
            }

            .success-box {
                background-color: #f0f9f4;
                border-left: 5px solid #4caf50;
                padding: 20px 25px;
                margin: 25px 0;
                border-radius: 0 6px 6px 0;
                box-shadow: 0 2px 6px rgba(76,175,80,0.15);
            }

            /* Tables */
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 25px 0;
                background-color: #fff;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                border-radius: 6px;
                overflow: hidden;
            }

            thead {
                background: linear-gradient(135deg, #8b7355 0%, #6b5b47 100%);
            }

            th {
                color: white;
                padding: 14px 12px;
                text-align: left;
                font-weight: 600;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            td {
                padding: 12px;
                border-bottom: 1px solid #e8e4df;
                font-size: 14px;
                vertical-align: middle;
            }

            tr:nth-child(even) {
                background-color: #fafaf7;
            }

            tr:last-child td {
                border-bottom: none;
            }

            tbody tr:hover {
                background-color: #f0ebe5;
                transition: background-color 0.2s ease;
            }

            /* Stat Cards */
            .summary-stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }

            .stat-card {
                background: linear-gradient(135deg, #ffffff 0%, #fafaf7 100%);
                padding: 20px;
                border-radius: 10px;
                border: 2px solid #d4c4a8;
                text-align: center;
                box-shadow: 0 4px 10px rgba(0,0,0,0.08);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }

            .stat-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 16px rgba(0,0,0,0.12);
            }

            .stat-label {
                font-size: 11px;
                color: #7f8c8d;
                text-transform: uppercase;
                letter-spacing: 1.2px;
                font-weight: 600;
                margin-bottom: 8px;
            }

            .stat-value {
                font-size: 28px;
                font-weight: 700;
                color: #2c5530;
                margin-top: 8px;
                line-height: 1.2;
            }

            /* Plot Container */
            .plot-container {
                text-align: center;
                margin: 30px 0;
                padding: 20px;
                background-color: #ffffff;
                border: 1px solid #d4c4a8;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            }

            .plot-container img {
                max-width: 100%;
                height: auto;
                border-radius: 4px;
            }

            /* Footer */
            .footer {
                margin-top: 60px;
                padding-top: 25px;
                border-top: 2px solid #e0d8cd;
                text-align: center;
                color: #95a5a6;
                font-size: 12px;
                line-height: 1.6;
            }

            /* Section Dividers */
            .section-divider {
                height: 2px;
                background: linear-gradient(to right, transparent, #d4c4a8, transparent);
                margin: 40px 0;
                border: none;
            }

            /* Utility Classes */
            .highlight {
                background-color: #fff9e6;
                padding: 2px 6px;
                border-radius: 3px;
            }

            strong {
                font-weight: 600;
                color: #2c3e50;
            }
        </style>
        """

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
        """Format project metadata section"""
        html = '<div class="metadata">'

        if metadata.get('project_name'):
            html += f'<p><strong>Project:</strong> {metadata["project_name"]}</p>'
        if metadata.get('location'):
            html += f'<p><strong>Location:</strong> {metadata["location"]}</p>'
        if metadata.get('client'):
            html += f'<p><strong>Client:</strong> {metadata["client"]}</p>'
        if metadata.get('analyst'):
            html += f'<p><strong>Analyst:</strong> {metadata["analyst"]}</p>'

        html += f'<p><strong>Report Date:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>'
        html += '</div>'

        return html

    def generate_grain_size_report(self, dataset: GrainSizeData,
                                  metadata: Optional[Dict[str, str]] = None,
                                  sections: Optional[Dict[str, bool]] = None) -> str:
        """Generate a grain size analysis report for a single sample"""

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
        cu = (d60 / d10) if (d10 and d60) else None
        cc = ((d30 * d30) / (d10 * d60)) if (d10 and d30 and d60) else None

        # Start HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Grain Size Analysis Report - {dataset.sample_name}</title>
            {self.report_style}
        </head>
        <body>
            <h1>Grain Size Analysis Report</h1>

            {self._format_metadata_section(metadata)}

            <div class="metadata">
                <p><strong>Sample Name:</strong> {dataset.sample_name}</p>
                <p><strong>Temperature:</strong> {dataset.temperature}°C</p>
                <p><strong>Porosity:</strong> {dataset.porosity}</p>
                <p><strong>Data Points:</strong> {len(dataset.particle_sizes)}</p>
            </div>
        """

        # Executive Summary
        if sections.get('executive_summary', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Executive Summary</h2>
            <div class="info-box">
                <p><strong>Sample:</strong> {dataset.sample_name} has been classified as <strong>{dataset.classify_soil()}</strong>.</p>
                <p><strong>Key Parameters:</strong> D₅₀ = {f'{d50:.3f} mm' if d50 else 'N/A'},
                Cu = {f'{cu:.2f}' if cu else 'N/A'}, Cc = {f'{cc:.2f}' if cc else 'N/A'}</p>
                <p><strong>Gradation:</strong> {self._classify_uniformity(cu)}</p>
            </div>
            </div>
            """

        # Methodology
        if sections.get('methodology', True):
            html += """
            <div style="page-break-before: auto;">
            <h2>Methodology</h2>
            <div class="info-box">
                <h3>Grain Size Analysis</h3>
                <p>Grain size distribution analysis was performed using sieve analysis and/or sedimentation methods.
                The particle size distribution curve represents the cumulative percent passing versus grain size on a
                semi-logarithmic scale.</p>
                <h3>Characteristic Diameters</h3>
                <p>Characteristic grain sizes (D₁₀, D₃₀, D₅₀, D₆₀) represent the grain diameter at which 10%, 30%, 50%,
                and 60% of the soil mass is finer, respectively. These values are fundamental for soil classification
                and hydraulic conductivity estimation.</p>
                <h3>Gradation Coefficients</h3>
                <p><strong>Uniformity Coefficient (Cu):</strong> Cu = D₆₀/D₁₀. Values &lt; 4 indicate uniform gradation,
                4-6 indicate moderate gradation, and &gt; 6 indicate well-graded soil.</p>
                <p><strong>Coefficient of Curvature (Cc):</strong> Cc = (D₃₀)²/(D₁₀ × D₆₀). Values between 1-3 indicate
                well-graded soil with good particle size distribution.</p>
            </div>
            </div>
            """

        # Results
        if sections.get('results', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Results & Analysis</h2>

            <h3>Characteristic Grain Sizes</h3>
            <div class="summary-stats">
                <div class="stat-card">
                    <div class="stat-label">D10</div>
                    <div class="stat-value">{f'{d10:.3f} mm' if d10 else 'N/A'}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">D30</div>
                    <div class="stat-value">{f'{d30:.3f} mm' if d30 else 'N/A'}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">D50 (Median)</div>
                    <div class="stat-value">{f'{d50:.3f} mm' if d50 else 'N/A'}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">D60</div>
                    <div class="stat-value">{f'{d60:.3f} mm' if d60 else 'N/A'}</div>
                </div>
            </div>

            <h3>Soil Classification Parameters</h3>
            <table>
                <tr>
                    <th>Parameter</th>
                    <th>Value</th>
                    <th>Classification</th>
                </tr>
                <tr>
                    <td>Uniformity Coefficient (Cu)</td>
                    <td>{f'{cu:.2f}' if cu else 'N/A'}</td>
                    <td>{self._classify_uniformity(cu)}</td>
                </tr>
                <tr>
                    <td>Coefficient of Curvature (Cc)</td>
                    <td>{f'{cc:.2f}' if cc else 'N/A'}</td>
                    <td>{self._classify_curvature(cc)}</td>
                </tr>
                <tr>
                    <td>Soil Type</td>
                    <td colspan="2">{dataset.classify_soil()}</td>
                </tr>
            </table>
            """

            # Add detailed statistics sections
            if sections.get('percentiles', True):
                html += f"<h3>Detailed Percentiles</h3>{self._create_percentiles_table(dataset)}"

            if sections.get('gradation', True):
                html += f"<h3>Gradation Breakdown</h3>{self._create_gradation_table(dataset)}"

            if sections.get('data_quality', False):
                html += f"<h3>Data Quality Assessment</h3>{self._create_data_quality_table(dataset)}"

            html += "</div>"

        # Visual Charts
        if sections.get('plots', True):
            grain_plot = self._create_grain_size_plot(dataset)
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Grain Size Distribution Curve</h2>
            <div class="plot-container">
                <img src="{grain_plot}" alt="Grain Size Distribution" style="max-width: 100%; height: auto;">
            </div>
            </div>
            """

        # Raw data table
        if sections.get('raw_data', False):
            html += """
            <div style="page-break-before: always;">
            <h2>Appendix A: Raw Data</h2>
            <table>
                <tr>
                    <th>Grain Size (mm)</th>
                    <th>Percent Passing (%)</th>
                    <th>Percent Retained (%)</th>
                </tr>
            """

            for i, (size, passing) in enumerate(zip(dataset.particle_sizes, dataset.percent_passing)):
                retained = 100 - passing
                html += f"""
                <tr>
                    <td>{size:.4f}</td>
                    <td>{passing:.2f}</td>
                    <td>{retained:.2f}</td>
                </tr>
                """

            html += "</table>"

            # Add comprehensive comparison tables
            if sections.get('grain_comparison', True):
                html += f"<h3>Grain Parameters Comparison</h3>{self._create_grain_parameters_comparison_table(datasets)}"

            if sections.get('k_statistics', True) and k_results_dict:
                html += f"<h3>Permeability Classification Summary</h3>{self._create_permeability_classification_table(k_results_dict)}"

            html += "</div>"

        # Interpretation
        if sections.get('interpretation', True):
            html += f"""
            <div style="page-break-before: auto;">
            <h2>Interpretation & Discussion</h2>
            <div class="info-box">
                <h3>Grain Size Distribution Analysis</h3>
                <p>{self._interpret_grain_distribution(dataset, cu, cc)}</p>
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

    def generate_k_value_report(self, dataset: GrainSizeData,
                               k_results: List[KCalculationResult],
                               temperature: float,
                               porosity: float,
                               metadata: Optional[Dict[str, str]] = None,
                               sections: Optional[Dict[str, bool]] = None) -> str:
        """Generate a K-value calculation report for a single sample"""

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

        # Start HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Hydraulic Conductivity Report - {dataset.sample_name}</title>
            {self.report_style}
        </head>
        <body>
            <h1>Hydraulic Conductivity Analysis Report</h1>

            {self._format_metadata_section(metadata)}

            <div class="metadata">
                <p><strong>Sample Name:</strong> {dataset.sample_name}</p>
                <p><strong>Temperature:</strong> {temperature}°C</p>
                <p><strong>Porosity:</strong> {porosity}</p>
                <p><strong>Valid Calculations:</strong> {len(valid_results)} / {len(k_results)}</p>
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
            <tr>
                <th>Percentile</th>
                <th>Size (mm)</th>
                <th>Visual Distribution</th>
            </tr>
        """

        for p in percentiles_list:
            val = percentiles_dict[p]
            bar_width = int((val / max_val) * 100) if max_val > 0 else 0

            # Highlight key percentiles
            row_style = ""
            if p in [10, 30, 50, 60]:
                row_style = ' style="background-color: #fffacd;"'

            html += f"""
            <tr{row_style}>
                <td style="text-align: center;"><strong>D{p}</strong></td>
                <td style="text-align: right;">{val:.3f}</td>
                <td>
                    <div style="background-color: #6b8e23; width: {bar_width}%; height: 15px; border-radius: 3px;"></div>
                </td>
            </tr>
            """

        html += "</table>"
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
            <tr>
                <th>Fraction</th>
                <th>Size Range</th>
                <th>Percentage</th>
                <th>Visual</th>
            </tr>
        """

        gradations = [
            ("Gravel", "> 2 mm", gravel_percent, "#8b7355"),
            ("Sand", "0.063 - 2 mm", sand_percent, "#daa520"),
            ("Fines", "< 0.063 mm", fines_percent, "#cd853f")
        ]

        for name, size_range, percent, color in gradations:
            bar_width = int(percent)
            html += f"""
            <tr>
                <td style="font-weight: bold;">{name}</td>
                <td>{size_range}</td>
                <td style="text-align: right;">{percent:.1f}%</td>
                <td>
                    <div style="background-color: {color}; width: {bar_width}%; height: 20px; border-radius: 3px; display: inline-block;"></div>
                </td>
            </tr>
            """

        html += "</table>"
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
            # Determine status color
            status_str = str(result.status) if hasattr(result.status, 'value') else str(result.status)

            if "OK" in status_str or "WITHIN_RANGE" in status_str:
                status_color = "#e8f5e9"  # Light green
                status_text = "✓ OK"
            elif "WARNING" in status_str or "OUTSIDE_RANGE" in status_str:
                status_color = "#fff9e6"  # Light yellow
                status_text = "⚠ Warning"
            else:
                status_color = "#ffebee"  # Light red
                status_text = "✗ Error"

            k_display = f"{result.k_value:.2e}" if result.k_value else "N/A"

            # Get status message or default text
            notes = result.status_message if hasattr(result, 'status_message') and result.status_message else status_str

            html += f"""
            <tr>
                <td style="font-weight: bold;">{result.method_name}</td>
                <td style="text-align: right; font-family: monospace;">{k_display}</td>
                <td style="background-color: {status_color}; text-align: center;">{status_text}</td>
                <td style="font-size: 9pt;">{notes}</td>
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

            # Add cells with color-coding
            for val in values:
                if val is None:
                    html += "<td style='text-align: center; color: #999;'>N/A</td>"
                else:
                    # Normalize value for color coding
                    if val_range > 0:
                        normalized = (val - min_val) / val_range
                    else:
                        normalized = 0.5

                    # Color interpolation: green (low) -> yellow (mid) -> red (high)
                    if normalized < 0.5:
                        r = int(255 * (normalized * 2))
                        g = 200
                        b = 100
                    else:
                        r = 255
                        g = int(200 * (1 - (normalized - 0.5) * 2))
                        b = 100

                    color = f"rgba({r}, {g}, {b}, 0.31)"  # 0.31 ≈ 80/255 for transparency

                    display_val = f"{val:.3f}" if param.endswith("(mm)") else f"{val:.2f}"
                    html += f"<td style='text-align: center; background-color: {color};'>{display_val}</td>"

            # Add statistics column
            if valid_values:
                mean = np.mean(valid_values)
                std = np.std(valid_values)
                cv = (std / mean * 100) if mean > 0 else 0

                stats_text = f"μ={mean:.2f}<br>σ={std:.2f}<br>CV={cv:.1f}%"
                html += f"<td style='background-color: #f0f0f0; text-align: center; font-size: 9pt;'>{stats_text}</td>"
            else:
                html += "<td style='text-align: center; color: #999;'>N/A</td>"

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

                # Classify and color-code
                if mean_k > 1e-2:
                    classification = "Very High (Gravel)"
                    color = "rgba(76, 175, 80, 0.39)"  # Green, 0.39 ≈ 100/255
                elif mean_k > 1e-4:
                    classification = "High (Clean Sand)"
                    color = "rgba(139, 195, 74, 0.39)"  # Light green
                elif mean_k > 1e-5:
                    classification = "Moderate (Fine Sand)"
                    color = "rgba(255, 235, 59, 0.39)"  # Yellow
                elif mean_k > 1e-7:
                    classification = "Low (Silt)"
                    color = "rgba(255, 152, 0, 0.39)"  # Orange
                else:
                    classification = "Very Low (Clay)"
                    color = "rgba(244, 67, 54, 0.39)"  # Red

                html += f"""
                <tr style="background-color: {color};">
                    <td style="font-weight: bold;">{sample_name}</td>
                    <td style="text-align: right; font-family: monospace;">{mean_k:.2e}</td>
                    <td>{classification}</td>
                </tr>
                """
            else:
                html += f"""
                <tr style="background-color: #e0e0e0;">
                    <td style="font-weight: bold;">{sample_name}</td>
                    <td style="text-align: center; color: #999;">Not calculated</td>
                    <td style="text-align: center; color: #999;">N/A</td>
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

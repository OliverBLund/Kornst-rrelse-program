"""
Report generator for creating professional analysis reports
"""

from typing import List, Dict, Optional, Any
import numpy as np
from datetime import datetime
import base64
import io
from data_loader import GrainSizeData
from k_calculations import KCalculationResult


class ReportGenerator:
    """
    Generates professional reports for grain size analysis and K-value calculations
    """
    
    def __init__(self):
        self.report_style = """
        <style>
            body {
                font-family: 'Segoe UI', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            h1 {
                color: #2c5530;
                border-bottom: 3px solid #6b8e23;
                padding-bottom: 10px;
                margin-top: 30px;
            }
            h2 {
                color: #5d4e37;
                border-bottom: 1px solid #d4c4a8;
                padding-bottom: 5px;
                margin-top: 25px;
            }
            h3 {
                color: #6b5b47;
                margin-top: 20px;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            th {
                background-color: #8b7355;
                color: white;
                padding: 10px;
                text-align: left;
                font-weight: bold;
            }
            td {
                padding: 8px;
                border-bottom: 1px solid #ddd;
            }
            tr:nth-child(even) {
                background-color: #fafaf7;
            }
            tr:hover {
                background-color: #f0ebe5;
            }
            .info-box {
                background-color: #f5f5f0;
                border-left: 4px solid #6b8e23;
                padding: 15px;
                margin: 15px 0;
                border-radius: 4px;
            }
            .warning-box {
                background-color: #fff9e6;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 15px 0;
                border-radius: 4px;
            }
            .success-box {
                background-color: #e8f5e9;
                border-left: 4px solid #4caf50;
                padding: 15px;
                margin: 15px 0;
                border-radius: 4px;
            }
            .metadata {
                background-color: #fafaf7;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
            }
            .metadata p {
                margin: 5px 0;
            }
            .metadata strong {
                color: #5d4e37;
                min-width: 150px;
                display: inline-block;
            }
            .plot-container {
                text-align: center;
                margin: 20px 0;
                padding: 10px;
                background-color: #fff;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            .plot-container img {
                max-width: 100%;
                height: auto;
            }
            .summary-stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }
            .stat-card {
                background: linear-gradient(135deg, #f5f5f0 0%, #fafaf7 100%);
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #d4c4a8;
            }
            .stat-label {
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .stat-value {
                font-size: 24px;
                font-weight: bold;
                color: #2c5530;
                margin-top: 5px;
            }
            .footer {
                margin-top: 50px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                text-align: center;
                color: #666;
                font-size: 12px;
            }
        </style>
        """
    
    def generate_grain_size_report(self, dataset: GrainSizeData, 
                                  include_plot: bool = True,
                                  include_raw_data: bool = True) -> str:
        """Generate a grain size analysis report for a single sample"""
        
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
            
            <div class="metadata">
                <p><strong>Sample Name:</strong> {dataset.sample_name}</p>
                <p><strong>Report Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                <p><strong>Temperature:</strong> {dataset.temperature}°C</p>
                <p><strong>Porosity:</strong> {dataset.porosity}</p>
                <p><strong>Data Points:</strong> {len(dataset.particle_sizes)}</p>
            </div>
            
            <h2>Characteristic Grain Sizes</h2>
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
            
            <h2>Soil Classification Parameters</h2>
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
        
        # Add raw data table if requested
        if include_raw_data:
            html += """
            <h2>Grain Size Distribution Data</h2>
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
        
        # Add interpretation
        html += f"""
            <h2>Interpretation</h2>
            <div class="info-box">
                <h3>Grain Size Distribution Analysis</h3>
                <p>{self._interpret_grain_distribution(dataset, cu, cc)}</p>
            </div>
        """
        
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
                               porosity: float) -> str:
        """Generate a K-value calculation report for a single sample"""
        
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
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Hydraulic Conductivity Report - {dataset.sample_name}</title>
            {self.report_style}
        </head>
        <body>
            <h1>Hydraulic Conductivity Analysis Report</h1>
            
            <div class="metadata">
                <p><strong>Sample Name:</strong> {dataset.sample_name}</p>
                <p><strong>Report Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                <p><strong>Temperature:</strong> {temperature}°C</p>
                <p><strong>Porosity:</strong> {porosity}</p>
                <p><strong>Valid Calculations:</strong> {len(valid_results)} / {len(k_results)}</p>
            </div>
            
            <h2>Statistical Summary</h2>
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
            
            <h2>K-Value Calculations by Method</h2>
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
        
        html += "</table>"
        
        # Add permeability classification
        html += f"""
            <h2>Permeability Classification</h2>
            <div class="info-box">
                <p><strong>Classification:</strong> {self._classify_permeability(mean_k)}</p>
                <p><strong>Typical Application:</strong> {self._get_permeability_application(mean_k)}</p>
            </div>
        """
        
        # Add method comparison
        html += f"""
            <h2>Method Comparison Analysis</h2>
            <div class="info-box">
                <p><strong>Variability:</strong> {max_k/min_k:.1f}x difference between min and max</p>
                <p><strong>Standard Deviation:</strong> {std_k:.2e} m/s</p>
                <p><strong>Coefficient of Variation:</strong> {(std_k/mean_k)*100:.1f}%</p>
                <p>{self._interpret_k_variability(max_k/min_k)}</p>
            </div>
        """
        
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
                                porosity: float) -> str:
        """Generate a combined report with both grain size and K-value analysis"""
        
        # Combine both reports
        grain_report = self.generate_grain_size_report(dataset, include_plot=True, include_raw_data=False)
        k_report = self.generate_k_value_report(dataset, k_results, temperature, porosity)
        
        # Extract body content from both reports
        grain_body = grain_report.split('<body>')[1].split('</body>')[0]
        k_body = k_report.split('<h1>Hydraulic Conductivity Analysis Report</h1>')[1].split('</body>')[0]
        
        # Create combined report
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
                                  porosity: float) -> str:
        """Generate a comparison report for multiple samples"""
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Multi-Sample Comparison Report</title>
            {self.report_style}
        </head>
        <body>
            <h1>Multi-Sample Comparison Report</h1>
            
            <div class="metadata">
                <p><strong>Number of Samples:</strong> {len(datasets)}</p>
                <p><strong>Report Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                <p><strong>Temperature:</strong> {temperature}°C</p>
                <p><strong>Porosity:</strong> {porosity}</p>
            </div>
            
            <h2>Sample Summary</h2>
            <table>
                <tr>
                    <th>Sample</th>
                    <th>D10 (mm)</th>
                    <th>D50 (mm)</th>
                    <th>D60 (mm)</th>
                    <th>Cu</th>
                    <th>Soil Type</th>
                    <th>Mean K (m/s)</th>
                </tr>
        """
        
        for dataset in datasets:
            d10 = dataset.get_d10()
            d50 = dataset.get_d50()
            d60 = dataset.get_d60()
            cu = (d60/d10) if (d10 and d60) else None
            
            # Get mean K if available
            mean_k = "N/A"
            if dataset.sample_name in k_results_dict:
                k_values = [r.k_value for r in k_results_dict[dataset.sample_name] 
                           if r.k_value is not None and r.k_value > 0]
                if k_values:
                    mean_k = f"{np.mean(k_values):.2e}"
            
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
        
        html += "</table>"
        
        # Add comparison analysis
        html += """
            <h2>Comparative Analysis</h2>
            <div class="info-box">
        """
        
        # Find samples with highest/lowest K
        if k_results_dict:
            mean_k_by_sample = {}
            for name, results in k_results_dict.items():
                k_values = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]
                if k_values:
                    mean_k_by_sample[name] = np.mean(k_values)
            
            if mean_k_by_sample:
                highest = max(mean_k_by_sample.items(), key=lambda x: x[1])
                lowest = min(mean_k_by_sample.items(), key=lambda x: x[1])
                
                html += f"""
                    <p><strong>Highest Permeability:</strong> {highest[0]} ({highest[1]:.2e} m/s)</p>
                    <p><strong>Lowest Permeability:</strong> {lowest[0]} ({lowest[1]:.2e} m/s)</p>
                    <p><strong>Permeability Range:</strong> {highest[1]/lowest[1]:.1f}x difference</p>
                """
        
        html += """
            </div>
            
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
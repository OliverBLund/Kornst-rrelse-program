"""
Export Manager - Handles all export operations for grain size analysis data
"""

import os
import csv
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from PyQt6.QtWidgets import QProgressDialog

from data_loader import GrainSizeData
from k_calculations_v2 import KCalculationResult


class ExportManager:
    """Manages export operations for various file formats"""

    def __init__(self):
        self.exported_files = []

    def export(self, datasets: List[tuple], config: Dict, progress: Optional[QProgressDialog] = None) -> List[str]:
        """
        Export datasets according to configuration

        Args:
            datasets: List of (name, GrainSizeData, List[KCalculationResult]) tuples
            config: Export configuration dictionary
            progress: Optional progress dialog

        Returns:
            List of exported file paths
        """
        self.exported_files = []
        total_steps = self._calculate_total_steps(datasets, config)
        current_step = 0

        if progress:
            progress.setMaximum(total_steps)

        # CSV Export
        if config.get('csv', False):
            if config.get('csv_mode') == 'separate':
                for name, dataset, results in datasets:
                    self._export_csv_single(name, dataset, results, config)
                    current_step += 1
                    if progress:
                        progress.setValue(current_step)
            else:
                self._export_csv_combined(datasets, config)
                current_step += 1
                if progress:
                    progress.setValue(current_step)

        # Excel Export
        if config.get('excel', False):
            excel_mode = config.get('excel_mode', 'per_dataset')

            if excel_mode == 'per_dataset':
                for name, dataset, results in datasets:
                    self._export_excel_single(name, dataset, results, config)
                    current_step += 1
                    if progress:
                        progress.setValue(current_step)

            elif excel_mode == 'combined':
                self._export_excel_combined(datasets, config)
                current_step += 1
                if progress:
                    progress.setValue(current_step)

            elif excel_mode == 'method_organized':
                self._export_excel_method_organized(datasets, config)
                current_step += 1
                if progress:
                    progress.setValue(current_step)

        # JSON Export
        if config.get('json', False):
            for name, dataset, results in datasets:
                self._export_json(name, dataset, results, config)
                current_step += 1
                if progress:
                    progress.setValue(current_step)

        # Plot Export
        if config.get('plots', False) and config.get('plot_figures'):
            # Plot figures will be passed in config if available
            plot_figures = config.get('plot_figures', [])
            for idx, (name, dataset, results) in enumerate(datasets):
                if idx < len(plot_figures) and plot_figures[idx] is not None:
                    self._export_plots(name, plot_figures[idx], config)
                    current_step += 1
                    if progress:
                        progress.setValue(current_step)

        return self.exported_files

    def _export_plots(self, name: str, figure, config: Dict):
        """Export matplotlib figure to various formats"""
        output_dir = config['output_dir']
        template = config['filename_template']

        base_filename = self._format_filename(template, name, '')

        # PNG export
        if config.get('png', False):
            filename = f"{base_filename}_plot.png"
            filepath = os.path.join(output_dir, filename)
            dpi = config.get('png_dpi', 300)
            figure.savefig(filepath, dpi=dpi, bbox_inches='tight')
            self.exported_files.append(filepath)

        # SVG export
        if config.get('svg', False):
            filename = f"{base_filename}_plot.svg"
            filepath = os.path.join(output_dir, filename)
            figure.savefig(filepath, format='svg', bbox_inches='tight')
            self.exported_files.append(filepath)

        # PDF export
        if config.get('pdf_plot', False):
            filename = f"{base_filename}_plot.pdf"
            filepath = os.path.join(output_dir, filename)
            figure.savefig(filepath, format='pdf', bbox_inches='tight')
            self.exported_files.append(filepath)

    def _calculate_total_steps(self, datasets: List[tuple], config: Dict) -> int:
        """Calculate total steps for progress bar"""
        steps = 0

        if config.get('csv', False):
            if config.get('csv_mode') == 'separate':
                steps += len(datasets)
            else:
                steps += 1

        if config.get('excel', False):
            excel_mode = config.get('excel_mode', 'per_dataset')
            if excel_mode == 'per_dataset':
                steps += len(datasets)
            else:
                steps += 1

        if config.get('json', False):
            steps += len(datasets)

        return max(steps, 1)

    def _format_filename(self, template: str, name: str, extension: str = "") -> str:
        """Format filename from template"""
        now = datetime.now()

        replacements = {
            '{sample_name}': name,
            '{date}': now.strftime('%Y%m%d'),
            '{time}': now.strftime('%H%M%S'),
            '{project}': 'grain_analysis',
            '{method}': 'all'
        }

        filename = template
        for key, value in replacements.items():
            filename = filename.replace(key, value)

        # Remove any invalid filename characters
        invalid_chars = '<>:"|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        if extension and not filename.endswith(extension):
            filename += extension

        return filename

    # ==================== CSV EXPORT ====================

    def _export_csv_single(self, name: str, dataset: GrainSizeData,
                          results: List[KCalculationResult], config: Dict):
        """Export single dataset to CSV"""
        output_dir = config['output_dir']
        template = config['filename_template']

        # Generate base filename
        base_filename = self._format_filename(template, name, '')

        # Export grain size data if requested
        if config.get('grain_distribution', True):
            filename = f"{base_filename}_grain_size.csv"
            filepath = os.path.join(output_dir, filename)
            self._write_grain_size_csv(filepath, dataset)
            self.exported_files.append(filepath)

        # Export K-values if requested
        if config.get('k_values', True) and results:
            filename = f"{base_filename}_k_values.csv"
            filepath = os.path.join(output_dir, filename)
            self._write_k_values_csv(filepath, name, dataset, results, config)
            self.exported_files.append(filepath)

        # Export statistics if requested
        if config.get('statistics', True):
            filename = f"{base_filename}_statistics.csv"
            filepath = os.path.join(output_dir, filename)
            self._write_statistics_csv(filepath, dataset, results, config)
            self.exported_files.append(filepath)

    def _export_csv_combined(self, datasets: List[tuple], config: Dict):
        """Export all datasets to a single combined CSV"""
        output_dir = config['output_dir']
        template = config['filename_template']

        filename = self._format_filename(template, 'combined_all_datasets', '.csv')
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow([
                'Sample Name', 'Method', 'K (m/s)', 'K (cm/s)', 'K (m/d)',
                'Status', 'Formula', 'Temperature (°C)', 'Porosity',
                'D10 (mm)', 'D50 (mm)', 'D60 (mm)', 'Cu', 'Cc'
            ])

            # Write data for each dataset
            # DEBUG
            print(f"[DEBUG] _export_csv_combined: Processing {len(datasets)} datasets")
            for name, dataset, results in datasets:
                print(f"[DEBUG] Dataset: {name}, Results count: {len(results) if results else 0}")
                if results:
                    print(f"[DEBUG] First result: {results[0].method_name if results else 'None'}")
                    for result in results:
                        if result.k_value is not None:
                            k_cm_s = result.k_value * 100
                            k_m_d = result.k_value * 86400

                            writer.writerow([
                                name,
                                result.method_name,
                                f"{result.k_value:.3e}",
                                f"{k_cm_s:.3e}",
                                f"{k_m_d:.2f}",
                                result.status.value if hasattr(result.status, 'value') else str(result.status),
                                result.formula_used,
                                result.temperature,
                                result.porosity,
                                dataset.get_d10() if hasattr(dataset, 'get_d10') else '',
                                dataset.get_d50() if hasattr(dataset, 'get_d50') else '',
                                dataset.get_d60() if hasattr(dataset, 'get_d60') else '',
                                dataset.get_uniformity_coefficient() if hasattr(dataset, 'get_uniformity_coefficient') else '',
                                dataset.get_coefficient_of_curvature() if hasattr(dataset, 'get_coefficient_of_curvature') else ''
                            ])

        self.exported_files.append(filepath)

        # Also export wide format
        self._export_csv_wide_format(datasets, config)

    def _export_csv_wide_format(self, datasets: List[tuple], config: Dict):
        """
        Export wide-format CSV with one row per dataset and columns for all parameters.
        Perfect for statistical analysis and comparison.
        """
        output_dir = config['output_dir']
        template = config['filename_template']

        filename = self._format_filename(template, 'wide_format_all_datasets', '.csv')
        filepath = os.path.join(output_dir, filename)

        # Get all unique method names from results (dynamically) - DO THIS FIRST!
        # DEBUG
        print(f"[DEBUG] _export_csv_wide_format: Processing {len(datasets)} datasets")
        all_method_names = set()
        for idx, (name, dataset, results) in enumerate(datasets):
            print(f"[DEBUG] Dataset {idx}: name={name}, has_results={results is not None}, results_count={len(results) if results else 0}")
            if results:
                print(f"[DEBUG]   First few results: {[r.method_name for r in results[:3]]}")
                for result in results:
                    all_method_names.add(result.method_name)

        print(f"[DEBUG] Found {len(all_method_names)} unique methods: {sorted(all_method_names)}")

        # Sort method names for consistent ordering
        method_names = sorted(all_method_names)

        # If no results yet, use standard methods as fallback
        if not method_names:
            method_names = [
                'Hazen', 'Hazen_1892', 'Slichter', 'Terzaghi',
                'Beyer', 'Sauerbrei', 'Kruger', 'Kozeny-Carman',
                'Zunker', 'Zamarin', 'USBR', 'Barr',
                'Alyamani-Sen', 'Chapuis', 'Shepherd', 'Krumbein-Monk'
            ]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Build header DYNAMICALLY based on actual method names
            header = [
                # Sample info
                'Sample_Name',
                'Temperature_C',
                'Porosity',

                # Grain size percentiles
                'D5_mm', 'D10_mm', 'D16_mm', 'D17_mm', 'D20_mm', 'D30_mm',
                'D50_mm', 'D60_mm', 'D84_mm', 'D95_mm',

                # Gradation parameters
                'Cu_Uniformity_Coefficient',
                'Cc_Curvature_Coefficient',
            ]

            # Add K-values for each method in m/s
            for method in method_names:
                # Replace special chars for column names
                safe_name = method.replace('-', '_').replace(' ', '_')
                header.append(f'K_{safe_name}_m/s')

            # Add K-values in cm/s
            for method in method_names:
                safe_name = method.replace('-', '_').replace(' ', '_')
                header.append(f'K_{safe_name}_cm/s')

            # Add K-values in m/d
            for method in method_names:
                safe_name = method.replace('-', '_').replace(' ', '_')
                header.append(f'K_{safe_name}_m/d')

            # Add status flags for each method
            for method in method_names:
                safe_name = method.replace('-', '_').replace(' ', '_')
                header.append(f'Status_{safe_name}')

            # Add statistical summaries
            header.extend([
                'K_Mean_m/s', 'K_Median_m/s', 'K_StdDev_m/s', 'K_Min_m/s', 'K_Max_m/s',
                'K_Mean_cm/s', 'K_Median_cm/s', 'K_Min_cm/s', 'K_Max_cm/s',
                'K_Mean_m/d', 'K_Median_m/d', 'K_Min_m/d', 'K_Max_m/d',
                'Valid_Methods_Count'
            ])

            writer.writerow(header)

            # Write data for each dataset
            for name, dataset, results in datasets:
                row = []

                # Sample info
                row.append(name)
                row.append(dataset.temperature)
                row.append(dataset.current_porosity or dataset.porosity)

                # Grain size percentiles
                percentiles = [5, 10, 16, 17, 20, 30, 50, 60, 84, 95]
                for p in percentiles:
                    if hasattr(dataset, '_interpolate_grain_size'):
                        value = dataset._interpolate_grain_size(p)
                        row.append(f"{value:.4f}" if value is not None else '')
                    elif hasattr(dataset, f'get_d{p}'):
                        value = getattr(dataset, f'get_d{p}')()
                        row.append(f"{value:.4f}" if value is not None else '')
                    else:
                        row.append('')

                # Gradation parameters
                cu = dataset.get_uniformity_coefficient() if hasattr(dataset, 'get_uniformity_coefficient') else None
                cc = dataset.get_coefficient_of_curvature() if hasattr(dataset, 'get_coefficient_of_curvature') else None
                row.append(f"{cu:.2f}" if cu is not None else '')
                row.append(f"{cc:.2f}" if cc is not None else '')

                # Build method -> result mapping
                method_results = {}
                if results:
                    for result in results:
                        method_results[result.method_name] = result

                # K-values in m/s
                for method in method_names:
                    if method in method_results:
                        k_val = method_results[method].k_value
                        row.append(f"{k_val:.3e}" if k_val is not None else '')
                    else:
                        row.append('')

                # K-values in cm/s
                for method in method_names:
                    if method in method_results:
                        k_val = method_results[method].k_value
                        row.append(f"{k_val * 100:.3e}" if k_val is not None else '')
                    else:
                        row.append('')

                # K-values in m/d
                for method in method_names:
                    if method in method_results:
                        k_val = method_results[method].k_value
                        row.append(f"{k_val * 86400:.2f}" if k_val is not None else '')
                    else:
                        row.append('')

                # Status flags
                for method in method_names:
                    if method in method_results:
                        status = method_results[method].status
                        row.append(status.value if hasattr(status, 'value') else str(status))
                    else:
                        row.append('')

                # Statistical summaries
                valid_k_values = [r.k_value for r in results if r.k_value is not None and r.k_value > 0] if results else []

                if valid_k_values:
                    import statistics

                    mean_k = statistics.mean(valid_k_values)
                    median_k = statistics.median(valid_k_values)
                    stdev_k = statistics.stdev(valid_k_values) if len(valid_k_values) > 1 else 0
                    min_k = min(valid_k_values)
                    max_k = max(valid_k_values)

                    # m/s
                    row.append(f"{mean_k:.3e}")
                    row.append(f"{median_k:.3e}")
                    row.append(f"{stdev_k:.3e}")
                    row.append(f"{min_k:.3e}")
                    row.append(f"{max_k:.3e}")

                    # cm/s
                    row.append(f"{mean_k * 100:.3e}")
                    row.append(f"{median_k * 100:.3e}")
                    row.append(f"{min_k * 100:.3e}")
                    row.append(f"{max_k * 100:.3e}")

                    # m/d
                    row.append(f"{mean_k * 86400:.2f}")
                    row.append(f"{median_k * 86400:.2f}")
                    row.append(f"{min_k * 86400:.2f}")
                    row.append(f"{max_k * 86400:.2f}")

                    row.append(len(valid_k_values))
                else:
                    # Empty statistics
                    row.extend([''] * 13)

                writer.writerow(row)

        self.exported_files.append(filepath)

    def _write_grain_size_csv(self, filepath: str, dataset: GrainSizeData):
        """Write grain size distribution to CSV"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(['Particle Size (mm)', 'Percent Passing (%)'])

            # Data
            for size, percent in zip(dataset.particle_sizes, dataset.percent_passing):
                writer.writerow([f"{size:.4f}", f"{percent:.2f}"])

    def _write_k_values_csv(self, filepath: str, name: str, dataset: GrainSizeData,
                           results: List[KCalculationResult], config: Dict):
        """Write K-values to CSV"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            header = ['Method', 'K (m/s)', 'K (cm/s)', 'K (m/d)', 'Status', 'Status Message']

            if config.get('formulas', False):
                header.append('Formula')

            header.extend(['Temperature (°C)', 'Porosity', 'Grain Size Used'])

            writer.writerow(header)

            # Data
            for result in results:
                if result.k_value is not None:
                    k_cm_s = result.k_value * 100
                    k_m_d = result.k_value * 86400

                    row = [
                        result.method_name,
                        f"{result.k_value:.3e}",
                        f"{k_cm_s:.3e}",
                        f"{k_m_d:.2f}",
                        result.status.value if hasattr(result.status, 'value') else str(result.status),
                        result.status_message
                    ]

                    if config.get('formulas', False):
                        row.append(result.formula_used)

                    row.extend([
                        result.temperature,
                        result.porosity,
                        result.grain_size_used
                    ])

                    writer.writerow(row)

    def _write_statistics_csv(self, filepath: str, dataset: GrainSizeData,
                             results: List[KCalculationResult], config: Dict):
        """Write statistics to CSV"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Sample Information
            writer.writerow(['Sample Information'])
            writer.writerow(['Parameter', 'Value'])
            writer.writerow(['Sample Name', dataset.sample_name])
            writer.writerow(['Temperature (°C)', dataset.temperature])
            writer.writerow(['Porosity', dataset.current_porosity or dataset.porosity])
            writer.writerow([])

            # Grain Size Percentiles
            if config.get('percentiles', True):
                writer.writerow(['Grain Size Percentiles'])
                writer.writerow(['Percentile', 'Size (mm)'])

                percentiles = {
                    'D10': dataset.get_d10() if hasattr(dataset, 'get_d10') else None,
                    'D20': dataset.get_d20() if hasattr(dataset, 'get_d20') else None,
                    'D30': dataset.get_d30() if hasattr(dataset, 'get_d30') else None,
                    'D50': dataset.get_d50() if hasattr(dataset, 'get_d50') else None,
                    'D60': dataset.get_d60() if hasattr(dataset, 'get_d60') else None,
                }

                for name, value in percentiles.items():
                    if value is not None:
                        writer.writerow([name, f"{value:.4f}"])

                writer.writerow([])

            # Gradation Parameters
            if config.get('gradation', True):
                writer.writerow(['Gradation Parameters'])
                writer.writerow(['Parameter', 'Value'])

                cu = dataset.get_uniformity_coefficient() if hasattr(dataset, 'get_uniformity_coefficient') else None
                cc = dataset.get_coefficient_of_curvature() if hasattr(dataset, 'get_coefficient_of_curvature') else None

                if cu is not None:
                    writer.writerow(['Uniformity Coefficient (Cu)', f"{cu:.2f}"])
                if cc is not None:
                    writer.writerow(['Coefficient of Curvature (Cc)', f"{cc:.2f}"])

                writer.writerow([])

            # K-Value Statistics
            if config.get('statistics', True) and results:
                valid_k_values = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]

                if valid_k_values:
                    import statistics

                    writer.writerow(['K-Value Statistics'])
                    writer.writerow(['Statistic', 'Value (m/s)', 'Value (cm/s)', 'Value (m/d)'])

                    mean_k = statistics.mean(valid_k_values)
                    median_k = statistics.median(valid_k_values)
                    min_k = min(valid_k_values)
                    max_k = max(valid_k_values)

                    if len(valid_k_values) > 1:
                        stdev_k = statistics.stdev(valid_k_values)
                    else:
                        stdev_k = 0

                    writer.writerow(['Mean', f"{mean_k:.3e}", f"{mean_k*100:.3e}", f"{mean_k*86400:.2f}"])
                    writer.writerow(['Median', f"{median_k:.3e}", f"{median_k*100:.3e}", f"{median_k*86400:.2f}"])
                    writer.writerow(['Std Dev', f"{stdev_k:.3e}", f"{stdev_k*100:.3e}", f"{stdev_k*86400:.2f}"])
                    writer.writerow(['Min', f"{min_k:.3e}", f"{min_k*100:.3e}", f"{min_k*86400:.2f}"])
                    writer.writerow(['Max', f"{max_k:.3e}", f"{max_k*100:.3e}", f"{max_k*86400:.2f}"])

    # ==================== EXCEL EXPORT ====================

    def _export_excel_single(self, name: str, dataset: GrainSizeData,
                            results: List[KCalculationResult], config: Dict):
        """Export single dataset to Excel workbook with multiple sheets"""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise ImportError("openpyxl is required for Excel export. Install with: pip install openpyxl")

        output_dir = config['output_dir']
        template = config['filename_template']

        filename = self._format_filename(template, name, '.xlsx')
        filepath = os.path.join(output_dir, filename)

        wb = Workbook()

        # Remove default sheet
        if 'Sheet' in wb.sheetnames:
            wb.remove(wb['Sheet'])

        # Sheet 1: Summary
        ws_summary = wb.create_sheet('Summary')
        self._write_excel_summary(ws_summary, name, dataset, results, config)

        # Sheet 2: Grain Size Data
        if config.get('grain_distribution', True):
            ws_grain = wb.create_sheet('Grain_Size_Data')
            self._write_excel_grain_size(ws_grain, dataset)

        # Sheet 3: Percentiles
        if config.get('percentiles', True):
            ws_percentiles = wb.create_sheet('Percentiles')
            self._write_excel_percentiles(ws_percentiles, dataset)

        # Sheet 4: K-Values
        if config.get('k_values', True) and results:
            ws_k = wb.create_sheet('K_Values')
            self._write_excel_k_values(ws_k, results, config)

        # Sheet 5: Statistics
        if config.get('statistics', True) and results:
            ws_stats = wb.create_sheet('Statistics')
            self._write_excel_statistics(ws_stats, results)

        wb.save(filepath)
        self.exported_files.append(filepath)

    def _export_excel_combined(self, datasets: List[tuple], config: Dict):
        """Export all datasets to single Excel workbook"""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill
        except ImportError:
            raise ImportError("openpyxl is required for Excel export. Install with: pip install openpyxl")

        output_dir = config['output_dir']
        template = config['filename_template']

        filename = self._format_filename(template, 'combined_all_datasets', '.xlsx')
        filepath = os.path.join(output_dir, filename)

        wb = Workbook()

        # Remove default sheet
        if 'Sheet' in wb.sheetnames:
            wb.remove(wb['Sheet'])

        # Create a summary sheet comparing all datasets
        ws_summary = wb.create_sheet('All_Datasets_Summary')
        self._write_excel_combined_summary(ws_summary, datasets, config)

        # Create individual sheets for each dataset
        for name, dataset, results in datasets:
            # Sanitize sheet name (max 31 chars, no special chars)
            sheet_name = name[:31]
            for char in ['\\', '/', '*', '[', ']', ':', '?']:
                sheet_name = sheet_name.replace(char, '_')

            ws = wb.create_sheet(sheet_name)
            self._write_excel_dataset_combined(ws, name, dataset, results, config)

        wb.save(filepath)
        self.exported_files.append(filepath)

    def _export_excel_method_organized(self, datasets: List[tuple], config: Dict):
        """Export Excel workbook organized by K-calculation methods"""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill
        except ImportError:
            raise ImportError("openpyxl is required for Excel export. Install with: pip install openpyxl")

        output_dir = config['output_dir']
        template = config['filename_template']

        filename = self._format_filename(template, 'method_comparison', '.xlsx')
        filepath = os.path.join(output_dir, filename)

        wb = Workbook()

        # Remove default sheet
        if 'Sheet' in wb.sheetnames:
            wb.remove(wb['Sheet'])

        # Get all unique methods
        all_methods = set()
        for _, _, results in datasets:
            if results:
                for result in results:
                    all_methods.add(result.method_name)

        # Create a sheet for each method
        for method in sorted(all_methods):
            # Sanitize sheet name
            sheet_name = method[:31]
            ws = wb.create_sheet(sheet_name)
            self._write_excel_method_comparison(ws, method, datasets)

        wb.save(filepath)
        self.exported_files.append(filepath)

    def _write_excel_summary(self, ws, name: str, dataset: GrainSizeData,
                            results: List[KCalculationResult], config: Dict):
        """Write summary sheet to Excel"""
        from openpyxl.styles import Font, Alignment, PatternFill

        # Title
        ws['A1'] = 'Grain Size Analysis Summary'
        ws['A1'].font = Font(size=14, bold=True)

        row = 3

        # Sample Information
        ws[f'A{row}'] = 'Sample Name:'
        ws[f'B{row}'] = name
        ws[f'A{row}'].font = Font(bold=True)
        row += 1

        ws[f'A{row}'] = 'Temperature:'
        ws[f'B{row}'] = f"{dataset.temperature}°C"
        ws[f'A{row}'].font = Font(bold=True)
        row += 1

        ws[f'A{row}'] = 'Porosity:'
        ws[f'B{row}'] = dataset.current_porosity or dataset.porosity
        ws[f'A{row}'].font = Font(bold=True)
        row += 2

        # Key grain sizes
        ws[f'A{row}'] = 'Key Grain Sizes'
        ws[f'A{row}'].font = Font(bold=True, size=12)
        row += 1

        percentiles = {
            'D10': dataset.get_d10() if hasattr(dataset, 'get_d10') else None,
            'D50': dataset.get_d50() if hasattr(dataset, 'get_d50') else None,
            'D60': dataset.get_d60() if hasattr(dataset, 'get_d60') else None,
        }

        for pname, value in percentiles.items():
            if value is not None:
                ws[f'A{row}'] = f"{pname}:"
                ws[f'B{row}'] = f"{value:.4f} mm"
                ws[f'A{row}'].font = Font(bold=True)
                row += 1

        row += 1

        # Gradation
        cu = dataset.get_uniformity_coefficient() if hasattr(dataset, 'get_uniformity_coefficient') else None
        cc = dataset.get_coefficient_of_curvature() if hasattr(dataset, 'get_coefficient_of_curvature') else None

        if cu is not None:
            ws[f'A{row}'] = 'Uniformity Coefficient (Cu):'
            ws[f'B{row}'] = f"{cu:.2f}"
            ws[f'A{row}'].font = Font(bold=True)
            row += 1

        if cc is not None:
            ws[f'A{row}'] = 'Coefficient of Curvature (Cc):'
            ws[f'B{row}'] = f"{cc:.2f}"
            ws[f'A{row}'].font = Font(bold=True)
            row += 1

        # Classification
        if config.get('classification', True) and hasattr(dataset, 'classify_soil'):
            row += 1
            ws[f'A{row}'] = 'Soil Classification:'
            ws[f'B{row}'] = dataset.classify_soil()
            ws[f'A{row}'].font = Font(bold=True)

        # K-value statistics
        if results:
            valid_k_values = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]

            if valid_k_values:
                import statistics

                row += 2
                ws[f'A{row}'] = 'K-Value Statistics'
                ws[f'A{row}'].font = Font(bold=True, size=12)
                row += 1

                mean_k = statistics.mean(valid_k_values)
                median_k = statistics.median(valid_k_values)

                ws[f'A{row}'] = 'Mean K:'
                ws[f'B{row}'] = f"{mean_k:.3e} m/s"
                ws[f'A{row}'].font = Font(bold=True)
                row += 1

                ws[f'A{row}'] = 'Median K:'
                ws[f'B{row}'] = f"{median_k:.3e} m/s"
                ws[f'A{row}'].font = Font(bold=True)
                row += 1

        # Auto-size columns
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 20

    def _write_excel_grain_size(self, ws, dataset: GrainSizeData):
        """Write grain size data sheet"""
        from openpyxl.styles import Font

        # Header
        ws['A1'] = 'Particle Size (mm)'
        ws['B1'] = 'Percent Passing (%)'
        ws['A1'].font = Font(bold=True)
        ws['B1'].font = Font(bold=True)

        # Data
        for i, (size, percent) in enumerate(zip(dataset.particle_sizes, dataset.percent_passing), start=2):
            ws[f'A{i}'] = size
            ws[f'B{i}'] = percent

        ws.column_dimensions['A'].width = 20
        ws.column_dimensions['B'].width = 20

    def _write_excel_percentiles(self, ws, dataset: GrainSizeData):
        """Write percentiles sheet"""
        from openpyxl.styles import Font

        # Header
        ws['A1'] = 'Percentile'
        ws['B1'] = 'Size (mm)'
        ws['A1'].font = Font(bold=True)
        ws['B1'].font = Font(bold=True)

        # Data
        percentiles = [
            ('D5', dataset._interpolate_grain_size(5) if hasattr(dataset, '_interpolate_grain_size') else None),
            ('D10', dataset.get_d10() if hasattr(dataset, 'get_d10') else None),
            ('D20', dataset.get_d20() if hasattr(dataset, 'get_d20') else None),
            ('D30', dataset.get_d30() if hasattr(dataset, 'get_d30') else None),
            ('D50', dataset.get_d50() if hasattr(dataset, 'get_d50') else None),
            ('D60', dataset.get_d60() if hasattr(dataset, 'get_d60') else None),
        ]

        row = 2
        for name, value in percentiles:
            if value is not None:
                ws[f'A{row}'] = name
                ws[f'B{row}'] = value
                row += 1

        ws.column_dimensions['A'].width = 15
        ws.column_dimensions['B'].width = 15

    def _write_excel_k_values(self, ws, results: List[KCalculationResult], config: Dict):
        """Write K-values sheet"""
        from openpyxl.styles import Font

        # Header
        headers = ['Method', 'K (m/s)', 'K (cm/s)', 'K (m/d)', 'Status']
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col)
            cell.value = header
            cell.font = Font(bold=True)

        # Data
        for row, result in enumerate(results, start=2):
            if result.k_value is not None:
                ws.cell(row=row, column=1).value = result.method_name
                ws.cell(row=row, column=2).value = result.k_value
                ws.cell(row=row, column=3).value = result.k_value * 100
                ws.cell(row=row, column=4).value = result.k_value * 86400
                ws.cell(row=row, column=5).value = result.status.value if hasattr(result.status, 'value') else str(result.status)

        # Auto-size
        for col in range(1, 6):
            ws.column_dimensions[chr(64 + col)].width = 18

    def _write_excel_statistics(self, ws, results: List[KCalculationResult]):
        """Write statistics sheet"""
        from openpyxl.styles import Font
        import statistics

        valid_k_values = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]

        if not valid_k_values:
            return

        # Header
        ws['A1'] = 'Statistic'
        ws['B1'] = 'Value (m/s)'
        ws['C1'] = 'Value (cm/s)'
        ws['D1'] = 'Value (m/d)'

        for col in ['A', 'B', 'C', 'D']:
            ws[f'{col}1'].font = Font(bold=True)

        # Calculate statistics
        mean_k = statistics.mean(valid_k_values)
        median_k = statistics.median(valid_k_values)
        min_k = min(valid_k_values)
        max_k = max(valid_k_values)
        stdev_k = statistics.stdev(valid_k_values) if len(valid_k_values) > 1 else 0

        stats_data = [
            ('Mean', mean_k),
            ('Median', median_k),
            ('Std Dev', stdev_k),
            ('Min', min_k),
            ('Max', max_k),
        ]

        for row, (name, value) in enumerate(stats_data, start=2):
            ws[f'A{row}'] = name
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = value
            ws[f'C{row}'] = value * 100
            ws[f'D{row}'] = value * 86400

        # Auto-size
        for col in ['A', 'B', 'C', 'D']:
            ws.column_dimensions[col].width = 15

    def _write_excel_combined_summary(self, ws, datasets: List[tuple], config: Dict):
        """Write combined summary comparing all datasets"""
        from openpyxl.styles import Font

        # Header
        ws['A1'] = 'Sample'
        headers = ['Sample']
        col = 2

        # Get all method names
        all_methods = set()
        for _, _, results in datasets:
            if results:
                for result in results:
                    all_methods.add(result.method_name)

        for method in sorted(all_methods):
            ws.cell(row=1, column=col).value = method
            ws.cell(row=1, column=col).font = Font(bold=True)
            col += 1

        # Add statistical columns
        ws.cell(row=1, column=col).value = 'Mean'
        ws.cell(row=1, column=col).font = Font(bold=True)
        col += 1
        ws.cell(row=1, column=col).value = 'Median'
        ws.cell(row=1, column=col).font = Font(bold=True)

        # Data rows
        for row, (name, dataset, results) in enumerate(datasets, start=2):
            ws.cell(row=row, column=1).value = name

            # Create method -> k_value mapping
            method_values = {}
            if results:
                for result in results:
                    if result.k_value is not None:
                        method_values[result.method_name] = result.k_value

            # Fill in K-values
            col = 2
            for method in sorted(all_methods):
                if method in method_values:
                    ws.cell(row=row, column=col).value = method_values[method]
                col += 1

            # Calculate and fill statistics
            if method_values:
                import statistics
                values = list(method_values.values())
                ws.cell(row=row, column=col).value = statistics.mean(values)
                col += 1
                ws.cell(row=row, column=col).value = statistics.median(values)

    def _write_excel_dataset_combined(self, ws, name: str, dataset: GrainSizeData,
                                     results: List[KCalculationResult], config: Dict):
        """Write all data for a single dataset on one sheet"""
        from openpyxl.styles import Font

        row = 1

        # Title
        ws[f'A{row}'] = name
        ws[f'A{row}'].font = Font(size=14, bold=True)
        row += 2

        # Grain sizes
        ws[f'A{row}'] = 'Key Grain Sizes'
        ws[f'A{row}'].font = Font(bold=True)
        row += 1

        percentiles = {
            'D10': dataset.get_d10() if hasattr(dataset, 'get_d10') else None,
            'D50': dataset.get_d50() if hasattr(dataset, 'get_d50') else None,
            'D60': dataset.get_d60() if hasattr(dataset, 'get_d60') else None,
        }

        for pname, value in percentiles.items():
            if value is not None:
                ws[f'A{row}'] = pname
                ws[f'B{row}'] = value
                row += 1

        row += 1

        # K-values
        ws[f'A{row}'] = 'K-Values'
        ws[f'A{row}'].font = Font(bold=True)
        row += 1

        ws[f'A{row}'] = 'Method'
        ws[f'B{row}'] = 'K (m/s)'
        ws[f'A{row}'].font = Font(bold=True)
        ws[f'B{row}'].font = Font(bold=True)
        row += 1

        if results:
            for result in results:
                if result.k_value is not None:
                    ws[f'A{row}'] = result.method_name
                    ws[f'B{row}'] = result.k_value
                    row += 1

    def _write_excel_method_comparison(self, ws, method: str, datasets: List[tuple]):
        """Write comparison sheet for a specific method across all datasets"""
        from openpyxl.styles import Font

        # Header
        ws['A1'] = 'Sample'
        ws['B1'] = f'{method} K (m/s)'
        ws['C1'] = 'K (cm/s)'
        ws['D1'] = 'K (m/d)'
        ws['E1'] = 'Status'

        for col in ['A', 'B', 'C', 'D', 'E']:
            ws[f'{col}1'].font = Font(bold=True)

        # Data
        row = 2
        for name, dataset, results in datasets:
            if results:
                for result in results:
                    if result.method_name == method and result.k_value is not None:
                        ws[f'A{row}'] = name
                        ws[f'B{row}'] = result.k_value
                        ws[f'C{row}'] = result.k_value * 100
                        ws[f'D{row}'] = result.k_value * 86400
                        ws[f'E{row}'] = result.status.value if hasattr(result.status, 'value') else str(result.status)
                        row += 1
                        break

        # Auto-size
        for col in ['A', 'B', 'C', 'D', 'E']:
            ws.column_dimensions[col].width = 18

    # ==================== JSON EXPORT ====================

    def _export_json(self, name: str, dataset: GrainSizeData,
                    results: List[KCalculationResult], config: Dict):
        """Export dataset to JSON format"""
        output_dir = config['output_dir']
        template = config['filename_template']

        filename = self._format_filename(template, name, '.json')
        filepath = os.path.join(output_dir, filename)

        # Build JSON structure
        data = {
            'sample_name': name,
            'metadata': {
                'temperature': dataset.temperature,
                'porosity': dataset.current_porosity or dataset.porosity,
                'file_path': dataset.file_path if hasattr(dataset, 'file_path') else None,
            }
        }

        # Grain size distribution
        if config.get('grain_distribution', True):
            data['grain_size_distribution'] = {
                'particle_sizes_mm': dataset.particle_sizes,
                'percent_passing': dataset.percent_passing,
            }

        # Percentiles
        if config.get('percentiles', True):
            data['percentiles'] = {
                'D10': dataset.get_d10() if hasattr(dataset, 'get_d10') else None,
                'D20': dataset.get_d20() if hasattr(dataset, 'get_d20') else None,
                'D30': dataset.get_d30() if hasattr(dataset, 'get_d30') else None,
                'D50': dataset.get_d50() if hasattr(dataset, 'get_d50') else None,
                'D60': dataset.get_d60() if hasattr(dataset, 'get_d60') else None,
            }

        # Gradation
        if config.get('gradation', True):
            data['gradation'] = {
                'uniformity_coefficient': dataset.get_uniformity_coefficient() if hasattr(dataset, 'get_uniformity_coefficient') else None,
                'coefficient_of_curvature': dataset.get_coefficient_of_curvature() if hasattr(dataset, 'get_coefficient_of_curvature') else None,
            }

        # Classification
        if config.get('classification', True) and hasattr(dataset, 'classify_soil'):
            data['classification'] = dataset.classify_soil()

        # K-values
        if config.get('k_values', True) and results:
            data['k_values'] = []
            for result in results:
                if result.k_value is not None:
                    k_data = {
                        'method': result.method_name,
                        'k_m_s': result.k_value,
                        'k_cm_s': result.k_value * 100,
                        'k_m_d': result.k_value * 86400,
                        'status': result.status.value if hasattr(result.status, 'value') else str(result.status),
                        'status_message': result.status_message,
                        'grain_size_used': result.grain_size_used,
                    }

                    if config.get('formulas', False):
                        k_data['formula'] = result.formula_used

                    data['k_values'].append(k_data)

        # Statistics
        if config.get('statistics', True) and results:
            valid_k_values = [r.k_value for r in results if r.k_value is not None and r.k_value > 0]

            if valid_k_values:
                import statistics

                data['statistics'] = {
                    'mean_k_m_s': statistics.mean(valid_k_values),
                    'median_k_m_s': statistics.median(valid_k_values),
                    'min_k_m_s': min(valid_k_values),
                    'max_k_m_s': max(valid_k_values),
                    'stdev_k_m_s': statistics.stdev(valid_k_values) if len(valid_k_values) > 1 else 0,
                    'count': len(valid_k_values),
                }

        # Write JSON file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

        self.exported_files.append(filepath)

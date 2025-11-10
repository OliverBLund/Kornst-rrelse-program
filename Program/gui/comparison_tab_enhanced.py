"""
Enhanced comparison table methods with color-coding
These methods will replace the existing ones in comparison_tab.py
"""

from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import numpy as np


def update_grain_parameters_table_enhanced(self):
    """Update grain size parameters table with color-coding and statistics"""
    params = [
        ("D10 (mm)", "d10"),
        ("D20 (mm)", "d20"),
        ("D30 (mm)", "d30"),
        ("D50 (mm)", "d50"),
        ("D60 (mm)", "d60"),
        ("Cu", "cu"),
        ("Cc", "cc"),
        ("Gradation", "gradation")
    ]

    self.grain_comparison_table.setRowCount(len(params))
    self.grain_comparison_table.setColumnCount(len(self.selected_datasets) + 2)
    self.grain_comparison_table.setAlternatingRowColors(True)

    # Set headers
    headers = ["Parameter"] + [tab.get_dataset_name() for tab in self.selected_datasets] + ["Statistics"]
    self.grain_comparison_table.setHorizontalHeaderLabels(headers)

    for row, (param_name, param_key) in enumerate(params):
        # Parameter name
        param_item = QTableWidgetItem(param_name)
        param_item.setFlags(param_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        font = param_item.font()
        font.setBold(True)
        param_item.setFont(font)
        self.grain_comparison_table.setItem(row, 0, param_item)

        # Collect values for this parameter
        values = []
        for col, tab in enumerate(self.selected_datasets, 1):
            dataset = tab.get_dataset()
            value = None
            value_str = "N/A"

            if param_key == "d10":
                value = dataset.get_d10()
                value_str = f"{value:.3f}" if value else "N/A"
            elif param_key == "d20":
                value = dataset.get_d20()
                value_str = f"{value:.3f}" if value else "N/A"
            elif param_key == "d30":
                value = dataset.get_d30()
                value_str = f"{value:.3f}" if value else "N/A"
            elif param_key == "d50":
                value = dataset.get_d50()
                value_str = f"{value:.3f}" if value else "N/A"
            elif param_key == "d60":
                value = dataset.get_d60()
                value_str = f"{value:.3f}" if value else "N/A"
            elif param_key == "cu":
                d10, d60 = dataset.get_d10(), dataset.get_d60()
                if d10 and d60 and d10 > 0:
                    value = d60 / d10
                    value_str = f"{value:.2f}"
            elif param_key == "cc":
                d10, d30, d60 = dataset.get_d10(), dataset.get_d30(), dataset.get_d60()
                if d10 and d30 and d60 and d10 > 0 and d60 > 0:
                    value = (d30 * d30) / (d10 * d60)
                    value_str = f"{value:.2f}"
            elif param_key == "gradation":
                d10, d60 = dataset.get_d10(), dataset.get_d60()
                if d10 and d60 and d10 > 0:
                    cu = d60 / d10
                    if cu < 4:
                        value_str = "Uniform"
                    elif cu < 6:
                        value_str = "Moderate"
                    else:
                        value_str = "Well-graded"
                value = cu if d10 and d60 else None

            item = QTableWidgetItem(value_str)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Store numeric value for color-coding
            if value is not None:
                values.append(value)
                item.setData(Qt.ItemDataRole.UserRole, value)

            self.grain_comparison_table.setItem(row, col, item)

        # Color-code numeric values (not gradation)
        if param_key != "gradation" and len(values) > 1:
            min_val = min(values)
            max_val = max(values)

            for col in range(1, len(self.selected_datasets) + 1):
                item = self.grain_comparison_table.item(row, col)
                value = item.data(Qt.ItemDataRole.UserRole)

                if value is not None:
                    # Green for smaller, red for larger (except Cu - opposite)
                    if param_key == "cu":
                        # For Cu, higher is better (well-graded)
                        normalized = (value - min_val) / (max_val - min_val) if max_val > min_val else 0.5
                        color = self._interpolate_color(normalized, reverse=False)
                    else:
                        # For grain sizes, color based on relative position
                        normalized = (value - min_val) / (max_val - min_val) if max_val > min_val else 0.5
                        color = self._interpolate_color(normalized)

                    item.setBackground(color)

        # Statistics column
        if values:
            mean_val = np.mean(values)
            std_val = np.std(values)
            cv = (std_val / mean_val * 100) if mean_val > 0 else 0

            if param_key == "gradation":
                stats_str = f"Avg Cu: {mean_val:.2f}"
            else:
                stats_str = f"μ={mean_val:.2f}\nCV={cv:.1f}%"

            stats_item = QTableWidgetItem(stats_str)
            stats_item.setFlags(stats_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            stats_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            stats_item.setBackground(QColor(240, 240, 240))
            self.grain_comparison_table.setItem(row, len(self.selected_datasets) + 1, stats_item)

    self.grain_comparison_table.resizeColumnsToContents()


def update_permeability_classification_table_enhanced(self):
    """Update permeability classification table"""
    self.permeability_table.setRowCount(1)
    self.permeability_table.setColumnCount(len(self.selected_datasets) + 1)
    self.permeability_table.setAlternatingRowColors(True)

    headers = ["Dataset"] + [tab.get_dataset_name() for tab in self.selected_datasets]
    self.permeability_table.setHorizontalHeaderLabels(headers)

    # Row: Permeability classification
    label_item = QTableWidgetItem("Classification")
    label_item.setFlags(label_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    font = label_item.font()
    font.setBold(True)
    label_item.setFont(font)
    self.permeability_table.setItem(0, 0, label_item)

    for col, tab in enumerate(self.selected_datasets, 1):
        results = tab.get_results()
        valid_k = [r.k_value for r in results if r.k_value and r.k_value > 0]

        if valid_k:
            mean_k = np.mean(valid_k)

            # Classify permeability
            if mean_k > 1e-2:
                classification = "Very High\n(Gravel)"
                color = QColor(76, 175, 80, 100)  # Green
            elif mean_k > 1e-4:
                classification = "High\n(Clean Sand)"
                color = QColor(139, 195, 74, 100)  # Light green
            elif mean_k > 1e-5:
                classification = "Moderate\n(Fine Sand)"
                color = QColor(255, 235, 59, 100)  # Yellow
            elif mean_k > 1e-7:
                classification = "Low\n(Silt)"
                color = QColor(255, 152, 0, 100)  # Orange
            else:
                classification = "Very Low\n(Clay)"
                color = QColor(244, 67, 54, 100)  # Red

            item = QTableWidgetItem(f"{classification}\n{mean_k:.2e} m/s")
        else:
            classification = "Not Calculated"
            item = QTableWidgetItem(classification)
            color = QColor(200, 200, 200)

        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setBackground(color)
        self.permeability_table.setItem(0, col, item)

    self.permeability_table.resizeColumnsToContents()
    self.permeability_table.resizeRowsToContents()


def _interpolate_color(self, normalized_value, reverse=False):
    """
    Interpolate color between green and red based on normalized value (0-1)

    Args:
        normalized_value: Value between 0 and 1
        reverse: If True, green=high, red=low. If False, green=low, red=high
    """
    if reverse:
        normalized_value = 1 - normalized_value

    # Green (low) -> Yellow (mid) -> Red (high)
    if normalized_value < 0.5:
        # Green to yellow
        r = int(255 * (normalized_value * 2))
        g = 200
        b = 100
    else:
        # Yellow to red
        r = 255
        g = int(200 * (1 - (normalized_value - 0.5) * 2))
        b = 100

    return QColor(r, g, b, 80)  # 80 = semi-transparent

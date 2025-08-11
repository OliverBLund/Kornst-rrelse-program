"""
Simple plot widget placeholder for grain size distribution visualization
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
import math

class PlotWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.k_results = {}
        self.sample_data = None
        self.sample_name = "Sample"
        self.show_characteristic_lines = True
        
        # Apply professional geotechnical styling
        self.setStyleSheet("""
            QWidget {
                background-color: #fafaf7;
            }
            QLabel {
                color: #2f2f2f;
                font-weight: bold;
                font-size: 12px;
            }
            QFrame {
                border: 1px solid #8b7355;
                border-radius: 4px;
                background-color: #ffffff;
            }
        """)
        
        self.method_colors = {
            "Hazen": QColor(183, 28, 28),        # Deep red
            "Terzaghi": QColor(46, 125, 50),     # Forest green
            "Beyer": QColor(21, 101, 192),       # Deep blue
            "Slichter": QColor(239, 108, 0),     # Deep orange
            "Kozeny-Carman": QColor(123, 31, 162), # Deep purple
            "Shepherd": QColor(194, 24, 91),     # Deep pink
            "Zunker": QColor(0, 172, 193),       # Teal
            "Zamarin": QColor(251, 192, 45),     # Golden yellow
            "USBR": QColor(109, 76, 65),         # Earth brown
            "Sauerbrei": QColor(84, 110, 122)    # Blue gray
        }
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the plot widget layout"""
        layout = QVBoxLayout(self)
        
        # Create placeholder plots using simple drawing
        self.main_plot = PlaceholderPlot("Grain Size Distribution Curve", 
                                       "Grain Diameter (mm)", 
                                       "Cumulative % Passing",
                                       self.method_colors)
        self.histogram_plot = PlaceholderPlot("K-Value Distribution by Method", 
                                            "Hydraulic Conductivity Methods", 
                                            "K-Value (m/s)",
                                            self.method_colors)
        
        # Add plots to layout
        layout.addWidget(self.main_plot)
        layout.addWidget(self.histogram_plot)
        
    def update_plot(self, diameters=None, cumulative=None, sample_name="Sample"):
        """Update plot with new data - placeholder implementation"""
        if diameters is not None and cumulative is not None:
            self.sample_data = (diameters, cumulative)
            self.sample_name = sample_name
            self.main_plot.set_sample_data(diameters, cumulative, sample_name)
            self.main_plot.set_data_info(f"Data: {sample_name} ({len(diameters)} points)")
            self.histogram_plot.set_data_info(f"K-Values from: {sample_name}")
        else:
            self.main_plot.set_sample_data(None, None, sample_name)
            self.main_plot.set_data_info(f"Sample: {sample_name} (placeholder data)")
        
    def reset_view(self):
        """Reset plot view to default - placeholder implementation"""
        self.main_plot.set_data_info("Plot view reset")
        self.histogram_plot.set_data_info("Plot view reset")
        
    def export_plot(self, filename, dpi=300):
        """Export current plot to file - placeholder implementation"""
        print(f"Plot export requested to: {filename}")
        print("Export functionality will be available once matplotlib is configured.")
        
    def add_k_calculation_results(self, k_results):
        """Add K calculation results - display as colored bars"""
        self.k_results = k_results
        self.main_plot.set_k_results(k_results)
        self.histogram_plot.set_k_results(k_results)
        
        k_text = "K Results: "
        for method, k_value in k_results.items():
            k_text += f"{method}={k_value:.1e} "
        
        self.main_plot.set_data_info(k_text)


class PlaceholderPlot(QFrame):
    """A simple placeholder plot widget that draws a basic chart"""
    
    def __init__(self, title, xlabel, ylabel, method_colors):
        super().__init__()
        self.title = title
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.data_info = "No data loaded - use 'Open Data' to import grain size files"
        self.method_colors = method_colors
        self.k_results = {}
        self.sample_data = None
        self.sample_name = "Sample"
        self.legend_items = []
        
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(250)
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 2px solid #8b7355;
                border-radius: 6px;
            }
        """)
        
    def set_data_info(self, info):
        """Set data information text"""
        self.data_info = info
        self.update()
        
    def set_sample_data(self, diameters, cumulative, sample_name):
        """Set sample data for the grain size distribution"""
        self.sample_data = (diameters, cumulative) if diameters is not None else None
        self.sample_name = sample_name
        self.update_legend()
        self.update()
        
    def set_k_results(self, k_results):
        """Set K calculation results for display"""
        self.k_results = k_results
        self.update_legend()
        self.update()
        
    def update_legend(self):
        """Update the dynamic legend based on current display"""
        self.legend_items = []
        
        # Add sample data to legend
        if "Distribution" in self.title:
            self.legend_items.append({
                "label": f"Grain Size Curve ({self.sample_name})",
                "color": QColor(0, 100, 200),
                "line_style": "solid"
            })
            
            # Add characteristic diameter lines
            if self.sample_data or True:  # Show even for placeholder
                d_info = [
                    ("D10 = 0.15mm", QColor(255, 0, 0)),
                    ("D30 = 0.35mm", QColor(0, 150, 0)),
                    ("D60 = 0.65mm", QColor(128, 0, 128))
                ]
                for label, color in d_info:
                    self.legend_items.append({
                        "label": label,
                        "color": color,
                        "line_style": "dashed"
                    })
            
            # Add methods used in calculations
            if self.k_results:
                for method in list(self.k_results.keys())[:3]:  # Show top 3 methods
                    if method in self.method_colors:
                        self.legend_items.append({
                            "label": f"{method} Method",
                            "color": self.method_colors[method],
                            "line_style": "dotted"
                        })
        
        elif "K-Value" in self.title:
            # Legend for K-value plot
            if self.k_results:
                for method, k_value in self.k_results.items():
                    if method in self.method_colors:
                        self.legend_items.append({
                            "label": f"{method}: {k_value:.1e} m/s",
                            "color": self.method_colors[method],
                            "line_style": "solid"
                        })
        
    def paintEvent(self, a0):
        """Draw a simple placeholder chart"""
        super().paintEvent(a0)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get widget dimensions
        width = self.width()
        height = self.height()
        margin = 50
        
        # Define plot area
        plot_left = margin
        plot_right = width - margin
        plot_top = margin + 30
        plot_bottom = height - margin
        plot_width = plot_right - plot_left
        plot_height = plot_bottom - plot_top
        
        # Draw background with professional styling
        painter.fillRect(plot_left, plot_top, plot_width, plot_height, QColor(252, 252, 250))
        
        # Draw border with geotechnical color
        pen = QPen(QColor(139, 115, 85))  # Earth brown
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(plot_left, plot_top, plot_width, plot_height)
        
        # Draw title with professional styling
        font = painter.font()
        font.setBold(True)
        font.setPointSize(13)
        painter.setFont(font)
        painter.setPen(QColor(47, 47, 47))  # Dark gray
        title_width = painter.fontMetrics().horizontalAdvance(self.title)
        painter.drawText(width//2 - title_width//2, 20, self.title)
        
        # Reset font
        font.setBold(False)
        font.setPointSize(9)
        painter.setFont(font)
        
        # Draw axis labels
        painter.save()
        painter.translate(15, height//2)
        painter.rotate(-90)
        ylabel_width = painter.fontMetrics().horizontalAdvance(self.ylabel)
        painter.drawText(-ylabel_width//2, 0, self.ylabel)
        painter.restore()
        
        xlabel_width = painter.fontMetrics().horizontalAdvance(self.xlabel)
        painter.drawText(width//2 - xlabel_width//2, height - 5, self.xlabel)
        
        # Draw grid lines with professional styling
        pen = QPen(QColor(210, 200, 185))  # Light earth tone
        pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)
        
        # Vertical grid lines
        for i in range(1, 5):
            x = plot_left + (plot_width * i) // 5
            painter.drawLine(x, plot_top, x, plot_bottom)
            
        # Horizontal grid lines
        for i in range(1, 4):
            y = plot_top + (plot_height * i) // 4
            painter.drawLine(plot_left, y, plot_right, y)
        
        # Draw content based on plot type
        if "K-Value Distribution" in self.title:
            self.draw_k_value_bars(painter, plot_left, plot_top, plot_width, plot_height, plot_bottom)
        else:
            self.draw_grain_size_curves(painter, plot_left, plot_top, plot_width, plot_height, plot_bottom)
        
        # Draw dynamic legend
        self.draw_legend(painter, width, plot_top)
        
        # Draw data info with professional styling
        painter.setPen(QColor(93, 78, 55))  # Earth brown text
        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(plot_left + 10, plot_top + 15, self.data_info)
        
    def draw_legend(self, painter, width, plot_top):
        """Draw dynamic legend based on current display"""
        if not self.legend_items:
            return
            
        # Legend settings
        legend_x = width - 250
        legend_y = plot_top + 40
        legend_width = 230
        line_height = 16
        legend_height = len(self.legend_items) * line_height + 20
        
        # Draw legend background
        painter.fillRect(legend_x, legend_y, legend_width, legend_height, QColor(255, 255, 255, 240))
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRect(legend_x, legend_y, legend_width, legend_height)
        
        # Draw legend title
        font = painter.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(legend_x + 5, legend_y + 15, "Legend")
        
        # Draw legend items
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        
        for i, item in enumerate(self.legend_items):
            y = legend_y + 25 + i * line_height
            
            # Draw line/color indicator
            pen = QPen(item["color"], 2)
            if item["line_style"] == "dashed":
                pen.setStyle(Qt.PenStyle.DashLine)
            elif item["line_style"] == "dotted":
                pen.setStyle(Qt.PenStyle.DotLine)
            else:
                pen.setStyle(Qt.PenStyle.SolidLine)
            
            painter.setPen(pen)
            painter.drawLine(legend_x + 8, y, legend_x + 25, y)
            
            # Draw text
            painter.setPen(QColor(0, 0, 0))
            painter.drawText(legend_x + 30, y + 4, item["label"])
        
    def draw_k_value_bars(self, painter, plot_left, plot_top, plot_width, plot_height, plot_bottom):
        """Draw K-value bars for different methods"""
        if not self.k_results:
            # Show empty state message for K-values
            painter.setPen(QColor(120, 120, 120))
            font = painter.font()
            font.setPointSize(14)
            font.setBold(True)
            painter.setFont(font)
            
            empty_text = "🧮 Calculate K values to view method comparison"
            text_width = painter.fontMetrics().horizontalAdvance(empty_text)
            text_x = plot_left + (plot_width - text_width) // 2
            text_y = plot_top + plot_height // 2
            painter.drawText(text_x, text_y, empty_text)
            
            # Draw subtitle
            font.setPointSize(10)
            font.setBold(False)
            painter.setFont(font)
            subtitle = "Load data first, then click 'Calculate K Values'"
            subtitle_width = painter.fontMetrics().horizontalAdvance(subtitle)
            subtitle_x = plot_left + (plot_width - subtitle_width) // 2
            painter.drawText(subtitle_x, text_y + 25, subtitle)
            return
        
        # Draw actual K-value results
        methods = list(self.k_results.keys())
        for i, (method, k_value) in enumerate(self.k_results.items()):
            if method in self.method_colors:
                color = self.method_colors[method]
                bar_width = plot_width // len(methods) - 5
                x = plot_left + i * (plot_width // len(methods)) + 2
                
                # Normalize bar height based on K-value (log scale)
                log_k = math.log10(max(k_value, 1e-10))  # Avoid log(0)
                normalized_height = max(0.1, min(0.9, (log_k + 10) / 8))  # Rough normalization
                bar_height = plot_height * normalized_height
                y = plot_bottom - bar_height
                
                # Draw bar
                painter.fillRect(int(x), int(y), bar_width, int(bar_height), color.lighter(150))
                
                pen = QPen(color)
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(int(x), int(y), bar_width, int(bar_height))
                
                # Draw labels
                painter.setPen(QColor(0, 0, 0))
                painter.save()
                painter.translate(x + bar_width//2, plot_bottom + 15)
                painter.rotate(-45)
                painter.drawText(-20, 0, method[:8])
                painter.restore()
                
                painter.drawText(int(x), int(y) - 5, f"{k_value:.1e}")
    
    def draw_grain_size_curves(self, painter, plot_left, plot_top, plot_width, plot_height, plot_bottom):
        """Draw grain size distribution curves with method highlights"""
        plot_right = plot_left + plot_width
        
        # If no sample data, show empty state message
        if self.sample_data is None:
            painter.setPen(QColor(120, 120, 120))
            font = painter.font()
            font.setPointSize(14)
            font.setBold(True)
            painter.setFont(font)
            
            empty_text = "📂 Load grain size data to view distribution curve"
            text_width = painter.fontMetrics().horizontalAdvance(empty_text)
            text_x = plot_left + (plot_width - text_width) // 2
            text_y = plot_top + plot_height // 2
            painter.drawText(text_x, text_y, empty_text)
            
            # Draw subtitle
            font.setPointSize(10)
            font.setBold(False)
            painter.setFont(font)
            subtitle = "Use 'Open Data' button in toolbar to import CSV files"
            subtitle_width = painter.fontMetrics().horizontalAdvance(subtitle)
            subtitle_x = plot_left + (plot_width - subtitle_width) // 2
            painter.drawText(subtitle_x, text_y + 25, subtitle)
            return
        
        # Draw main cumulative curve
        pen = QPen(QColor(0, 100, 200))
        pen.setWidth(3)
        painter.setPen(pen)
        
        points = []
        for i in range(plot_width):
            x = plot_left + i
            # Generate S-curve
            t = i / plot_width
            y_norm = 1 / (1 + math.exp(-8 * (t - 0.5)))  # Sigmoid function
            y = plot_bottom - y_norm * plot_height
            points.append((x, y))
        
        # Draw the main curve
        for i in range(1, len(points)):
            painter.drawLine(int(points[i-1][0]), int(points[i-1][1]), 
                           int(points[i][0]), int(points[i][1]))
        
        # Draw characteristic diameter lines and annotations
        d_values = [0.15, 0.35, 0.65]  # D10, D30, D60
        d_names = ["D10", "D30", "D60"]
        percentages = [10, 30, 60]
        colors = [QColor(255, 0, 0), QColor(0, 150, 0), QColor(128, 0, 128)]
        
        for i, (d_val, d_name, percent, color) in enumerate(zip(d_values, d_names, percentages, colors)):
            # Vertical line
            x_pos = plot_left + (plot_width * (0.2 + i * 0.3))
            y_pos = plot_bottom - (plot_height * percent / 100)
            
            pen = QPen(color)
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            
            painter.drawLine(int(x_pos), plot_top, int(x_pos), plot_bottom)
            painter.drawLine(plot_left, int(y_pos), plot_right, int(y_pos))
            
            # Small annotations near the lines
            painter.setPen(QColor(0, 0, 0))
            painter.drawText(int(x_pos) + 5, plot_top + 20, f"{d_name}")
            painter.drawText(plot_left + 5, int(y_pos) - 5, f"{percent}%")
        
        # Draw method indicators if K calculations have been performed
        if self.k_results:
            # Add small colored dots or markers for methods that use specific diameters
            d10_methods = ["Hazen", "Terzaghi", "Beyer", "Slichter", "Kozeny-Carman", "Zunker", "Zamarin", "Sauerbrei"]
            d20_methods = ["Shepherd", "USBR"]
            
            # Mark D10 line with method colors
            x_d10 = plot_left + (plot_width * 0.2)
            for i, method in enumerate([m for m in d10_methods if m in self.k_results][:3]):
                if method in self.method_colors:
                    color = self.method_colors[method]
                    painter.fillRect(int(x_d10) - 15, plot_top + 30 + i * 8, 6, 6, color)
            
            # Mark D20 line with method colors  
            x_d20 = plot_left + (plot_width * 0.35)
            for i, method in enumerate([m for m in d20_methods if m in self.k_results]):
                if method in self.method_colors:
                    color = self.method_colors[method]
                    painter.fillRect(int(x_d20) - 15, plot_top + 30 + i * 8, 6, 6, color)

# Implementation Code Examples
## Specific Code to Add Missing Content to Reports

---

## 1. COMPREHENSIVE PERCENTILE TABLE

### Method to Add to ReportGenerator

```python
def _format_complete_percentile_table(self, dataset: GrainSizeData) -> str:
    """
    Generate HTML table with comprehensive percentile distribution
    Mirrors the percentile display from statistics_tab.py
    """
    from k_calculations import KCalculator
    
    calculator = KCalculator()
    grain_data = {
        "particle_sizes": list(dataset.particle_sizes),
        "percent_passing": list(dataset.percent_passing),
    }
    
    # Calculate all percentiles
    percentiles = {}
    standard_percentiles = [
        5, 10, 15, 16, 17, 20, 25, 30, 40, 50, 60, 70, 75, 80, 84, 85, 90, 95
    ]
    
    for p in standard_percentiles:
        value = calculator._interpolate_percentile(grain_data, p)
        if value:
            percentiles[p] = value
    
    # Key percentiles used by multiple methods
    key_percentiles = {10, 20, 30, 50, 60}
    
    html = '<h3>Complete Grain Size Percentiles</h3>'
    html += '<table>'
    html += '<tr><th>Percentile</th><th>Size (mm)</th><th>Methods Using</th></tr>'
    
    # Define which percentiles are used by which methods
    percentile_usage = {
        5: ['Barr'],
        10: ['Hazen', 'Hazen_1892', 'Slichter', 'Terzaghi', 'Beyer', 'Kozeny-Carman', 'Zunker', 'Zamarin', 'Chapuis', 'Alyamani-Sen'],
        16: ['Sorting (σ)'],
        17: ['Sauerbrei'],
        20: ['USBR', 'Beyer (fallback)'],
        30: ['Cu', 'Cc calculations'],
        50: ['Kruger', 'Alyamani-Sen', 'Shepherd'],
        60: ['Beyer', 'Barr', 'Cu calculation'],
        84: ['Sorting (σ)', 'Krumbein-Monk'],
        95: ['Krumbein-Monk']
    }
    
    for p in standard_percentiles:
        if p not in percentiles:
            continue
            
        size = percentiles[p]
        is_key = p in key_percentiles
        
        # Format percentile with star if key
        percentile_label = f"D{p}"
        if is_key:
            percentile_label += " ⭐"
        
        # Get methods using this percentile
        methods = percentile_usage.get(p, [])
        methods_str = ", ".join(methods) if methods else "Reference only"
        
        # Highlight key percentiles
        if is_key:
            html += f'<tr style="background-color: #ffffcc;">'
        else:
            html += '<tr>'
            
        html += f'<td>{percentile_label}</td>'
        html += f'<td style="text-align: right;">{size:.4f}</td>'
        html += f'<td style="font-size: 9px;">{methods_str}</td>'
        html += '</tr>'
    
    html += '</table>'
    
    # Add note about range and span
    if percentiles:
        min_size = min(percentiles.values())
        max_size = max(percentiles.values())
        span = max_size / min_size if min_size > 0 else 0
        
        html += f'<p style="font-size: 10px; color: #666;">'
        html += f'<strong>Range:</strong> {min_size:.4f} - {max_size:.4f} mm | '
        html += f'<strong>Span Ratio (D95/D5):</strong> {span:.2f}x'
        html += '</p>'
    
    return html
```

### Usage in grain_size_report
```python
def generate_grain_size_report(self, dataset: GrainSizeData, ...):
    # ... existing code ...
    
    if sections.get('results', True):
        html += f"""
        <div style="page-break-before: auto;">
        <h2>Results & Analysis</h2>
        
        <h3>Characteristic Grain Sizes</h3>
        <!-- existing stat cards -->
        
        <!-- ADD NEW SECTION -->
        {self._format_complete_percentile_table(dataset)}
        
        <h3>Soil Classification Parameters</h3>
        <!-- existing table -->
        </div>
        """
```

---

## 2. SORTING COEFFICIENT (σ) CALCULATIONS

### Method to Add to ReportGenerator

```python
def _format_sorting_coefficient_analysis(self, dataset: GrainSizeData) -> str:
    """
    Calculate and format Sorting Coefficient (σ) analysis
    Formula: σ = √(D84/D16)
    """
    from k_calculations import KCalculator
    import math
    
    calculator = KCalculator()
    grain_data = {
        "particle_sizes": list(dataset.particle_sizes),
        "percent_passing": list(dataset.percent_passing),
    }
    
    d16 = calculator._interpolate_percentile(grain_data, 16)
    d84 = calculator._interpolate_percentile(grain_data, 84)
    
    if not d16 or not d84 or d16 <= 0 or d84 <= 0:
        return '<p style="color: #999;">Sorting Coefficient: Cannot calculate (insufficient data)</p>'
    
    sigma = math.sqrt(d84 / d16)
    
    # Classify sorting
    if sigma < 2:
        classification = "Well sorted"
        description = "Particles are very similar in size; highly uniform distribution"
    elif sigma < 4:
        classification = "Moderately sorted"
        description = "Reasonable range of particle sizes; typical for many soils"
    else:
        classification = "Poorly sorted"
        description = "Wide range of particle sizes; mixed grain size distribution"
    
    html = '''
    <h3>Sorting Coefficient (σ)</h3>
    <table>
        <tr>
            <th>Parameter</th>
            <th>Value</th>
            <th>Interpretation</th>
        </tr>
        <tr>
            <td>Sorting Coefficient (σ)</td>
            <td style="text-align: center; font-weight: bold;">{:.2f}</td>
            <td><strong>{}</strong><br/>{}</td>
        </tr>
        <tr>
            <td colspan="3" style="font-size: 9px; color: #666; background-color: #f9f9f9;">
                <strong>Formula:</strong> σ = √(D₈₄/D₁₆) = √({:.4f}/{:.4f})<br/>
                <strong>Classification:</strong>
                σ &lt; 2 = Well sorted | 
                2 ≤ σ &lt; 4 = Moderately sorted | 
                σ ≥ 4 = Poorly sorted
            </td>
        </tr>
    </table>
    '''.format(sigma, classification, description, d84, d16)
    
    return html

def _format_span_ratio_analysis(self, dataset: GrainSizeData) -> str:
    """
    Calculate and format Span Ratio (D95/D5)
    Indicates overall range of particle sizes
    """
    from k_calculations import KCalculator
    
    calculator = KCalculator()
    grain_data = {
        "particle_sizes": list(dataset.particle_sizes),
        "percent_passing": list(dataset.percent_passing),
    }
    
    d5 = calculator._interpolate_percentile(grain_data, 5)
    d95 = calculator._interpolate_percentile(grain_data, 95)
    
    if not d5 or not d95 or d5 <= 0:
        return '<p style="color: #999;">Span Ratio: Cannot calculate (insufficient data)</p>'
    
    span = d95 / d5
    
    html = f'''
    <p style="margin-top: 15px; font-size: 10pt;">
        <strong>Span Ratio (D₉₅/D₅):</strong> {span:.2f}x<br/>
        <span style="font-size: 9px; color: #666;">
        Range of grain sizes from {d5:.4f} mm (D₅) to {d95:.4f} mm (D₉₅).
        Higher values indicate wider distribution of particle sizes.
        </span>
    </p>
    '''
    
    return html
```

### Updated gradation section in generate_grain_size_report
```python
# In generate_grain_size_report, in results section:

# Add after existing Cu/Cc table
html += self._format_sorting_coefficient_analysis(dataset)
html += self._format_span_ratio_analysis(dataset)
```

---

## 3. DATA QUALITY ASSESSMENT SECTION

### Method to Add to ReportGenerator

```python
def _assess_data_quality(self, dataset: GrainSizeData) -> Dict:
    """
    Assess the quality of input grain size data
    Returns dict with quality metrics
    """
    import numpy as np
    
    sizes = np.array(dataset.particle_sizes)
    passing = np.array(dataset.percent_passing)
    
    # Check 1: Curve Monotonicity
    diffs = np.diff(passing)
    monotonic_count = np.sum(diffs >= -0.5)  # Allow small negative (rounding)
    monotonicity = monotonic_count / len(diffs) * 100
    
    if monotonicity >= 95:
        monotonicity_rating = "Excellent"
    elif monotonicity >= 85:
        monotonicity_rating = "Good"
    else:
        monotonicity_rating = "Fair"
    
    # Check 2: Data Coverage
    # Look at grain size range relative to typical ranges
    min_size = sizes.min()
    max_size = sizes.max()
    size_range = max_size / min_size
    
    if size_range >= 100:
        coverage_rating = "Excellent"
    elif size_range >= 10:
        coverage_rating = "Good"
    elif size_range >= 2:
        coverage_rating = "Adequate"
    else:
        coverage_rating = "Poor"
    
    # Check 3: Point Density
    num_points = len(sizes)
    
    if num_points >= 30:
        density_rating = "Dense"
    elif num_points >= 15:
        density_rating = "Adequate"
    elif num_points >= 8:
        density_rating = "Sparse"
    else:
        density_rating = "Very Sparse"
    
    # Check 4: Overall Quality
    ratings = [monotonicity_rating, coverage_rating, density_rating]
    rating_scores = {
        "Excellent": 5, "Good": 4, "Adequate": 3, 
        "Fair": 2, "Sparse": 2, "Poor": 1, "Very Sparse": 1, "Dense": 5
    }
    
    avg_score = np.mean([rating_scores.get(r, 3) for r in ratings])
    
    if avg_score >= 4.5:
        overall = ("Excellent", "★★★★★")
    elif avg_score >= 3.5:
        overall = ("Good", "★★★★☆")
    elif avg_score >= 2.5:
        overall = ("Fair", "★★★☆☆")
    else:
        overall = ("Poor", "★★☆☆☆")
    
    return {
        'monotonicity': (monotonicity_rating, monotonicity),
        'coverage': (coverage_rating, size_range),
        'density': (density_rating, num_points),
        'overall': overall,
        'min_size': min_size,
        'max_size': max_size
    }

def _format_data_quality_section(self, dataset: GrainSizeData) -> str:
    """Format data quality assessment as HTML section"""
    
    quality = self._assess_data_quality(dataset)
    
    html = '''
    <div style="page-break-before: auto;">
    <h2>Data Quality Assessment</h2>
    <div class="info-box">
        <h3>Input Data Quality Indicators</h3>
        <table>
            <tr>
                <th>Quality Metric</th>
                <th>Rating</th>
                <th>Details</th>
            </tr>
            <tr>
                <td>Curve Monotonicity</td>
                <td style="font-weight: bold;">{}</td>
                <td style="font-size: 9px;">{:.1f}% of points follow monotonic trend</td>
            </tr>
            <tr>
                <td>Data Coverage</td>
                <td style="font-weight: bold;">{}</td>
                <td style="font-size: 9px;">Grain size range: {:.1f}x (D_max/D_min)</td>
            </tr>
            <tr>
                <td>Point Density</td>
                <td style="font-weight: bold;">{}</td>
                <td style="font-size: 9px;">{} measurement points</td>
            </tr>
            <tr style="background-color: #f0f8ff; font-weight: bold;">
                <td>Overall Quality Rating</td>
                <td colspan="2" style="text-align: center;">{} {}</td>
            </tr>
        </table>
        <p style="font-size: 9px; color: #666; margin-top: 10px;">
            <strong>Interpretation:</strong> Data quality assessment indicates the reliability of the grain size 
            distribution measurement. Higher ratings suggest more confidence in calculated parameters and K-value estimates.
            All ratings should be considered when interpreting results.
        </p>
    </div>
    </div>
    '''.format(
        quality['monotonicity'][0],
        quality['monotonicity'][1],
        quality['coverage'][0],
        quality['coverage'][1],
        quality['density'][0],
        quality['density'][1],
        quality['overall'][0],
        quality['overall'][1]
    )
    
    return html
```

### Usage in generate_grain_size_report
```python
# After methodology section, before results section:
if sections.get('methodology', True):
    html += """<!-- existing methodology -->"""
    # ADD NEW SECTION
    html += self._format_data_quality_section(dataset)

if sections.get('results', True):
    html += """<!-- existing results -->"""
```

---

## 4. METHOD AGREEMENT ANALYSIS

### Method to Add to ReportGenerator

```python
def _format_method_agreement_analysis(self, k_results: List[KCalculationResult]) -> str:
    """
    Analyze how well different methods agree on K-value estimate
    Provides interpretation of variability
    """
    valid_results = [r for r in k_results if r.k_value is not None and r.k_value > 0]
    
    if not valid_results:
        return '<div class="warning-box"><p>No valid K-value calculations for method agreement analysis.</p></div>'
    
    k_values = [r.k_value for r in valid_results]
    mean_k = np.mean(k_values)
    std_k = np.std(k_values)
    min_k = np.min(k_values)
    max_k = np.max(k_values)
    cv = (std_k / mean_k) * 100 if mean_k > 0 else 0
    variability_ratio = max_k / min_k if min_k > 0 else 0
    
    # Interpretation based on variability
    if variability_ratio < 5:
        interpretation = "Excellent agreement"
        agreement_level = "★★★★★"
        description = (
            "Methods show excellent agreement. The narrow range of K-values "
            "suggests high confidence in the estimate. This typically occurs when "
            "the soil has uniform gradation and grain sizes fall within optimal "
            "ranges for multiple methods."
        )
        color = "#e8f5e9"
        border_color = "#4caf50"
    elif variability_ratio < 20:
        interpretation = "Good agreement"
        agreement_level = "★★★★☆"
        description = (
            "Methods show good agreement with reasonable consistency. Slight "
            "variations are expected due to different theoretical assumptions. "
            "The estimate is reliable with typical environmental variations."
        )
        color = "#f1f8e9"
        border_color = "#8bc34a"
    elif variability_ratio < 100:
        interpretation = "Moderate variability"
        agreement_level = "★★★☆☆"
        description = (
            "Methods show moderate variability. Some methods may be outside "
            "their optimal applicability ranges. Consider using median value "
            "and the range as uncertainty bounds. Methods outside the typical "
            "range should be weighted less heavily."
        )
        color = "#fff9e6"
        border_color = "#ffc107"
    else:
        interpretation = "High variability"
        agreement_level = "★★☆☆☆"
        description = (
            "High variability between methods indicates uncertainty. This may "
            "reflect soil properties that don't match typical assumptions, grain "
            "sizes at method boundaries, or mixed soil composition. Recommend "
            "site-specific calibration or field testing to validate estimates."
        )
        color = "#ffebee"
        border_color = "#f44336"
    
    html = f'''
    <h3>Method Agreement Analysis</h3>
    <div style="
        background-color: {color};
        border-left: 4px solid {border_color};
        padding: 15px;
        margin: 15px 0;
        border-radius: 4px;
    ">
        <p style="margin: 0 0 10px 0;">
            <strong>Agreement Level: {interpretation}</strong> {agreement_level}
        </p>
        <p style="margin: 0; font-size: 10pt; line-height: 1.5;">
            {description}
        </p>
    </div>
    
    <table>
        <tr>
            <th>Metric</th>
            <th>Value</th>
            <th>Interpretation</th>
        </tr>
        <tr>
            <td>Variability Ratio (Max/Min)</td>
            <td style="text-align: center; font-weight: bold;">{variability_ratio:.1f}x</td>
            <td style="font-size: 9px;">Range between highest and lowest K estimates</td>
        </tr>
        <tr>
            <td>Coefficient of Variation</td>
            <td style="text-align: center; font-weight: bold;">{cv:.1f}%</td>
            <td style="font-size: 9px;">Relative standard deviation (std/mean × 100)</td>
        </tr>
        <tr>
            <td>Methods Used</td>
            <td style="text-align: center; font-weight: bold;">{len(valid_results)} / {len(k_results)}</td>
            <td style="font-size: 9px;">Valid calculations / Total methods</td>
        </tr>
        <tr style="background-color: #f9f9f9;">
            <td colspan="3" style="font-size: 9px;">
                <strong>Variability Interpretation Thresholds:</strong>
                &lt;5x = Excellent | 5-20x = Good | 20-100x = Moderate | &gt;100x = High
            </td>
        </tr>
    </table>
    '''
    
    return html
```

### Usage in generate_k_value_report
```python
# In generate_k_value_report, in results section:

if sections.get('results', True):
    html += f"""
    <h3>K-Value Calculations by Method</h3>
    <!-- existing method table -->
    
    {self._format_method_agreement_analysis(k_results)}
    
    <h3>Permeability Classification</h3>
    <!-- existing classification -->
    """
```

---

## 5. ENHANCED K-VALUE STATISTICS WITH MEDIAN

### Method to Add to ReportGenerator

```python
def _format_k_value_statistics(self, k_results: List[KCalculationResult]) -> str:
    """
    Format comprehensive K-value statistics including median and standard deviation
    Shows values in multiple units (m/s, cm/s, m/d)
    """
    valid_results = [r for r in k_results if r.k_value is not None and r.k_value > 0]
    
    if not valid_results:
        return ''
    
    k_values = [r.k_value for r in valid_results]
    
    mean_k = np.mean(k_values)
    median_k = np.median(k_values)
    std_k = np.std(k_values)
    min_k = np.min(k_values)
    max_k = np.max(k_values)
    cv = (std_k / mean_k) * 100 if mean_k > 0 else 0
    
    # Unit conversions
    def format_k_values(k_ms):
        return {
            'm/s': f'{k_ms:.2e}',
            'cm/s': f'{k_ms * 100:.3e}',
            'm/d': f'{k_ms * 86400:.1f}'
        }
    
    html = '''
    <h3>Hydraulic Conductivity Statistical Summary</h3>
    <table>
        <tr>
            <th>Statistic</th>
            <th>m/s</th>
            <th>cm/s</th>
            <th>m/day</th>
        </tr>
    '''
    
    for label, k_value in [
        ('Mean K', mean_k),
        ('Median K', median_k),
        ('Standard Deviation', std_k),
        ('Minimum K', min_k),
        ('Maximum K', max_k)
    ]:
        values = format_k_values(k_value)
        
        # Highlight mean and median
        if label in ['Mean K', 'Median K']:
            html += '<tr style="background-color: #ffffcc; font-weight: bold;">'
        else:
            html += '<tr>'
            
        html += f'<td>{label}</td>'
        html += f'<td>{values["m/s"]}</td>'
        html += f'<td>{values["cm/s"]}</td>'
        html += f'<td>{values["m/d"]}</td>'
        html += '</tr>'
    
    html += '''
        <tr style="background-color: #f9f9f9; font-size: 9px;">
            <td colspan="4">
                <strong>Coefficient of Variation:</strong> {:.1f}% 
                (Std Dev / Mean × 100)
            </td>
        </tr>
    </table>
    '''.format(cv)
    
    return html
```

### Usage in generate_k_value_report
```python
# Replace existing statistical summary with new method
if sections.get('results', True):
    html += f"""
    <div style="page-break-before: auto;">
    <h2>Results & Analysis</h2>
    
    {self._format_k_value_statistics(k_results)}
    
    <h3>K-Value Calculations by Method</h3>
    <!-- existing method table -->
    </div>
    """
```

---

## 6. SPECIAL METHOD DIAMETERS SECTION

### Method to Add to ReportGenerator

```python
def _format_special_diameters_section(self, dataset: GrainSizeData) -> str:
    """
    Format special effective diameter calculations used by different methods
    Shows how different methods interpret grain size
    """
    from k_calculations import KCalculator
    
    calculator = KCalculator()
    grain_data = {
        "particle_sizes": list(dataset.particle_sizes),
        "percent_passing": list(dataset.percent_passing),
    }
    
    # Calculate all special diameters
    kruger_de = calculator._kruger_diameter_cm(grain_data)
    harmonic_de = calculator._harmonic_mean_diameter_cm(grain_data)
    zunker_de = calculator._zunker_diameter_cm(grain_data)
    zamarin_de = calculator._zamarin_diameter_cm(grain_data)
    geom_mean = calculator._calculate_geometric_mean(grain_data)
    
    html = '''
    <div style="page-break-before: auto;">
    <h2>Special Method Parameters</h2>
    <div class="info-box">
        <p>Different empirical methods use different effective diameters based on grain size.
        These special diameters represent weighted averages that characterize the grain size
        distribution in ways optimized for each method.</p>
    </div>
    
    <h3>Method-Specific Effective Diameters</h3>
    <table>
        <tr>
            <th>Method</th>
            <th>Effective Diameter</th>
            <th>Calculation Basis</th>
            <th>Physical Meaning</th>
        </tr>
    '''
    
    # Kruger method
    if kruger_de:
        html += f'''
        <tr>
            <td><strong>Kruger</strong></td>
            <td style="text-align: center;">{kruger_de:.4f} cm<br/>({kruger_de*10:.4f} mm)</td>
            <td style="font-size: 9px;">Method-specific weighting of grain sizes</td>
            <td style="font-size: 9px;">Represents typical diameter for Kruger equation</td>
        </tr>
        '''
    
    # Kozeny-Carman (Harmonic mean)
    if harmonic_de:
        html += f'''
        <tr>
            <td><strong>Kozeny-Carman</strong></td>
            <td style="text-align: center;">{harmonic_de:.4f} cm<br/>({harmonic_de*10:.4f} mm)</td>
            <td style="font-size: 9px;">Harmonic mean of grain sizes (1/d_avg)</td>
            <td style="font-size: 9px;">Appropriate for flow through porous media</td>
        </tr>
        '''
    
    # Zunker method
    if zunker_de:
        html += f'''
        <tr>
            <td><strong>Zunker</strong></td>
            <td style="text-align: center;">{zunker_de:.4f} cm<br/>({zunker_de*10:.4f} mm)</td>
            <td style="font-size: 9px;">Zunker-specific grain size weighting</td>
            <td style="font-size: 9px;">Optimized for fine sand and silt</td>
        </tr>
        '''
    
    # Zamarin method
    if zamarin_de:
        html += f'''
        <tr>
            <td><strong>Zamarin</strong></td>
            <td style="text-align: center;">{zamarin_de:.4f} cm<br/>({zamarin_de*10:.4f} mm)</td>
            <td style="font-size: 9px;">Zamarin-specific grain size calculation</td>
            <td style="font-size: 9px;">Considers full distribution</td>
        </tr>
        '''
    
    html += '</table>'
    
    # Geometric mean as reference
    if geom_mean:
        html += f'''
        <h3>Reference Diameters</h3>
        <p><strong>Geometric Mean Diameter:</strong> {geom_mean:.4f} mm</p>
        <p style="font-size: 9px; color: #666;">
            The geometric mean represents the logarithmic center of the distribution
            and is often used as a reference for grain size characterization.
        </p>
        '''
    
    html += '</div>'
    
    return html
```

### Usage in generate_combined_report
```python
# After grain size section, before K-value section:

# Add special diameters explanation
html += self._format_special_diameters_section(dataset)

# Then continue with K-value results...
```

---

## 7. COMPARISON DATASET OVERVIEW TABLE

### Method to Add to ReportGenerator

```python
def _format_comparison_overview_table(self, datasets: List[GrainSizeData]) -> str:
    """
    Create overview table comparing basic properties of all datasets side-by-side
    Mirrors the overview table from comparison_tab.py
    """
    
    overview_params = [
        ("Sample Name", "name"),
        ("Soil Classification", "classification"),
        ("Temperature (°C)", "temperature"),
        ("Porosity", "porosity"),
        ("Data Points", "points")
    ]
    
    html = '<h3>Dataset Overview</h3>'
    html += '<table>'
    html += '<tr><th>Property</th>'
    
    # Headers - dataset names
    for dataset in datasets:
        html += f'<th>{dataset.sample_name}</th>'
    
    html += '</tr>'
    
    # Data rows
    for param_label, param_key in overview_params:
        html += '<tr>'
        html += f'<td style="font-weight: bold;">{param_label}</td>'
        
        for dataset in datasets:
            if param_key == "name":
                value = dataset.sample_name
            elif param_key == "classification":
                value = dataset.classify_soil()
            elif param_key == "temperature":
                value = f"{dataset.temperature:.1f}"
            elif param_key == "porosity":
                porosity = getattr(dataset, 'current_porosity', dataset.porosity)
                value = f"{porosity:.4f}" if porosity else "N/A"
            elif param_key == "points":
                value = str(len(dataset.particle_sizes))
            
            html += f'<td style="text-align: center;">{value}</td>'
        
        html += '</tr>'
    
    html += '</table>'
    return html
```

---

## 8. GRAIN PARAMETER STATISTICS (μ, σ, CV%)

### Method Enhancement - Update existing comparison table

```python
# In generate_comparison_report, enhance the grain comparison table:

def _add_statistics_columns_to_grain_comparison(self, datasets: List[GrainSizeData]) -> str:
    """
    Enhanced grain parameter comparison with statistics columns
    Adds mean, std dev, and coefficient of variation for each parameter
    """
    
    params = [
        ("D10 (mm)", lambda d: d.get_d10()),
        ("D20 (mm)", lambda d: d.get_d20()),
        ("D30 (mm)", lambda d: d.get_d30()),
        ("D50 (mm)", lambda d: d.get_d50()),
        ("D60 (mm)", lambda d: d.get_d60()),
        ("Uniformity Coefficient (Cu)", lambda d: (d.get_d60()/d.get_d10()) if (d.get_d10() and d.get_d60()) else None),
        ("Curvature Coefficient (Cc)", lambda d: ((d.get_d30()**2)/(d.get_d10()*d.get_d60())) if (d.get_d10() and d.get_d30() and d.get_d60()) else None),
    ]
    
    html = '<h3>Grain Size Parameter Comparison with Statistics</h3>'
    html += '<table>'
    html += '<tr><th>Parameter</th>'
    
    for dataset in datasets:
        html += f'<th>{dataset.sample_name}</th>'
    
    html += '<th>μ (Mean)</th><th>σ (Std Dev)</th><th>CV (%)</th></tr>'
    
    for param_label, param_func in params:
        html += '<tr>'
        html += f'<td>{param_label}</td>'
        
        values = []
        
        for dataset in datasets:
            value = param_func(dataset)
            if value is not None:
                values.append(value)
                html += f'<td style="text-align: center;">{value:.3f}</td>'
            else:
                html += '<td style="text-align: center;">N/A</td>'
        
        # Calculate and add statistics
        if len(values) > 1:
            mean_val = np.mean(values)
            std_val = np.std(values)
            cv = (std_val / mean_val * 100) if mean_val > 0 else 0
            
            html += f'<td style="text-align: center; background-color: #f0f0f0;">{mean_val:.3f}</td>'
            html += f'<td style="text-align: center; background-color: #f0f0f0;">{std_val:.3f}</td>'
            html += f'<td style="text-align: center; background-color: #f0f0f0;">{cv:.1f}%</td>'
        else:
            html += '<td colspan="3" style="text-align: center; background-color: #f0f0f0;">-</td>'
        
        html += '</tr>'
    
    html += '</table>'
    return html
```

---

## 9. COMPREHENSIVE STATISTICAL SUMMARY FOR COMPARISONS

### New Method for comparison_report

```python
def _generate_comparison_statistical_summary(self, 
                                            datasets: List[GrainSizeData],
                                            k_results_dict: Dict[str, List[KCalculationResult]]) -> str:
    """
    Generate comprehensive statistical summary text for comparison report
    Consolidates grain size variability, K-value analysis, and trends
    """
    
    analysis = '<div style="page-break-before: auto;">'
    analysis += '<h2>Statistical Comparison Summary</h2>'
    
    # Section 1: Grain Size Variability
    analysis += '<h3>Grain Size Variability Analysis</h3>'
    
    for dataset in datasets:
        d10 = dataset.get_d10()
        d60 = dataset.get_d60()
        
        if d10 and d60:
            cu = d60 / d10
            
            if cu < 4:
                cu_class = "Uniform"
            elif cu < 6:
                cu_class = "Moderately graded"
            else:
                cu_class = "Well-graded"
            
            analysis += f'''
            <p><strong>{dataset.sample_name}:</strong> Cu = {cu:.2f} ({cu_class})<br/>
            <span style="font-size: 9px; color: #666;">
            D₁₀ = {d10:.3f} mm, D₆₀ = {d60:.3f} mm
            </span></p>
            '''
    
    # Section 2: K-Value Comparison
    if k_results_dict:
        analysis += '<h3>Hydraulic Conductivity Comparison</h3>'
        
        all_k_values = {}
        for name, results in k_results_dict.items():
            valid_k = [r.k_value for r in results if r.k_value and r.k_value > 0]
            if valid_k:
                all_k_values[name] = valid_k
        
        if all_k_values:
            # Find extremes
            mean_k_values = {name: np.mean(k_list) for name, k_list in all_k_values.items()}
            highest = max(mean_k_values.items(), key=lambda x: x[1])
            lowest = min(mean_k_values.items(), key=lambda x: x[1])
            
            analysis += f'''
            <ul>
                <li><strong>Highest Permeability:</strong> {highest[0]} with K = {highest[1]:.2e} m/s
                    <span style="font-size: 9px; color: #666;">({self._classify_permeability(highest[1])})</span></li>
                <li><strong>Lowest Permeability:</strong> {lowest[0]} with K = {lowest[1]:.2e} m/s
                    <span style="font-size: 9px; color: #666;">({self._classify_permeability(lowest[1])})</span></li>
                <li><strong>Variability Ratio:</strong> {highest[1]/lowest[1]:.1f}x difference between extremes</li>
            </ul>
            '''
            
            # Statistical overview
            all_values = list(mean_k_values.values())
            mean_all = np.mean(all_values)
            std_all = np.std(all_values)
            
            analysis += f'''
            <p style="margin-top: 15px; padding: 10px; background-color: #f5f5f5; border-radius: 4px;">
            <strong>Statistical Overview:</strong><br/>
            Mean K across all samples: {mean_all:.2e} m/s<br/>
            Standard deviation: {std_all:.2e} m/s<br/>
            Coefficient of variation: {(std_all/mean_all)*100:.1f}%
            </p>
            '''
    
    analysis += '</div>'
    return analysis
```

---

## Integration Guide

These methods should be added to the `ReportGenerator` class in `report_generator.py`. Then they should be called from the appropriate report generation methods:

1. **Grain size reports**: Call in `generate_grain_size_report()`
2. **K-value reports**: Call in `generate_k_value_report()`
3. **Combined reports**: Call in `generate_combined_report()`
4. **Comparison reports**: Call in `generate_comparison_report()`

Each method returns formatted HTML that can be directly inserted into the report sections.

---

## CSS Styling Classes

Add these to `ReportGenerator.report_style` for consistent formatting:

```css
.stat-box {
    background-color: #f0f8ff;
    border-left: 4px solid #0066cc;
    padding: 12px;
    margin: 10px 0;
    border-radius: 4px;
}

.warning-stat-box {
    background-color: #fff9e6;
    border-left: 4px solid #ffc107;
    padding: 12px;
    margin: 10px 0;
    border-radius: 4px;
}

.high-confidence {
    background-color: #e8f5e9;
    border-left: 4px solid #4caf50;
    padding: 12px;
    margin: 10px 0;
    border-radius: 4px;
}

.permeability-very-high {
    background-color: #4caf50;
    color: white;
}

.permeability-high {
    background-color: #8bc34a;
    color: white;
}

.permeability-moderate {
    background-color: #ffc107;
    color: black;
}

.permeability-low {
    background-color: #ff9800;
    color: white;
}

.permeability-very-low {
    background-color: #f44336;
    color: white;
}
```

---

## Testing Checklist

When implementing these additions:

- [ ] Test with single-sample grain size report
- [ ] Test with single-sample K-value report
- [ ] Test with combined report
- [ ] Test with multi-sample comparison report
- [ ] Verify all calculations match UI display
- [ ] Check HTML rendering in preview
- [ ] Test PDF export with new sections
- [ ] Verify page breaks are appropriate
- [ ] Check table formatting on different screen sizes
- [ ] Validate color-coding is semantically correct

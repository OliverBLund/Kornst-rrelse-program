# Complete Overview of Calculated Values

## 📊 All Values That Need to Be Displayed/Tracked

---

## 1️⃣ **GRAIN SIZE PERCENTILES** (from interpolation)

### **Standard Percentiles** (All calculated via linear interpolation)
Used in various K-calculation methods:

| Percentile | Used By Methods | Display Priority |
|------------|----------------|------------------|
| **D5**     | Barr, Krumbein-Monk | Medium |
| **D10** ⭐ | Hazen, Hazen_1892, Slichter, Terzaghi, Beyer, Kozeny-Carman, Zunker, Zamarin, Barr, Alyamani-Sen, Chapuis | **HIGH** (Most critical) |
| D15        | (Interpolation reference) | Low |
| **D16**    | Krumbein-Monk | Medium |
| **D17**    | Sauerbrei | Medium |
| **D20** ⭐ | USBR, Beyer (fallback) | High |
| D25        | (Common geotechnical reference) | Medium |
| **D30** ⭐ | Coefficient of Curvature (Cc) | **HIGH** |
| D40        | (Common geotechnical reference) | Low |
| **D50** ⭐ | Kruger, Alyamani-Sen, Shepherd, Krumbein-Monk | **HIGH** (Median) |
| **D60** ⭐ | Beyer, Barr, Uniformity Coefficient (Cu) | **HIGH** |
| D70        | (Common geotechnical reference) | Low |
| D75        | (Common geotechnical reference) | Low |
| D80        | (Common geotechnical reference) | Low |
| **D84**    | Krumbein-Monk | Medium |
| D85        | (Common geotechnical reference) | Low |
| D90        | (Common geotechnical reference) | Medium |
| **D95**    | Krumbein-Monk | Medium |

⭐ = **Critical values** - used by multiple methods or key parameters

---

## 2️⃣ **GRADATION PARAMETERS** (derived from percentiles)

### **Primary Parameters:**
```
Uniformity Coefficient (Cu) = D60 / D10
├─ Classification: Uniform (Cu < 4), Moderate (4-6), Well-graded (Cu > 6)
└─ Units: Dimensionless

Coefficient of Curvature (Cc) = D30² / (D10 × D60)
├─ Well-graded range: 1 ≤ Cc ≤ 3
└─ Units: Dimensionless
```

### **Statistical Parameters:**
```
Span Ratio = D95 / D5  (or Dmax / Dmin)
├─ Indicates breadth of grain size distribution
└─ Units: Dimensionless

Sorting Coefficient (σ) = √(D84 / D16)  [Folk & Ward method]
├─ Or: σ = (D84 - D16)/4 + (D95 - D5)/6.6  [Phi-based]
├─ Classification: Well sorted (σ < 2), Moderately sorted (2-4), Poorly sorted (σ > 4)
└─ Units: Dimensionless or phi units
```

### **Special Calculated Diameters:**
```
Geometric Mean Diameter (dgeom)
├─ Used by: Urumovic porosity, Krumbein-Monk method
├─ Formula: exp((1/Mtot) × Σ(mr(i+1) × ln(√(ps(i) × ps(i+1)))))
└─ Units: mm

Harmonic Mean Diameter (de_harmonic)
├─ Used by: Kozeny-Carman method
├─ Formula: 1 / Σ(mass_fraction × (ps(i) + ps(i+1))/(2 × ps(i) × ps(i+1)))
└─ Units: cm (converted from mm)

Special Method Diameters:
├─ Zunker diameter (special weighted calculation)
├─ Zamarin diameter (special weighted calculation)
└─ Kruger diameter (special harmonic mean variant)
```

---

## 3️⃣ **POROSITY VALUES**

```
Calculated Porosity (from grain size data)
├─ Simple Method: Based on Cu
├─ Urumovic Method: Uses geometric mean diameter and Cu
└─ Units: 0-1 (dimensionless)

Current Porosity (user-editable)
├─ Starts as calculated value
├─ Can be manually overridden
└─ Used in all K-calculations

Porosity Modification Status
├─ [Calculated] - Using auto-calculated value
├─ [Modified] - User has changed it
└─ [Manual] - No calculated value available
```

---

## 4️⃣ **ENVIRONMENTAL PARAMETERS**

```
Temperature
├─ Default: 20°C
├─ Used for viscosity/density corrections
└─ Affects all K-value calculations

Water Viscosity (calculated from temperature)
├─ Formula: Vuković & Soro (1992) polynomial
└─ Units: g/(cm·s)

Water Density (calculated from temperature)
├─ Formula: Vuković & Soro (1992) polynomial
└─ Units: g/cm³
```

---

## 5️⃣ **K-VALUE STATISTICS** (from calculation results)

### **Basic Statistics:**
```
Mean K-value
├─ Average of all valid K calculations
└─ Units: m/s

Median K-value
├─ Middle value of sorted K results
└─ Units: m/s

Standard Deviation
├─ Spread of K-values
└─ Units: m/s

Coefficient of Variation (CV)
├─ CV = (Std Dev / Mean) × 100%
└─ Units: %
```

### **Range Statistics:**
```
Min K-value
├─ Lowest K from all methods
├─ Include: Method name that produced it
└─ Units: m/s

Max K-value
├─ Highest K from all methods
├─ Include: Method name that produced it
└─ Units: m/s

Range Ratio
├─ Max K / Min K
└─ Units: Dimensionless (shows variability)
```

### **Quartile Statistics:**
```
Q1 (25th percentile)
Q2 (50th percentile = Median)
Q3 (75th percentile)
IQR (Interquartile Range) = Q3 - Q1
```

### **Method Counts:**
```
Total Methods Attempted: 16
Valid Methods: X (produced K-value > 0)
├─ OK: X (no warnings)
├─ Warning: X (applicability concerns)
└─ Error: X (failed to calculate)
```

---

## 6️⃣ **METHOD AGREEMENT ANALYSIS**

### **Clustering:**
```
Core Cluster Methods (within ±25% of median)
├─ List of method names
├─ Core cluster mean K
├─ Core cluster std dev
└─ Recommended as most reliable

Outlier Methods (>50% from median)
├─ High outliers: Method name, K-value, % deviation
├─ Low outliers: Method name, K-value, % deviation
└─ Reason for deviation (applicability range, etc.)

Failed Methods
├─ Method name
├─ Reason for failure (missing data, out of range, etc.)
└─ Required parameters
```

### **Recommended Range:**
```
Recommended K-value Range
├─ Based on core cluster mean ± std dev
├─ Example: 2.1e-4 m/s ± 30% → (1.5e-4 to 2.7e-4 m/s)
└─ Confidence level: High/Moderate/Low
```

---

## 7️⃣ **DATA QUALITY METRICS**

### **Curve Quality:**
```
Monotonicity Score
├─ 0-1, where 1 = perfectly monotonic percent passing curve
├─ Checks for reversals in data
└─ Rating: Excellent/Good/Fair/Poor

Data Coverage
├─ Percent passing range covered (e.g., 0-100%, 5-95%)
├─ Checks if D5 through D95 can be calculated
└─ Rating: Excellent (0-100%), Good (5-95%), Fair, Poor
```

### **Point Distribution:**
```
Point Density
├─ Number of sieve data points
├─ Check: Adequate spacing (no gaps > 2x average)
└─ Count: X points

Interpolation Quality
├─ Based on point spacing
├─ Large gaps reduce accuracy
└─ Rating: Excellent/Good/Fair/Poor
```

### **Validation Status:**
```
Data Errors
├─ Non-monotonic data
├─ Out-of-range values
├─ Missing critical data
└─ Count: X errors

Data Warnings
├─ Sparse data points
├─ Limited range coverage
├─ Unusual Cu/Cc values
└─ Count: X warnings

Overall Quality Rating
├─ ★★★★★ Excellent (no issues)
├─ ★★★★☆ Good (minor warnings)
├─ ★★★☆☆ Fair (several warnings)
├─ ★★☆☆☆ Poor (errors present)
└─ ★☆☆☆☆ Critical (unusable)
```

---

## 8️⃣ **SOIL CLASSIFICATION**

### **USCS Classification:**
```
Primary Classification
├─ Examples: SP, SW, SM, SC, ML, CL, etc.
└─ Based on grain size distribution and gradation

Secondary Classification (if applicable)
├─ Examples: SP-SM, SW-SC
└─ Borderline cases

Full Name
├─ "Poorly Graded Sand"
├─ "Well-graded Sand with Silt"
└─ Human-readable description
```

### **Classification Criteria Met:**
```
☑ >50% retained on No. 200 sieve
☑ >50% of coarse passes No. 4 sieve
☑ Cu < 6 or Cc outside 1-3
☐ Plasticity index criteria
```

### **Typical Engineering Properties:**
```
Angle of Internal Friction: X-Y degrees
Unit Weight Range: X-Y kN/m³
Compressibility: Low/Medium/High
Shear Strength: Low/Medium/High
Drainage Characteristics: Poor/Fair/Good/Excellent
```

---

## 9️⃣ **PERMEABILITY CLASSIFICATION**

### **Classification Scale:**
```
Based on Mean K-value:
├─ K > 10⁻² m/s:     Very High Permeability (Clean Gravel)
├─ 10⁻⁴ < K ≤ 10⁻²:  High Permeability (Clean Sand)
├─ 10⁻⁵ < K ≤ 10⁻⁴:  Moderate Permeability (Fine Sand)
├─ 10⁻⁷ < K ≤ 10⁻⁵:  Low Permeability (Silt)
├─ 10⁻⁹ < K ≤ 10⁻⁷:  Very Low Permeability (Clay-Silt)
└─ K ≤ 10⁻⁹:         Practically Impermeable (Clay)
```

### **Engineering Implications:**
```
Drainage Quality
Typical Applications
Foundation Suitability
Barrier/Filter Potential
```

---

## 🔟 **RAW DATA INFORMATION**

### **Dataset Metadata:**
```
Sample Name
File Name/Path
Data Points Count
Date Loaded
Date Last Calculated
```

### **Sieve Data:**
```
Particle Sizes Array (mm)
Percent Passing Array (%)
├─ Min size: X mm
├─ Max size: Y mm
└─ Span: Y/X ratio
```

---

## 📍 **WHERE TO DISPLAY EACH VALUE:**

### **Results Tab - Input Parameters Section:** (NEW)
```
✓ D5, D10, D17, D20, D30, D50, D60, D84, D95
✓ Cu, Cc
✓ Temperature, Porosity (calculated + current)
✓ Geometric mean (if needed by methods)
```

### **Stats Tab - Percentile Table:**
```
✓ All D5-D95 (every 5th percentile)
✓ Visual bars showing relative sizes
✓ Highlight key percentiles (D10, D20, D30, D50, D60)
```

### **Stats Tab - Gradation Analysis:**
```
✓ Cu, Cc (with formulas)
✓ Classifications (uniform/moderate/well-graded)
✓ Sorting coefficient
✓ Span ratio
```

### **Stats Tab - K-Statistics Widget:**
```
✓ All K-value statistics (mean, median, std, quartiles, etc.)
✓ Method agreement analysis
✓ Core cluster identification
✓ Outlier analysis
✓ Recommended K-value range
```

### **Stats Tab - Data Quality:**
```
✓ Monotonicity score
✓ Coverage quality
✓ Point density
✓ Interpolation quality
✓ Overall rating (stars)
✓ Warnings/errors list
```

### **Stats Tab - Soil Classification:**
```
✓ USCS primary/secondary
✓ Full name
✓ Criteria checklist
✓ Typical properties
```

### **Stats Tab - Compact Info Bar:**
```
✓ Sample name
✓ D50
✓ Cu
✓ Mean K
✓ Soil type
```

---

## 🎯 **PRIORITY LEVELS FOR IMPLEMENTATION:**

### **Phase 2A - Critical (Implement First):**
- ✅ D10, D20, D30, D50, D60 (already exist)
- 🆕 D5, D17 (needed by methods)
- 🆕 Cu, Cc calculations
- 🆕 Basic K-statistics (mean, median, std, min, max)
- 🆕 Method counts (total, ok, warning, error)

### **Phase 2B - High Priority:**
- 🆕 D16, D84, D95 (Krumbein-Monk)
- 🆕 All standard percentiles D5-D95
- 🆕 Quartiles for K-values
- 🆕 Method agreement clustering
- 🆕 Basic data quality (monotonicity, coverage)

### **Phase 2C - Medium Priority:**
- 🆕 Sorting coefficient
- 🆕 Span ratio
- 🆕 Geometric/harmonic means
- 🆕 Enhanced soil classification
- 🆕 Permeability classification

### **Phase 2D - Nice to Have:**
- 🆕 Detailed engineering properties
- 🆕 Advanced quality metrics
- 🆕 Gap detection
- 🆕 Historical tracking

---

## 📝 **NOTES:**

1. **Interpolation Method**: Use `k_calculations_v2.py`'s `_interpolate_percentile()` for ALL percentiles to ensure consistency
2. **Units**: Keep consistent - mm for grain sizes, m/s for K-values
3. **Temperature Correction**: All K-values already temperature-corrected by k_calculator
4. **Validation**: Use existing validation_messages from GrainSizeData
5. **Method Names**: Keep exactly as in k_calculations_v2.py for traceability

---

**Document Status**: Complete overview for Phase 2 implementation
**Last Updated**: 2025-10-14
**Next Step**: Begin Phase 2A implementation

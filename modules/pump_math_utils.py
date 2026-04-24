"""
Pump Curve Solver - Mathematical Utilities for Pump Selection
Supports TWO modes for pump curves:

MODE 1: BEP-Based Estimation (Default)
- Uses polynomial head curve: H = a + bQ + cQ²
- Efficiency estimated from BEP parameters
- Good for preliminary design and comparison

MODE 2: Digitized Manufacturer Data (Accurate)
- Uses actual data points from manufacturer curves
- Linear/spline interpolation between points
- Accurate for final pump specification

Power Calculation:
- P_kW = (Q × H) / (367 × η)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
import json
import os

# Try to import scipy for advanced interpolation
try:
    from scipy import interpolate as scipy_interpolate
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    scipy_interpolate = None


@dataclass
class PumpCurveCoefficients:
    """Polynomial coefficients for pump head curve (Mode 1)"""
    # Head curve: H = a + b*Q + c*Q²
    head_a: float
    head_b: float
    head_c: float


@dataclass 
class DigitizedCurveData:
    """Digitized pump curve data points from manufacturer (Mode 2)"""
    # H-Q curve points
    flow_points: List[float] = field(default_factory=list)  # Q values (m³/h)
    head_points: List[float] = field(default_factory=list)  # H values (m)
    
    # Efficiency curve points (along the H-Q curve)
    eff_flow_points: List[float] = field(default_factory=list)  # Q values for efficiency
    eff_points: List[float] = field(default_factory=list)       # η values (%)
    
    # Optional: Power curve points
    power_flow_points: List[float] = field(default_factory=list)
    power_points: List[float] = field(default_factory=list)     # P values (kW)
    
    # Metadata
    impeller_diameter_mm: float = 0
    source: str = ""  # e.g., "Manufacturer catalog digitized"
    
    def is_valid(self) -> bool:
        """Check if we have enough data points for interpolation"""
        return (len(self.flow_points) >= 3 and 
                len(self.head_points) >= 3 and
                len(self.flow_points) == len(self.head_points))
    
    def has_efficiency_data(self) -> bool:
        """Check if efficiency data is available"""
        return (len(self.eff_flow_points) >= 3 and 
                len(self.eff_points) >= 3 and
                len(self.eff_flow_points) == len(self.eff_points))


@dataclass
class BEPParameters:
    """Best Efficiency Point parameters for estimation mode"""
    q_bep: float          # Flow at BEP (m³/h)
    eff_bep: float        # Peak efficiency at BEP (%)
    shape_factor: float   # How quickly efficiency drops from BEP (0.3-0.5 typical)


@dataclass
class PumpLimits:
    """Operating limits for a pump"""
    min_flow_m3h: float
    max_flow_m3h: float
    max_head_m: float


@dataclass
class DutyPoint:
    """Calculated duty point (intersection of pump and system curves)"""
    flow_m3h: float
    head_m: float
    efficiency_percent: float
    power_kw: float
    is_valid: bool
    message: str = ""


@dataclass
class PumpMatch:
    """Result of pump suitability analysis"""
    pump_id: str
    brand: str
    model: str
    description: str
    image_url: str
    catalog_link: str
    rpm: int
    impeller_diameter_mm: str
    
    # Calculated values at required flow
    head_at_required_flow: float
    efficiency_at_required_flow: float
    power_at_required_flow: float
    
    # Duty point (actual operating point)
    duty_point: DutyPoint
    
    # Match analysis
    is_suitable: bool
    head_margin_percent: float
    efficiency_rating: str  # "Excellent", "Standard", "Low"
    match_score: float


class PumpCurveSolver:
    """
    Mathematical engine for pump curve calculations.
    
    Supports TWO MODES:
    
    MODE 1 - BEP Estimation (Default):
    - Uses polynomial for H-Q curve
    - Estimates efficiency from BEP parameters
    - Good for preliminary design
    
    MODE 2 - Digitized Data (Accurate):
    - Uses actual manufacturer data points
    - Interpolates between points
    - Accurate for final specification
    """
    
    # Metric constant for power calculation (water, SG=1.0)
    POWER_CONSTANT = 367.0
    
    # Head tolerance for pump suitability (+0% to +15%)
    HEAD_TOLERANCE_MIN = 0.0
    HEAD_TOLERANCE_MAX = 0.15
    
    # Default shape factor for efficiency curve
    DEFAULT_SHAPE_FACTOR = 0.35
    
    def __init__(self, pump_data: dict):
        """
        Initialize solver with pump data from database.
        
        Automatically detects mode based on available data:
        - If 'digitized' data present → Mode 2 (accurate)
        - Otherwise → Mode 1 (BEP estimation)
        
        Args:
            pump_data: Dictionary containing pump specifications
        """
        self.pump_id = pump_data.get('id', '')
        self.brand = pump_data.get('brand', '')
        self.model = pump_data.get('model', '')
        self.description = pump_data.get('description', '')
        self.rpm = pump_data.get('rpm', 0)
        self.impeller_diameter_mm = str(pump_data.get('impeller_diameter_mm', 'N/A'))
        self.image_url = pump_data.get('image', '')
        self.catalog_link = pump_data.get('catalog_link', '')
        
        # Extract curves section
        curves = pump_data.get('curves', {})
        
        # Check for digitized data (Mode 2)
        digitized_data = curves.get('digitized', {})
        if digitized_data and self._has_valid_digitized_data(digitized_data):
            self.mode = "digitized"
            self.digitized = self._load_digitized_data(digitized_data)
            self._setup_interpolators()
        else:
            self.mode = "bep_estimation"
            self.digitized = None
        
        # Extract head curve coefficients (used in Mode 1, or as fallback)
        head_coeffs = curves.get('head', {})
        self.coefficients = PumpCurveCoefficients(
            head_a=head_coeffs.get('a', 0),
            head_b=head_coeffs.get('b', 0),
            head_c=head_coeffs.get('c', 0)
        )
        
        # Extract limits
        limits = pump_data.get('limits', {})
        self.limits = PumpLimits(
            min_flow_m3h=limits.get('min_flow_m3h', 0),
            max_flow_m3h=limits.get('max_flow_m3h', 100),
            max_head_m=limits.get('max_head_m', 50)
        )
        
        # Extract or calculate BEP parameters
        self.bep = self._extract_bep_parameters(pump_data)
    
    def _has_valid_digitized_data(self, digitized_data: dict) -> bool:
        """Check if digitized data has enough points"""
        flow_pts = digitized_data.get('flow_points', [])
        head_pts = digitized_data.get('head_points', [])
        return len(flow_pts) >= 3 and len(head_pts) >= 3
    
    def _load_digitized_data(self, data: dict) -> DigitizedCurveData:
        """Load digitized curve data from dictionary"""
        return DigitizedCurveData(
            flow_points=data.get('flow_points', []),
            head_points=data.get('head_points', []),
            eff_flow_points=data.get('eff_flow_points', []),
            eff_points=data.get('eff_points', []),
            power_flow_points=data.get('power_flow_points', []),
            power_points=data.get('power_points', []),
            impeller_diameter_mm=data.get('impeller_diameter_mm', 0),
            source=data.get('source', 'Digitized from manufacturer curve')
        )
    
    def _setup_interpolators(self):
        """Setup interpolation functions for digitized data"""
        if self.digitized and self.digitized.is_valid():
            if SCIPY_AVAILABLE:
                # Use scipy cubic interpolation (more accurate)
                self._head_interp = scipy_interpolate.interp1d(
                    self.digitized.flow_points,
                    self.digitized.head_points,
                    kind='cubic',
                    fill_value='extrapolate'
                )
                
                # Efficiency interpolator (if available)
                if self.digitized.has_efficiency_data():
                    self._eff_interp = scipy_interpolate.interp1d(
                        self.digitized.eff_flow_points,
                        self.digitized.eff_points,
                        kind='cubic',
                        fill_value='extrapolate'
                    )
                else:
                    self._eff_interp = None
            else:
                # Fallback to numpy linear interpolation
                self._head_interp = lambda q: np.interp(
                    q, self.digitized.flow_points, self.digitized.head_points
                )
                if self.digitized.has_efficiency_data():
                    self._eff_interp = lambda q: np.interp(
                        q, self.digitized.eff_flow_points, self.digitized.eff_points
                    )
                else:
                    self._eff_interp = None
        else:
            self._head_interp = None
            self._eff_interp = None
    
    def get_data_source(self) -> str:
        """Return description of data source for transparency"""
        if self.mode == "digitized":
            source = self.digitized.source if self.digitized else "Digitized data"
            return f"📊 Manufacturer Data: {source}"
        else:
            return "📐 BEP Estimation Model"
    
    def _extract_bep_parameters(self, pump_data: dict) -> BEPParameters:
        """
        Extract BEP parameters from pump data.
        
        Priority:
        1. Direct BEP specification (q_bep, eff_bep)
        2. Estimate from pump characteristics using industry correlations
        
        Args:
            pump_data: Pump specification dictionary
            
        Returns:
            BEPParameters dataclass
        """
        curves = pump_data.get('curves', {})
        bep_data = curves.get('bep', {})
        
        # Check for direct BEP specification
        if bep_data and 'q_bep' in bep_data:
            return BEPParameters(
                q_bep=bep_data.get('q_bep'),
                eff_bep=bep_data.get('eff_bep', 78),
                shape_factor=bep_data.get('shape_factor', self.DEFAULT_SHAPE_FACTOR)
            )
        
        # Estimate BEP from pump characteristics
        return self._estimate_bep_from_characteristics(pump_data)
    
    def _estimate_bep_from_characteristics(self, pump_data: dict) -> BEPParameters:
        """
        Estimate BEP parameters using industry correlations.
        
        Based on:
        - Pump specific speed (Ns) correlations
        - Typical BEP occurs at 65-80% of max flow
        - Peak efficiency related to pump size and type
        
        Args:
            pump_data: Pump specification dictionary
            
        Returns:
            Estimated BEPParameters
        """
        limits = pump_data.get('limits', {})
        max_flow = limits.get('max_flow_m3h', 100)
        min_flow = limits.get('min_flow_m3h', 0)
        max_head = limits.get('max_head_m', 50)
        rpm = pump_data.get('rpm', 1750)
        
        # Estimate Q_bep: typically 65-75% of max flow for centrifugal pumps
        # Larger pumps tend to have BEP closer to 70% of max flow
        q_bep_ratio = 0.70 if max_flow > 200 else 0.65
        q_bep = max_flow * q_bep_ratio
        
        # Ensure Q_bep is above minimum flow
        q_bep = max(q_bep, min_flow * 1.2)
        
        # Calculate specific speed (Ns) - dimensionless indicator of pump geometry
        # Ns = N × √Q / H^0.75 (using Q in m³/h, H in m, N in rpm)
        # Higher Ns = more axial-flow characteristics, lower Ns = more radial
        h_at_bep = self.calculate_head(q_bep)
        if h_at_bep > 0:
            ns = rpm * np.sqrt(q_bep) / (h_at_bep ** 0.75)
        else:
            ns = 50  # Default for low-head pumps
        
        # Estimate peak efficiency based on:
        # 1. Flow rate (larger pumps are more efficient)
        # 2. Specific speed (optimal Ns range gives best efficiency)
        # 3. Pump type implied by description
        
        description = pump_data.get('description', '').lower()
        
        # Base efficiency from flow rate (larger = more efficient)
        if max_flow >= 500:
            base_eff = 82
        elif max_flow >= 300:
            base_eff = 80
        elif max_flow >= 150:
            base_eff = 78
        elif max_flow >= 50:
            base_eff = 75
        else:
            base_eff = 70
        
        # Adjust for pump type
        if 'submersible' in description or 'borehole' in description:
            base_eff -= 2  # Submersibles slightly less efficient
        elif 'turbine' in description:
            base_eff -= 1  # Vertical turbines slightly less efficient
        elif 'split case' in description or 'split-case' in description:
            base_eff += 2  # Split case pumps very efficient
        elif 'multistage' in description:
            base_eff -= 3  # Multistage have more losses
        
        # Adjust for specific speed (optimal Ns ≈ 40-80)
        if 30 <= ns <= 100:
            base_eff += 1  # Optimal specific speed range
        elif ns < 20 or ns > 150:
            base_eff -= 2  # Outside optimal range
        
        # Clamp to realistic range
        eff_bep = max(65, min(86, base_eff))
        
        # Shape factor: how quickly efficiency drops from BEP
        # Larger, well-designed pumps have flatter curves (lower shape factor)
        if max_flow >= 300:
            shape_factor = 0.30
        elif max_flow >= 100:
            shape_factor = 0.35
        else:
            shape_factor = 0.40
        
        return BEPParameters(
            q_bep=q_bep,
            eff_bep=eff_bep,
            shape_factor=shape_factor
        )
    
    def calculate_head(self, flow_m3h: float) -> float:
        """
        Calculate pump head at given flow rate.
        
        MODE 1 (BEP Estimation): Uses polynomial H = a + bQ + cQ²
        MODE 2 (Digitized): Interpolates from manufacturer data points
        
        Args:
            flow_m3h: Flow rate in m³/h
            
        Returns:
            Head in meters
        """
        # MODE 2: Use digitized data if available
        if self.mode == "digitized" and hasattr(self, '_head_interp') and self._head_interp is not None:
            try:
                head = float(self._head_interp(flow_m3h))
                return max(0, head)
            except:
                pass  # Fall back to polynomial
        
        # MODE 1: Polynomial calculation
        a = self.coefficients.head_a
        b = self.coefficients.head_b
        c = self.coefficients.head_c
        
        head = a + (b * flow_m3h) + (c * flow_m3h ** 2)
        return max(0, head)  # Head cannot be negative
    
    def calculate_efficiency(self, flow_m3h: float) -> float:
        """
        Calculate pump efficiency at given flow rate.
        
        MODE 1 (BEP Estimation): Uses BEP-based parabolic model
        MODE 2 (Digitized): Interpolates from manufacturer data points
        
        Args:
            flow_m3h: Flow rate in m³/h
            
        Returns:
            Efficiency as percentage (0-100)
        """
        if flow_m3h <= 0:
            return 5.0  # Minimum efficiency at zero flow
        
        # MODE 2: Use digitized efficiency data if available
        if (self.mode == "digitized" and 
            hasattr(self, '_eff_interp') and 
            self._eff_interp is not None):
            try:
                efficiency = float(self._eff_interp(flow_m3h))
                return max(5.0, min(95.0, efficiency))
            except:
                pass  # Fall back to BEP estimation
        
        # MODE 1: BEP-based estimation
        q_bep = self.bep.q_bep
        eff_bep = self.bep.eff_bep
        k = self.bep.shape_factor
        
        # Normalized deviation from BEP
        deviation = (flow_m3h - q_bep) / q_bep
        
        # Parabolic efficiency curve centered at BEP
        efficiency = eff_bep * (1 - k * deviation ** 2)
        
        # Additional derating for extreme deviations (outside normal operating range)
        if abs(deviation) > 0.5:
            # Extra penalty for operating far from BEP
            extra_deviation = abs(deviation) - 0.5
            efficiency *= (1 - 0.3 * extra_deviation)
        
        # Clamp to realistic range (5% min, eff_bep max)
        return max(5.0, min(eff_bep, efficiency))
    
    def calculate_power(self, flow_m3h: float, head_m: float, efficiency_percent: float) -> float:
        """
        Calculate motor power required in kilowatts.
        
        Formula: Power_kW = (Q × H) / (367 × Eff)
        
        Where:
        - Q = Flow rate (m³/h)
        - H = Head (m)
        - Eff = Efficiency as decimal (0-1)
        - 367 = Metric constant for water (SG=1.0)
        
        Args:
            flow_m3h: Flow rate in m³/h
            head_m: Head in meters
            efficiency_percent: Efficiency as percentage
            
        Returns:
            Power in kilowatts
        """
        if efficiency_percent <= 0:
            return 0
        
        eff_decimal = efficiency_percent / 100.0
        power_kw = (flow_m3h * head_m) / (self.POWER_CONSTANT * eff_decimal)
        return power_kw
    
    def generate_pump_curve_points(self, num_points: int = 25) -> Tuple[List[float], List[float], List[float]]:
        """
        Generate points for plotting the pump performance curve.
        
        Args:
            num_points: Number of points to generate
            
        Returns:
            Tuple of (flows, heads, efficiencies)
        """
        flows = np.linspace(0, self.limits.max_flow_m3h, num_points)
        heads = [self.calculate_head(q) for q in flows]
        efficiencies = [self.calculate_efficiency(q) for q in flows]
        
        return list(flows), heads, efficiencies
    
    def generate_system_curve_points(
        self, 
        static_head_m: float, 
        friction_k: float, 
        max_flow_m3h: float,
        num_points: int = 25
    ) -> Tuple[List[float], List[float]]:
        """
        Generate points for the system curve.
        
        Formula: H_sys = H_static + k × Q^1.852 (Hazen-Williams)
        
        Args:
            static_head_m: Static head component (elevation + pressure)
            friction_k: Friction coefficient
            max_flow_m3h: Maximum flow for curve generation
            num_points: Number of points
            
        Returns:
            Tuple of (flows, heads)
        """
        flows = np.linspace(0, max_flow_m3h, num_points)
        heads = [static_head_m + friction_k * (q ** 1.852) for q in flows]
        
        return list(flows), heads
    
    def calculate_system_curve_k(self, required_head_m: float, required_flow_m3h: float, static_ratio: float = 0.4) -> float:
        """
        Calculate the friction coefficient k for the system curve.
        
        Args:
            required_head_m: Total required head at design flow
            required_flow_m3h: Design flow rate
            static_ratio: Ratio of static head to total head (default 40%)
            
        Returns:
            Friction coefficient k
        """
        static_head = required_head_m * static_ratio
        friction_head = required_head_m - static_head
        
        if required_flow_m3h <= 0:
            return 0
        
        # k = friction_head / Q^1.852
        k = friction_head / (required_flow_m3h ** 1.852)
        return k
    
    def find_duty_point(
        self,
        static_head_m: float,
        friction_k: float,
        tolerance: float = 0.5
    ) -> DutyPoint:
        """
        Find the duty point - intersection of pump curve and system curve.
        
        Uses numerical method to find where H_pump(Q) = H_sys(Q)
        
        Args:
            static_head_m: Static head component
            friction_k: System curve friction coefficient
            tolerance: Tolerance for convergence (m)
            
        Returns:
            DutyPoint with calculated values
        """
        # Search for intersection within pump operating range
        min_q = self.limits.min_flow_m3h
        max_q = self.limits.max_flow_m3h
        
        # Use binary search / Newton-Raphson hybrid
        for _ in range(100):  # Max iterations
            mid_q = (min_q + max_q) / 2
            
            h_pump = self.calculate_head(mid_q)
            h_sys = static_head_m + friction_k * (mid_q ** 1.852)
            
            diff = h_pump - h_sys
            
            if abs(diff) < tolerance:
                # Found intersection
                eff = self.calculate_efficiency(mid_q)
                power = self.calculate_power(mid_q, h_pump, eff)
                
                return DutyPoint(
                    flow_m3h=mid_q,
                    head_m=h_pump,
                    efficiency_percent=eff,
                    power_kw=power,
                    is_valid=True,
                    message="Duty point found successfully"
                )
            
            if diff > 0:
                # Pump curve above system curve, increase flow
                min_q = mid_q
            else:
                # Pump curve below system curve, decrease flow
                max_q = mid_q
        
        # No intersection found
        return DutyPoint(
            flow_m3h=0,
            head_m=0,
            efficiency_percent=0,
            power_kw=0,
            is_valid=False,
            message="No intersection found - pump may not be suitable"
        )
    
    def check_suitability(
        self,
        required_flow_m3h: float,
        required_head_m: float
    ) -> PumpMatch:
        """
        Check if pump is suitable for the given requirements.
        
        Criteria:
        - Flow within pump operating range
        - Head at required flow >= required head (within +0% to +15% tolerance)
        
        Args:
            required_flow_m3h: Required flow rate
            required_head_m: Required head
            
        Returns:
            PumpMatch with full analysis
        """
        # Check flow is within range
        flow_in_range = (self.limits.min_flow_m3h <= required_flow_m3h <= self.limits.max_flow_m3h)
        
        # Calculate head at required flow
        head_at_flow = self.calculate_head(required_flow_m3h)
        eff_at_flow = self.calculate_efficiency(required_flow_m3h)
        power_at_flow = self.calculate_power(required_flow_m3h, head_at_flow, eff_at_flow)
        
        # Calculate head margin
        if required_head_m > 0:
            head_margin = (head_at_flow - required_head_m) / required_head_m
        else:
            head_margin = 1.0
        
        # Check suitability (head margin between 0% and +15%)
        is_suitable = (
            flow_in_range and
            head_margin >= self.HEAD_TOLERANCE_MIN and
            head_margin <= self.HEAD_TOLERANCE_MAX
        )
        
        # Calculate duty point
        static_ratio = 0.4  # Assume 40% static head
        static_head = required_head_m * static_ratio
        friction_k = self.calculate_system_curve_k(required_head_m, required_flow_m3h, static_ratio)
        duty_point = self.find_duty_point(static_head, friction_k)
        
        # Efficiency rating
        if eff_at_flow > 75:
            eff_rating = "Excellent"
        elif eff_at_flow >= 60:
            eff_rating = "Standard"
        else:
            eff_rating = "Low"
        
        # Calculate match score (0-100)
        match_score = self._calculate_match_score(
            required_flow_m3h, required_head_m,
            head_at_flow, eff_at_flow, head_margin
        )
        
        return PumpMatch(
            pump_id=self.pump_id,
            brand=self.brand,
            model=self.model,
            description=self.description,
            image_url=self.image_url,
            catalog_link=self.catalog_link,
            rpm=self.rpm,
            impeller_diameter_mm=self.impeller_diameter_mm,
            head_at_required_flow=head_at_flow,
            efficiency_at_required_flow=eff_at_flow,
            power_at_required_flow=power_at_flow,
            duty_point=duty_point,
            is_suitable=is_suitable,
            head_margin_percent=head_margin * 100,
            efficiency_rating=eff_rating,
            match_score=match_score
        )
    
    def _calculate_match_score(
        self,
        required_flow: float,
        required_head: float,
        actual_head: float,
        efficiency: float,
        head_margin: float
    ) -> float:
        """Calculate overall match score (0-100)"""
        
        # Head match score (best when margin is ~5-10%)
        if head_margin < 0:
            head_score = max(0, 50 + head_margin * 100)  # Penalize under-capacity
        elif head_margin <= 0.15:
            head_score = 100 - abs(head_margin - 0.075) * 400  # Peak at 7.5%
        else:
            head_score = max(0, 100 - (head_margin - 0.15) * 200)  # Penalize over-capacity
        
        # Efficiency score
        eff_score = min(100, efficiency * 1.2)  # Scale efficiency
        
        # Flow range score (prefer middle of range)
        flow_range = self.limits.max_flow_m3h - self.limits.min_flow_m3h
        if flow_range > 0:
            optimal_flow = self.limits.min_flow_m3h + flow_range * 0.6  # 60% of range is optimal
            flow_deviation = abs(required_flow - optimal_flow) / flow_range
            flow_score = max(0, 100 - flow_deviation * 100)
        else:
            flow_score = 50
        
        # Weighted combination
        match_score = head_score * 0.45 + eff_score * 0.35 + flow_score * 0.20
        
        return max(0, min(100, match_score))


class PumpDatabaseManager:
    """Manages loading and querying pump database"""
    
    def __init__(self, database_path: str = None):
        """
        Initialize database manager.
        
        Args:
            database_path: Path to JSON database file. If None, uses default location.
        """
        if database_path is None:
            # Default to same directory as this module
            module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            database_path = os.path.join(module_dir, 'pump_database_seed.json')
        
        self.database_path = database_path
        self.pumps: List[dict] = []
        self._load_database()
    
    def _load_database(self):
        """Load pump database from JSON file"""
        try:
            with open(self.database_path, 'r') as f:
                self.pumps = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Pump database not found at {self.database_path}")
            self.pumps = []
        except json.JSONDecodeError as e:
            print(f"Warning: Error parsing pump database: {e}")
            self.pumps = []
    
    def get_all_pumps(self) -> List[dict]:
        """Get all pumps in database"""
        return self.pumps
    
    def get_pump_by_id(self, pump_id: str) -> Optional[dict]:
        """Get pump by ID"""
        for pump in self.pumps:
            if pump.get('id') == pump_id:
                return pump
        return None
    
    def get_pumps_by_brand(self, brand: str) -> List[dict]:
        """Get all pumps from a specific brand"""
        return [p for p in self.pumps if p.get('brand', '').lower() == brand.lower()]
    
    def find_suitable_pumps(
        self,
        required_flow_m3h: float,
        required_head_m: float
    ) -> List[PumpMatch]:
        """
        Find all pumps that might be suitable for the requirements.
        
        Args:
            required_flow_m3h: Required flow rate
            required_head_m: Required head
            
        Returns:
            List of PumpMatch results, sorted by match score
        """
        matches = []
        
        for pump_data in self.pumps:
            solver = PumpCurveSolver(pump_data)
            match = solver.check_suitability(required_flow_m3h, required_head_m)
            matches.append(match)
        
        # Sort by suitability (suitable first) then by match score
        matches.sort(key=lambda m: (-int(m.is_suitable), -m.match_score))
        
        return matches


def get_efficiency_badge_color(efficiency: float) -> Tuple[str, str]:
    """
    Get badge color based on efficiency.
    
    Returns:
        Tuple of (color_code, label)
    """
    if efficiency > 75:
        return "#28a745", "Excellent Efficiency"  # Green
    elif efficiency >= 60:
        return "#ffc107", "Standard Efficiency"   # Yellow
    else:
        return "#dc3545", "Low Efficiency"        # Red


def format_power_display(power_kw: float) -> str:
    """Format power for display with appropriate units"""
    if power_kw < 1:
        return f"{power_kw * 1000:.0f} W"
    elif power_kw < 100:
        return f"{power_kw:.1f} kW"
    else:
        return f"{power_kw:.0f} kW"

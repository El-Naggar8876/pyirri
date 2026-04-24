"""
Input Validators Component
==========================
Professional input validation with inline error messages.
Validates engineering parameters against physical constraints.
"""

import streamlit as st
from dataclasses import dataclass
from typing import Optional, Tuple, Union, Callable
from enum import Enum


class ValidationLevel(Enum):
    """Validation severity levels."""
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    level: ValidationLevel
    message: Optional[str] = None
    
    @property
    def has_warning(self) -> bool:
        return self.level == ValidationLevel.WARNING
    
    @property
    def has_error(self) -> bool:
        return self.level == ValidationLevel.ERROR


# =============================================================================
# ENGINEERING VALIDATION LIMITS
# =============================================================================

ENGINEERING_LIMITS = {
    # Pressure limits (kPa)
    "pressure": {
        "min": 50,           # Minimum practical operating pressure
        "max": 1000,         # Maximum safe pressure for most systems
        "typical_min": 150,  # Typical minimum for sprinklers
        "typical_max": 500,  # Typical maximum for sprinklers
    },
    
    # Flow rate limits (m³/h)
    "flow_rate": {
        "min": 0.1,          # Minimum measurable flow
        "max": 500,          # Maximum for standard irrigation
        "typical_min": 0.5,
        "typical_max": 100,
    },
    
    # Pipe diameter limits (mm)
    "pipe_diameter": {
        "min": 10,           # Minimum practical pipe size
        "max": 500,          # Maximum for standard irrigation
        "typical_min": 20,
        "typical_max": 200,
    },
    
    # Spacing limits (m)
    "spacing": {
        "min": 1,            # Minimum practical spacing
        "max": 100,          # Maximum reasonable spacing
        "typical_min": 5,
        "typical_max": 30,
    },
    
    # Friction loss limits (m/100m)
    "friction_loss": {
        "min": 0,
        "max": 20,           # Critical - likely design error
        "typical_max": 5,    # Recommended maximum
    },
    
    # Velocity limits (m/s)
    "velocity": {
        "min": 0.3,          # Minimum to avoid sedimentation
        "max": 3.0,          # Maximum to avoid water hammer
        "typical_max": 2.0,  # Recommended maximum
    },
    
    # Head limits (m)
    "head": {
        "min": 0,
        "max": 200,          # Maximum practical pump head
        "typical_max": 100,
    },
    
    # Efficiency limits (%)
    "efficiency": {
        "min": 50,           # Below this, system needs redesign
        "typical_min": 70,   # Acceptable minimum
        "max": 100,
    }
}


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_positive_number(
    value: Union[int, float],
    field_name: str = "Value"
) -> ValidationResult:
    """
    Validate that a value is a positive number.
    
    Args:
        value: The value to validate
        field_name: Name of the field for error messages
    
    Returns:
        ValidationResult with status and message
    """
    if value is None:
        return ValidationResult(
            is_valid=False,
            level=ValidationLevel.ERROR,
            message=f"{field_name} is required"
        )
    
    try:
        num_value = float(value)
        if num_value <= 0:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"{field_name} must be greater than 0"
            )
        return ValidationResult(is_valid=True, level=ValidationLevel.OK)
    except (TypeError, ValueError):
        return ValidationResult(
            is_valid=False,
            level=ValidationLevel.ERROR,
            message=f"{field_name} must be a valid number"
        )


def validate_range(
    value: Union[int, float],
    min_val: float,
    max_val: float,
    field_name: str = "Value",
    typical_min: Optional[float] = None,
    typical_max: Optional[float] = None
) -> ValidationResult:
    """
    Validate that a value is within acceptable range.
    Returns warning if outside typical range but within physical limits.
    
    Args:
        value: The value to validate
        min_val: Absolute minimum (physically impossible below this)
        max_val: Absolute maximum (physically impossible above this)
        field_name: Name of the field for error messages
        typical_min: Typical engineering minimum (warning if below)
        typical_max: Typical engineering maximum (warning if above)
    
    Returns:
        ValidationResult with status and message
    """
    if value is None:
        return ValidationResult(
            is_valid=False,
            level=ValidationLevel.ERROR,
            message=f"{field_name} is required"
        )
    
    try:
        num_value = float(value)
        
        # Check absolute limits (ERROR)
        if num_value < min_val:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"{field_name} cannot be less than {min_val}"
            )
        
        if num_value > max_val:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"{field_name} cannot exceed {max_val}"
            )
        
        # Check typical limits (WARNING)
        if typical_min is not None and num_value < typical_min:
            return ValidationResult(
                is_valid=True,  # Still valid, but warn
                level=ValidationLevel.WARNING,
                message=f"{field_name} ({num_value}) is below typical minimum ({typical_min}). Verify design intent."
            )
        
        if typical_max is not None and num_value > typical_max:
            return ValidationResult(
                is_valid=True,  # Still valid, but warn
                level=ValidationLevel.WARNING,
                message=f"{field_name} ({num_value}) exceeds typical maximum ({typical_max}). Verify design intent."
            )
        
        return ValidationResult(is_valid=True, level=ValidationLevel.OK)
        
    except (TypeError, ValueError):
        return ValidationResult(
            is_valid=False,
            level=ValidationLevel.ERROR,
            message=f"{field_name} must be a valid number"
        )


def validate_pressure(value: Union[int, float], field_name: str = "Pressure") -> ValidationResult:
    """Validate pressure value (kPa)."""
    limits = ENGINEERING_LIMITS["pressure"]
    return validate_range(
        value,
        min_val=limits["min"],
        max_val=limits["max"],
        field_name=f"{field_name} (kPa)",
        typical_min=limits["typical_min"],
        typical_max=limits["typical_max"]
    )


def validate_flow_rate(value: Union[int, float], field_name: str = "Flow Rate") -> ValidationResult:
    """Validate flow rate value (m³/h)."""
    limits = ENGINEERING_LIMITS["flow_rate"]
    return validate_range(
        value,
        min_val=limits["min"],
        max_val=limits["max"],
        field_name=f"{field_name} (m³/h)",
        typical_min=limits["typical_min"],
        typical_max=limits["typical_max"]
    )


def validate_pipe_diameter(value: Union[int, float], field_name: str = "Pipe Diameter") -> ValidationResult:
    """Validate pipe diameter value (mm)."""
    limits = ENGINEERING_LIMITS["pipe_diameter"]
    return validate_range(
        value,
        min_val=limits["min"],
        max_val=limits["max"],
        field_name=f"{field_name} (mm)",
        typical_min=limits["typical_min"],
        typical_max=limits["typical_max"]
    )


def validate_spacing(value: Union[int, float], field_name: str = "Spacing") -> ValidationResult:
    """Validate spacing value (m)."""
    limits = ENGINEERING_LIMITS["spacing"]
    return validate_range(
        value,
        min_val=limits["min"],
        max_val=limits["max"],
        field_name=f"{field_name} (m)",
        typical_min=limits["typical_min"],
        typical_max=limits["typical_max"]
    )


def validate_velocity(value: Union[int, float], field_name: str = "Velocity") -> ValidationResult:
    """Validate water velocity (m/s)."""
    limits = ENGINEERING_LIMITS["velocity"]
    return validate_range(
        value,
        min_val=limits["min"],
        max_val=limits["max"],
        field_name=f"{field_name} (m/s)",
        typical_max=limits["typical_max"]
    )


def validate_friction_loss(value: Union[int, float], field_name: str = "Friction Loss") -> ValidationResult:
    """Validate friction loss (m/100m or total)."""
    limits = ENGINEERING_LIMITS["friction_loss"]
    return validate_range(
        value,
        min_val=limits["min"],
        max_val=limits["max"],
        field_name=field_name,
        typical_max=limits["typical_max"]
    )


def validate_efficiency(value: Union[int, float], field_name: str = "Efficiency") -> ValidationResult:
    """Validate efficiency percentage."""
    limits = ENGINEERING_LIMITS["efficiency"]
    return validate_range(
        value,
        min_val=limits["min"],
        max_val=limits["max"],
        field_name=f"{field_name} (%)",
        typical_min=limits["typical_min"]
    )


# =============================================================================
# STREAMLIT UI HELPERS
# =============================================================================

def render_validation_message(result: ValidationResult):
    """
    Render inline validation message below an input field.
    Only renders if there's a warning or error.
    
    Args:
        result: ValidationResult from a validation function
    """
    if result.level == ValidationLevel.OK or result.message is None:
        return
    
    if result.level == ValidationLevel.ERROR:
        st.markdown(
            f'<div class="validation-error">{result.message}</div>',
            unsafe_allow_html=True
        )
    elif result.level == ValidationLevel.WARNING:
        st.markdown(
            f'<div class="validation-warning">⚠ {result.message}</div>',
            unsafe_allow_html=True
        )


def validated_number_input(
    label: str,
    validator: Callable[[float], ValidationResult],
    key: str,
    min_value: float = None,
    max_value: float = None,
    value: float = None,
    step: float = None,
    help: str = None,
    format: str = None
) -> Tuple[float, ValidationResult]:
    """
    Create a number input with automatic validation display.
    
    Args:
        label: Input label
        validator: Validation function to apply
        key: Streamlit widget key
        min_value, max_value, value, step, help, format: Standard st.number_input args
    
    Returns:
        Tuple of (input_value, validation_result)
    """
    input_value = st.number_input(
        label=label,
        min_value=min_value,
        max_value=max_value,
        value=value,
        step=step,
        help=help,
        format=format,
        key=key
    )
    
    result = validator(input_value)
    render_validation_message(result)
    
    return input_value, result


def get_validation_summary(results: list[ValidationResult]) -> dict:
    """
    Get summary of multiple validation results.
    
    Args:
        results: List of ValidationResult objects
    
    Returns:
        Dict with counts of errors, warnings, and overall status
    """
    errors = sum(1 for r in results if r.level == ValidationLevel.ERROR)
    warnings = sum(1 for r in results if r.level == ValidationLevel.WARNING)
    
    if errors > 0:
        overall = "error"
    elif warnings > 0:
        overall = "warning"
    else:
        overall = "ok"
    
    return {
        "errors": errors,
        "warnings": warnings,
        "overall": overall,
        "is_valid": errors == 0
    }

from fractions import Fraction

def _float_to_frac(value: float, max_denominator: int = 8) -> str:
    """Convert a float to a compact fraction string"""
    
    frac = Fraction(value).limit_denominator(max_denominator)
    whole = int(frac)
    remainder = frac - whole
    
    # Create string representation
    if remainder == 0:
        return str(whole)
    elif whole == 0:
        return f"{remainder.numerator}/{remainder.denominator}"
    else:
        return f"{whole} {remainder.numerator}/{remainder.denominator}"
    
# print(_float_to_frac(0.25))  # "1/4"
# print(_float_to_frac(0.5))   # "1/2"
# print(_float_to_frac(1.5))   # "1 1/2"
# print(_float_to_frac(0.333)) # "1/3"
print(_float_to_frac(0.1))   # 0.1

import pint
ureg = pint.UnitRegistry()


q1 = ureg.Quantity(Fraction(1, 3), 'meter')
q2 = ureg.Quantity(Fraction(1, 4), 'meter')

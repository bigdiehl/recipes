
from pint import UnitRegistry

ureg = UnitRegistry()

def add_dimensionless_unit(name):
    ureg.define(f"{name} = 1 * dimensionless")
        
add_dimensionless_unit("bundle")
add_dimensionless_unit("cans")
add_dimensionless_unit("tub")
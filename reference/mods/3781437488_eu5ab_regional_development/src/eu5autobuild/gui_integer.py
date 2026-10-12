"""Exact int32 transport for GUI APIs without a CFixedPoint conversion.

IntToFixedPoint returns float in EU5 1.4 and cannot feed MakeScopeValue.
Select fixed literals for each binary digit, then add a balanced expression.
Negative inputs remain unknown (-1); no queue-size cap or clamping is imposed.
"""


def nonnegative_int32(expression: str) -> str:
    terms = [
        f"Select_CFixedPoint(EqualTo_int32(Modulo_int32(Divide_int32({expression}, "
        f"'(int32){1 << bit}'), '(int32)2'), '(int32)1'), "
        f"'(CFixedPoint){1 << bit}', '(CFixedPoint)0')"
        for bit in range(31)
    ]
    while len(terms) > 1:
        terms = [f'Add_CFixedPoint({terms[i]}, {terms[i + 1]})'
                 if i + 1 < len(terms) else terms[i]
                 for i in range(0, len(terms), 2)]
    return (f"Select_CFixedPoint(LessThan_int32({expression}, '(int32)0'), "
            f"'(CFixedPoint)-1', {terms[0]})")

from .parser import MatrixParser
from .formatted_string import FormattedString


def parse_html(input_html: str) -> str:
    return MatrixParser.parse(input_html).text

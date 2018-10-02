from typing import Union, Dict, List, NewType

JSON = NewType("JSON", Union[str, int, float, bool, None, Dict[str, 'JSON'], List['JSON']])

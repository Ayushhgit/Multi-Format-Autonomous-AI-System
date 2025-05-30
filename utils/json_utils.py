"""
JSON utility functions for validation and processing
"""

import json
import jsonschema
from typing import Dict, Any, List, Optional

def validate_json_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Validate JSON data against schema"""
    try:
        jsonschema.validate(instance=data, schema=schema)
        return {
            "is_valid": True,
            "errors": [],
            "message": "Validation successful"
        }
    except jsonschema.ValidationError as e:
        return {
            "is_valid": False,
            "errors": [e.message],
            "message": f"Validation failed: {e.message}",
            "path": list(e.path) if e.path else []
        }

def flatten_json(data: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """Flatten nested JSON structure"""
    items = []
    for k, v in data.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_json(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.extend(flatten_json(item, f"{new_key}[{i}]", sep=sep).items())
                else:
                    items.append((f"{new_key}[{i}]", item))
        else:
            items.append((new_key, v))
    return dict(items)

def extract_json_paths(data: Dict[str, Any]) -> List[str]:
    """Extract all JSON paths from nested structure"""
    paths = []
    
    def _extract_paths(obj, current_path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{current_path}.{key}" if current_path else key
                paths.append(new_path)
                _extract_paths(value, new_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = f"{current_path}[{i}]"
                paths.append(new_path)
                _extract_paths(item, new_path)
    
    _extract_paths(data)
    return paths

def safe_json_get(data: Dict[str, Any], path: str, default=None):
    """Safely get value from nested JSON using dot notation"""
    try:
        keys = path.split('.')
        value = data
        for key in keys:
            if '[' in key and ']' in key:
                # Handle array access
                array_key, index = key.split('[')
                index = int(index.rstrip(']'))
                value = value[array_key][index]
            else:
                value = value[key]
        return value
    except (KeyError, IndexError, TypeError):
        return default
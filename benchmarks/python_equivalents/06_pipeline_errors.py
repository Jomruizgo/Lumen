import httpx
import json
from typing import Union

def get_user_data(user_id: int) -> Union[dict, Exception]:
    try:
        response = httpx.get(f"https://api.example.com/users/{user_id}")
        response.raise_for_status()
    except httpx.HTTPError as e:
        return e

    try:
        parsed = response.json()
    except json.JSONDecodeError as e:
        return e

    data = parsed.get("data")
    if data is None:
        return KeyError("field 'data' not found in response")

    return data

if __name__ == "__main__":
    data = get_user_data(42)
    if isinstance(data, Exception):
        print(f"Error: {data}")
    elif isinstance(data, dict):
        print(f"Usuario: {data.get('name', 'unknown')}")
    else:
        print(f"Error: unexpected result type")

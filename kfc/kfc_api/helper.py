import requests
from typing import Any, Dict, Optional, Tuple


def HTTPGet(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
) -> Tuple[Optional[Any], Optional[Any]]:
    try:
        response = requests.get(
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
        )
        if not response.ok:
            return None, f"HTTP {response.status_code}: {response.text}"
        return response, response.status_code
    except requests.exceptions.Timeout:
        return None, "Request timed out"
    except requests.exceptions.ConnectionError:
        return None, "Connection error"
    except requests.exceptions.RequestException as e:
        return None, f"Request failed: {str(e)}"

import requests
from typing import Any, Dict, Optional, Tuple


def HTTPGet(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    cookies: Optional[Dict[str, str]] = None,
    timeout: int = 10,
) -> Tuple[Optional[Any], Optional[Any]]:
    try:
        response = requests.get(
            url=url,
            headers=headers,
            params=params,
            cookies=cookies,
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


def HTTPPost(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    cookies: Optional[Dict[str, str]] = None,
    timeout: int = 10,
) -> Tuple[Optional[Any], Optional[Any]]:
    try:
        response = requests.post(
            url=url,
            headers=headers,
            data=data,
            json=json,
            params=params,
            cookies=cookies,
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


def HTTPPut(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    cookies: Optional[Dict[str, str]] = None,
    timeout: int = 10,
) -> Tuple[Optional[Any], Optional[Any]]:
    try:
        response = requests.put(
            url=url,
            headers=headers,
            data=data,
            json=json,
            params=params,
            cookies=cookies,
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


def HTTPOptions(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    cookies: Optional[Dict[str, str]] = None,
    timeout: int = 10,
) -> Tuple[Optional[Any], Optional[Any]]:
    try:
        response = requests.options(
            url=url,
            headers=headers,
            data=data,
            params=params,
            cookies=cookies,
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

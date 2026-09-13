"""Bypass reCAPTCHA v3 pour la soumission de commande KFC (logique alignée sur Click)."""

from __future__ import annotations

import re
from typing import Optional, Tuple

import requests

_RECAPTCHA_ANCHOR_URL = (
    "https://recaptcha.net/recaptcha/api2/anchor?ar=1"
    "&k=6LdkEnMaAAAAAJdHrWw86-qry-pB2LYDbaDYirJs"
    "&co=aHR0cHM6Ly93d3cua2ZjLmZyOjQ0Mw.."
    "&hl=fr&v=gYdqkxiddE5aXrugNbBbKgtN&size=invisible"
    "&anchor-ms=20000&execute-ms=30000&cb=ki5ur14lmk1l"
)


class ReCaptchaV3Bypass:
    """Bypass reCAPTCHA v3 (fonctionne seulement pour certains challenges)."""

    def __init__(self, target_url: str) -> None:
        self.target_url = target_url
        self.session = requests.Session()
        self.session.trust_env = False

    def _extract_value(self, pattern: str, text: str) -> str:
        return re.search(pattern, text).group(1)

    def extract_values(self, response) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        try:
            recaptcha_token = self._extract_value(
                r'type="hidden" id="recaptcha-token" value="(.*?)"',
                response.text,
            )
            k_value = self._extract_value(r"&k=(.*?)&co", self.target_url)
            co_value = self._extract_value(r"&co=(.*?)&hl", self.target_url)
            v_value = self._extract_value(r"&v=(.*?)&size", self.target_url)
            return recaptcha_token, k_value, co_value, v_value
        except (AttributeError, IndexError):
            return None, None, None, None

    def get_response(self):
        try:
            return self.session.get(self.target_url, timeout=15)
        except requests.exceptions.RequestException:
            return None

    def post_response(self, recaptcha_token, k_value, co_value, v_value):
        post_url = "https://www.google.com/recaptcha/api2/reload?k=" + k_value
        post_data = {
            "v": v_value,
            "reason": "q",
            "c": recaptcha_token,
            "k": k_value,
            "co": co_value,
            "hl": "en",
            "size": "invisible",
            "chr": "%5B89%2C64%2C27%5D",
            "vh": "13599012192",
        }
        try:
            return self.session.post(post_url, data=post_data, timeout=15)
        except requests.exceptions.RequestException:
            return None

    def extract_gtk(self, response) -> Optional[str]:
        try:
            return self._extract_value(r'\["rresp","(.*?)"', response.text)
        except (AttributeError, IndexError):
            return None

    def bypass(self) -> Optional[str]:
        initial = self.get_response()
        if initial is None:
            return None

        recaptcha_token, k_value, co_value, v_value = self.extract_values(initial)
        if None in (recaptcha_token, k_value, co_value, v_value):
            return None

        post_resp = self.post_response(recaptcha_token, k_value, co_value, v_value)
        if post_resp is None:
            return None

        return self.extract_gtk(post_resp)


def GetRecaptchaToken() -> str:
    """Récupère un jeton reCAPTCHA v3 frais via bypass."""
    return ReCaptchaV3Bypass(_RECAPTCHA_ANCHOR_URL).bypass() or ""

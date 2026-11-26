from __future__ import annotations

from json import JSONDecodeError
import logging
import time

from PySubtitle.Helpers.Parse import ParseDelayFromHeader
from PySubtitle.SubtitleError import TranslationResponseError

try:

    from .MinimalOpenAIClient import MinimalOpenAIClient

    from PySubtitle.Helpers import FormatMessages
    from PySubtitle.SubtitleError import TranslationError, TranslationImpossibleError, TranslationProviderUnavailableError
    from PySubtitle.Translation import Translation
    from PySubtitle.TranslationClient import TranslationClient
    from PySubtitle.TranslationPrompt import TranslationPrompt

    class OpenAIClient(TranslationClient):
        """
        Handles communication with OpenAI to request translations
        """
        def __init__(self, settings : dict):
            super().__init__(settings)

            if not self.api_key:
                raise TranslationImpossibleError('API key must be provided as an argument')

            logging.info(f"Translating with model {self.model or 'default'}, Using API Base: {self.api_base or 'https://api.openai.com/v1'}")

            self.client = None

        @property
        def api_key(self):
            return self.settings.get('api_key')

        @property
        def api_base(self):
            return self.settings.get('api_base')

        @property
        def model(self):
            return self.settings.get('model')
        
        @property
        def reuse_client(self):
            return self.settings.get('reuse_client', True)

        def _request_translation(self, prompt : TranslationPrompt, temperature : float = None) -> Translation:
            """
            Request a translation based on the provided prompt
            """
            logging.debug(f"Messages:\n{FormatMessages(prompt.messages)}")

            # If we're using a new client for each request, create it here
            temperature = temperature or self.temperature

            response = self._try_send_messages(prompt, temperature)

            translation = Translation(response) if response else None

            if translation:
                if translation.quota_reached:
                    raise TranslationImpossibleError("Account quota reached, please upgrade your plan or wait until it renews")

                if translation.reached_token_limit:
                    raise TranslationError(f"Too many tokens in translation", translation=translation)

            return translation

        def _send_messages(self, messages : list[str], temperature : float):
            """
            Communicate with the API
            """
            raise NotImplementedError

        def _abort(self):
            # MinimalOpenAIClient does not require explicit close
            return super()._abort()
        
        # HTTP statuses worth retrying: request timeout, conflict, too early and server-side failures.
        TRANSIENT_STATUS_CODES = (408, 409, 425)
        MAX_RETRY_DELAY = 60.0
        # Give up on the whole file only after this many batches in a row could not reach the provider.
        MAX_CONSECUTIVE_UNAVAILABLE = 5

        def _try_send_messages(self, prompt : TranslationPrompt, temperature: float):
            last_error = None
            for retry in range(int(self.max_retries) + 1):
                if self.aborted:
                    return None

                backoff_time = min(self.backoff_time * 2.0**retry, self.MAX_RETRY_DELAY)

                try:
                    if not self.client or not self.reuse_client:
                        self._create_client()

                    response = self._send_messages(prompt.content, temperature)
                    self._consecutive_unavailable = 0
                    return response

                except TranslationImpossibleError:
                    raise

                except Exception as e:
                    last_error = e
                    status = getattr(getattr(e, 'response', None), 'status_code', None)

                    if status == 429:
                        if self._is_quota_exhausted(e.response):
                            raise TranslationImpossibleError("Account quota reached, please upgrade your plan or wait until it renews", error=e)
                        retry_after = e.response.headers.get('Retry-After') or e.response.headers.get('x-ratelimit-reset-requests')
                        if retry_after:
                            backoff_time = min(ParseDelayFromHeader(retry_after), self.MAX_RETRY_DELAY)
                        reason = "Rate limit hit"
                    elif status is not None and not (status >= 500 or status in self.TRANSIENT_STATUS_CODES):
                        # Bad key, bad model or bad request: retrying cannot help.
                        raise TranslationImpossibleError(f"Provider rejected the request (HTTP {status})", error=e)
                    elif status is not None:
                        reason = f"Provider error (HTTP {status})"
                    elif isinstance(e, (TranslationResponseError, ValueError, OSError)) or self._is_network_error(e):
                        # Timeouts, dropped connections and unreadable responses (JSONDecodeError is a ValueError).
                        reason = f"Provider unreachable ({type(e).__name__})"
                    else:
                        raise TranslationImpossibleError(f"Unexpected error communicating with the provider", error=e)

                    if retry < self.max_retries and not self.aborted:
                        logging.warning(f"{reason}, retrying in {backoff_time:.0f} seconds...")
                        time.sleep(backoff_time)
                        continue

            if self.aborted:
                return None

            self._consecutive_unavailable = getattr(self, '_consecutive_unavailable', 0) + 1
            if self._consecutive_unavailable >= self.MAX_CONSECUTIVE_UNAVAILABLE:
                raise TranslationImpossibleError(
                    f"Provider unreachable for {self._consecutive_unavailable} batches in a row, stopping translation",
                    error=last_error)
            raise TranslationProviderUnavailableError(
                f"Provider unreachable after {int(self.max_retries) + 1} attempts ({type(last_error).__name__}), skipping batch for now",
                error=last_error)

        @staticmethod
        def _is_network_error(error):
            try:
                import requests
                return isinstance(error, (requests.ConnectionError, requests.Timeout))
            except ImportError:
                return False

        @staticmethod
        def _is_quota_exhausted(response):
            try:
                body = response.json()
                code = (body.get('error') or {}).get('code') or (body.get('error') or {}).get('type')
                return code == 'insufficient_quota'
            except Exception:
                return False

        def _create_client(self):
            # Proxy support can be added to MinimalOpenAIClient if needed
            self.client = MinimalOpenAIClient(api_key=self.api_key, api_base=self.api_base)

except ImportError as e:
    logging.debug(f"Failed to import openai: {e}")

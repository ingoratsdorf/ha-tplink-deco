import asyncio
import base64
import hashlib
import json
import logging
import math
import re
import secrets
from typing import Any
from urllib.parse import quote_plus

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA
import aiohttp
from aiohttp.hdrs import CONTENT_TYPE
from aiohttp.hdrs import COOKIE
from aiohttp.hdrs import SET_COOKIE
import async_timeout
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.ciphers import modes
import homeassistant.util.ssl as ssl

from .const import DEFAULT_TIMEOUT_ERROR_RETRIES
from .const import DEFAULT_TIMEOUT_SECONDS
from .exceptions import EmptyDataException
from .exceptions import ForbiddenException
from .exceptions import LoginForbiddenException
from .exceptions import LoginInvalidException
from .exceptions import TimeoutException
from .exceptions import UnexpectedApiException

AES_KEY_BYTES = 16
MIN_AES_KEY = 10 ** (AES_KEY_BYTES - 1)
MAX_AES_KEY = (10**AES_KEY_BYTES) - 1

PKCS1_v1_5_HEADER_BYTES = 11

_LOGGER: logging.Logger = logging.getLogger(__name__)


def byte_len(n: int) -> int:
    return (int(math.log2(n)) + 8) >> 3


def decode_name_with_fallback(name: str):
    try:
        name = base64.b64decode(name)
        return name.decode()
    except Exception as err:
        _LOGGER.warning("Error decoding name %s: %s", name, err)
        return f"<Error Decoding {name}>"


def rsa_encrypt(n: int, e: int, plaintext: bytes) -> bytes:
    """
    RSA encrypts plaintext. TP-Link breaks the plaintext down into blocks and concatenates the output.
    :param n: The RSA public key's n value
    :param e: The RSA public key's e value
    :param plaintext: The data to encrypt
    :return: RSA encrypted ciphertext
    """
    public_key = RSA.construct((n, e)).publickey()
    encryptor = PKCS1_v1_5.new(public_key)
    block_size = byte_len(n)
    bytes_per_block = block_size - PKCS1_v1_5_HEADER_BYTES

    encrypted_text = ""
    text_bytes = len(plaintext)
    index = 0
    while index < text_bytes:
        content_num_bytes = min(bytes_per_block, text_bytes - index)
        content = plaintext[index : index + content_num_bytes]
        encrypted_text += encryptor.encrypt(content).hex()
        index += content_num_bytes

    return encrypted_text


def aes_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    """
    AES-CBC encrypt with PKCS #7 padding. This matches the AES options on TP-Link routers.
    :param key: The AES key
    :param iv: The AES IV
    :param plaintext: Data to encrypt
    :return: Ciphertext
    """
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    plaintext_bytes: bytes = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext_bytes) + encryptor.finalize()
    return ciphertext


def aes_decrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    """
    AES-CBC decrypt with PKCS #7 padding.
    :param key: The AES key
    :param iv: The AES IV
    :param plaintext: Data to encrypt
    :return: Ciphertext
    """
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    ciphertext = decryptor.update(plaintext) + decryptor.finalize()
    return ciphertext


def check_data_error_code(context, data):
    error_code = data.get("error_code") or data.get("errorcode")
    if error_code:
        if error_code == "timeout":
            raise TimeoutException(f'{context} response error_code="timeout"')

        _LOGGER.debug("%s error_code=%s, data=%s", context, error_code, data)
        raise UnexpectedApiException(f"{context} error_code={error_code}")


class TplinkDecoApi:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
        verify_ssl: bool,
        timeout_error_retries: int = DEFAULT_TIMEOUT_ERROR_RETRIES,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._host = host
        self._username = username
        self._password = password
        self._session = session
        self._timeout_error_retries = timeout_error_retries
        self._timeout_seconds = timeout_seconds
        self._auth_errors = 0

        self._aes_key = None
        self._aes_key_bytes = None
        self._aes_iv = None
        self._aes_iv_bytes = None

        self._password_rsa_n = None
        self._password_rsa_e = None
        self._sign_rsa_n = None
        self._sign_rsa_e = None

        self._login_future = None
        self._seq = None
        self._stok = None
        self._cookie = None

        if verify_ssl:
            self._ssl_context = None
        else:
            context = ssl.get_default_no_verify_context()
            self._ssl_context = context

    # Return list of deco devices
    async def async_list_devices(self) -> dict:
        return await self._async_call_with_retry(self._async_list_devices)

    async def _async_list_devices(self) -> dict:
        await self.async_login_if_needed()

        context = "List Devices"
        device_list_payload = {"operation": "read"}
        response_json = await self._async_post(
            context,
            f"{self._host}/cgi-bin/luci/;stok={self._stok}/admin/device",
            params={"form": "device_list"},
            data=self._encode_payload(device_list_payload),
        )
        data = self._decrypt_data(context, response_json["data"])
        check_data_error_code(context, data)

        try:
            device_list = data["result"]["device_list"]
            _LOGGER.debug("List devices device_count=%d", len(device_list))
            _LOGGER.debug("List devices device_list=%s", device_list)

            for device in device_list:
                custom_nickname = device.get("custom_nickname")
                if custom_nickname is not None:
                    device["custom_nickname"] = decode_name_with_fallback(
                        custom_nickname
                    )

            return device_list
        except Exception as err:
            _LOGGER.error("%s parse response error=%s, data=%s", context, err, data)
            raise err

    # Reboot decos.
    async def async_reboot_decos(self, deco_macs) -> dict:
        await self.async_login_if_needed()

        context = f"Reboot Decos {deco_macs}"
        client_payload = {
            "operation": "reboot",
            "params": {"mac_list": [{"mac": mac} for mac in deco_macs]},
        }
        response_json = await self._async_post(
            context,
            f"{self._host}/cgi-bin/luci/;stok={self._stok}/admin/device",
            params={"form": "system"},
            data=self._encode_payload(client_payload),
        )

        data = self._decrypt_data(context, response_json["data"])
        check_data_error_code(context, data)
        _LOGGER.debug("Rebooted decos %s", deco_macs)

    # Return list of clients. Default lists clients for all decos.
    async def async_list_clients(self, deco_mac="default") -> dict:
        return await self._async_call_with_retry(self._async_list_clients, deco_mac)

    async def _async_list_clients(self, deco_mac) -> dict:
        await self.async_login_if_needed()

        context = f"List Clients {deco_mac}"
        client_payload = {"operation": "read", "params": {"device_mac": deco_mac}}
        response_json = await self._async_post(
            context,
            f"{self._host}/cgi-bin/luci/;stok={self._stok}/admin/client",
            params={"form": "client_list"},
            data=self._encode_payload(client_payload),
        )

        data = self._decrypt_data(context, response_json["data"])
        check_data_error_code(context, data)

        try:
            client_list = data["result"]["client_list"]
            # client_list is only the connected clients
            _LOGGER.debug("%s client_count=%d", context, len(client_list))
            _LOGGER.debug("%s client_list=%s", context, client_list)

            for client in client_list:
                client["name"] = decode_name_with_fallback(client["name"])

            return client_list
        except Exception as err:
            _LOGGER.error("%s parse response error=%s, data=%s", context, err, data)
            raise err

    def _generate_aes_key_and_iv(self):
        # TPLink requires key and IV to be a 16 digit number (no leading 0s)
        self._aes_key = secrets.randbelow(MAX_AES_KEY - MIN_AES_KEY) + MIN_AES_KEY
        self._aes_iv = secrets.randbelow(MAX_AES_KEY - MIN_AES_KEY) + MIN_AES_KEY
        self._aes_key_bytes = str(self._aes_key).encode("utf-8")
        self._aes_iv_bytes = str(self._aes_iv).encode("utf-8")
        _LOGGER.debug("aes_key=%s", self._aes_key)
        _LOGGER.debug("aes_iv=%s", self._aes_iv)

    # Fetch password RSA keys
    async def _async_fetch_keys(self):
        context = "Fetch keys"
        response_json = await self._async_post(
            context,
            f"{self._host}/cgi-bin/luci/;stok=/login",
            params={"form": "keys"},
            data=json.dumps({"operation": "read"}),
        )

        try:
            keys = response_json["result"]["password"]
            self._password_rsa_n = int(keys[0], 16)
            self._password_rsa_e = int(keys[1], 16)
            _LOGGER.debug("password_rsa_n=%s", self._password_rsa_n)
            _LOGGER.debug("password_rsa_e=%s", self._password_rsa_e)
        except Exception as err:
            _LOGGER.error(
                "%s parse response error=%s, response_json=%s",
                context,
                err,
                response_json,
            )
            raise err

    # Fetch sign RSA keys and seq no
    async def _async_fetch_auth(self):
        context = "Fetch auth"
        response_json = await self._async_post(
            context,
            f"{self._host}/cgi-bin/luci/;stok=/login",
            params={"form": "auth"},
            data=json.dumps({"operation": "read"}),
        )

        try:
            auth_result = response_json["result"]
            auth_key = auth_result["key"]
            self._sign_rsa_n = int(auth_key[0], 16)
            _LOGGER.debug("sign_rsa_n=%s", self._sign_rsa_n)
            self._sign_rsa_e = int(auth_key[1], 16)
            _LOGGER.debug("sign_rsa_e=%s", self._sign_rsa_e)

            self._seq = auth_result["seq"]
            _LOGGER.debug("seq=%s", self._seq)
        except Exception as err:
            _LOGGER.error(
                "%s parse response error=%s, response_json=%s",
                context,
                err,
                response_json,
            )
            raise err

    async def async_login_if_needed(self):
        if self._seq is None or self._stok is None or self._cookie is None:
            await self.async_login()

    async def async_login(self):
        if self._login_future is not None:
            await self._login_future
            return

        self._login_future = asyncio.get_running_loop().create_future()
        try:
            await self._async_login()
            self._login_future.set_result(True)
        except Exception as err:
            self._login_future.set_exception(err)
            raise err
        finally:
            # Await future to suppress future exception was never retrieved error
            try:
                await self._login_future
            except Exception:
                pass
            self._login_future = None

    async def _async_login(self):
        if self._aes_key is None:
            self._generate_aes_key_and_iv()
        if self._password_rsa_n is None:
            await self._async_fetch_keys()
        if self._seq is None:
            await self._async_fetch_auth()

        password_encrypted = rsa_encrypt(
            self._password_rsa_n, self._password_rsa_e, self._password.encode()
        )

        login_payload = {
            "params": {"password": password_encrypted},
            "operation": "login",
        }
        context = "Login"
        try:
            response_json = await self._async_post(
                context,
                f"{self._host}/cgi-bin/luci/;stok=/login",
                params={"form": "login"},
                data=self._encode_payload(login_payload),
            )
        except ForbiddenException as err:
            raise LoginForbiddenException(
                (
                    "Login auth error. Likely caused by logging in with admin account on another device."
                    " See https://github.com/ingoratsdorf/ha-tplink-deco#manager-account."
                )
            ) from err

        data = self._decrypt_data(context, response_json["data"])
        error_code = data.get("error_code")
        result = data.get("result")
        if error_code != 0:
            if error_code == -5002:
                self.clear_auth()
                attempts = result.get("attemptsAllowed", "unknown")
                raise LoginInvalidException(attempts)
            raise UnexpectedApiException(f"Login error data={data}")
        check_data_error_code(context, data)

        try:
            self._stok = result["stok"]
            _LOGGER.debug("stok=%s", self._stok)
        except Exception as err:
            _LOGGER.error("%s parse response error=%s, data=%s", context, err, data)
            raise UnexpectedApiException from err

        if self._cookie is None:
            raise UnexpectedApiException(
                "Login response did not have a Set-Cookie header"
            )

        # Login success
        self._auth_errors = 0

    async def _async_post(
        self,
        context: str,
        url: str,
        params: dict[str:Any],
        data: Any,
    ) -> dict:
        headers = {CONTENT_TYPE: "application/json"}
        if self._cookie is not None:
            headers[COOKIE] = self._cookie
        try:
            async with async_timeout.timeout(self._timeout_seconds):
                response = await self._session.post(
                    url,
                    params=params,
                    data=data,
                    headers=headers,
                    ssl=self._ssl_context,
                )
                response.raise_for_status()

                cookie = response.headers.get(SET_COOKIE)
                if cookie is not None:
                    match = re.search(r"(sysauth=[a-f0-9]+)", cookie)
                    if match:
                        self._cookie = match.group(1)
                        _LOGGER.debug("cookie=%s", self._cookie)

                # Sometimes server responses with incorrect content type, so disable the check
                response_json = await response.json(content_type=None)
                if "error_code" in response_json:
                    error_code = response_json.get("error_code")

                    if error_code != 0 and error_code != "":
                        _LOGGER.debug(
                            "%s error_code=%s, response_json=%s",
                            context,
                            error_code,
                            response_json,
                        )
                        raise UnexpectedApiException(f"{context} error: {error_code}")

                return response_json
        except asyncio.TimeoutError as err:
            _LOGGER.debug(
                "%s timed out",
                context,
            )
            raise TimeoutException from err
        except aiohttp.ClientResponseError as err:
            _LOGGER.error(
                "%s client response error: %s",
                context,
                err,
            )
            if err.status == 401:
                self.clear_auth()
                raise err
            if err.status == 403:
                self.clear_auth()
                message = f"{context} Forbidden error: {err}"
                raise ForbiddenException(message) from err
            raise err
        except (aiohttp.ClientConnectorError, aiohttp.ServerDisconnectedError) as err:
            # Clear auth in case deco rebooted and auth is invalid
            self.clear_auth()
            _LOGGER.error(
                "%s connection error: %s",
                context,
                err,
            )
            raise err
        except aiohttp.ClientError as err:
            _LOGGER.error(
                "%s client error: %s",
                context,
                err,
            )
            raise err

    def _encode_payload(self, payload: Any):
        data = self._encode_data(payload)
        sign = self._encode_sign(len(data))
        # Must URI encode data after calculating data length
        payload = f"sign={sign}&data={quote_plus(data)}"
        return payload

    def _encode_sign(self, data_len: int):
        if self._seq is None:
            self.clear_auth()
            message = "_seq is None"
            raise EmptyDataException(message)
        seq_with_data_len = self._seq + data_len
        auth_hash = (
            hashlib.md5(f"{self._username}{self._password}".encode()).digest().hex()
        )
        sign_text = (
            f"k={self._aes_key}&i={self._aes_iv}&h={auth_hash}&s={seq_with_data_len}"
        )
        sign = rsa_encrypt(self._sign_rsa_n, self._sign_rsa_e, sign_text.encode())
        return sign

    def _encode_data(self, payload: Any):
        payload_json = json.dumps(payload, separators=(",", ":"))

        data_encrypted = aes_encrypt(
            self._aes_key_bytes, self._aes_iv_bytes, payload_json.encode()
        )
        data = base64.b64encode(data_encrypted).decode()
        return data

    def clear_auth(self):
        _LOGGER.debug("clear_auth")
        self._seq = None
        self._stok = None
        self._cookie = None

    def _decrypt_data(self, context: str, data: str):
        if data == "":
            self.clear_auth()
            message = f"{context} data is empty"
            raise EmptyDataException(message)

        try:
            data_decoded = base64.b64decode(data)
            data_decrypted = aes_decrypt(
                self._aes_key_bytes, self._aes_iv_bytes, data_decoded
            )
            # Remove the PKCS #7 padding
            num_padding_bytes = int(data_decrypted[-1])
            data_decrypted = data_decrypted[:-num_padding_bytes].decode()
            data_json = json.loads(data_decrypted)
            return data_json
        except Exception as err:
            _LOGGER.error(
                "%s decode data error=%s, data=%s",
                context,
                err,
                data,
            )
            raise err

    async def _async_call_with_retry(self, func, *args):
        relogin_retried = False
        timeout_retries = 0
        while True:
            try:
                return await func(*args)
            except (EmptyDataException, ForbiddenException) as err:
                if relogin_retried:
                    # Reached max relogin retries
                    raise err
                relogin_retried = True
                _LOGGER.debug(
                    "Re-login and retry potential expired auth error: %s",
                    err,
                )
            except TimeoutException as err:
                if timeout_retries >= self._timeout_error_retries:
                    # Reached max retries
                    raise err
                timeout_retries += 1
                _LOGGER.debug(
                    "Retry (%d of %d) timeout error: %s",
                    timeout_retries,
                    self._timeout_error_retries,
                    err,
                )

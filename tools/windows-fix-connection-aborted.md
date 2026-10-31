# Windows app: "ConnectionError: Connection aborted, RemoteDisconnected"

Provider hangs up without answering (usually a connection limit). In `aurora/xtream.py`, `XtreamClient._api`,
replace the request line inside the retry loop with:

```python
                try: r = self.s.get(f"{self.server}/player_api.php", params=q, timeout=self.timeout)
                except (requests.ConnectionError, requests.Timeout) as e:
                    _LAST[0] = time.time()
                    if attempt == 3:
                        raise XtreamError("Your provider closed the connection. This usually means it allows only a few connections at once: close 91 TV on other devices (TV, phone), wait a minute and try again.") from e
                    time.sleep((2, 4, 8)[attempt]); continue
                finally: _LAST[0] = time.time()
```

Tested on the 1.5.8 source (mocked drops: retries 3 times, then the friendly message). Needs to be applied to the 1.5.9 source (with activation) and rebuilt.

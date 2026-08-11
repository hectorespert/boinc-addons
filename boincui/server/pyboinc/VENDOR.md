# Vendored: pyboinc

Third-party code, copied into this repository. **Do not treat it as ours to restyle**; keep local
changes minimal and listed below so it stays possible to re-sync from upstream.

| | |
|---|---|
| Upstream | <https://github.com/nielstron/pyboinc> |
| Branch / commit | `dev` @ `f8a31dee62f4cf766ac919c99569b77cfb4335ac` |
| Upstream date | 2022-10-16 |
| Vendored on | 2026-08-10 |
| License | MIT (see `LICENSE`, kept verbatim) |

## Why vendored rather than depended on

It has never been published to PyPI, so there is no version to pin. The only other consumer,
the `SpuelMett/Boinc-Home-Assistant-Integration` HACS integration, vendored it for the same reason.
Copying it also keeps this add-on's image buildable from Debian packages alone: the library declares
no dependencies and imports only the standard library.

Only the package is copied — not upstream's tests, `setup.py` or `.travis.yml`.

## Local changes

- **`close()` added** to `_RPCClientRaw` and `RPCClient`. Upstream never closes the connection, so
  anything that polls leaks a socket per cycle and depends on the garbage collector to reap it; BOINC
  also caps concurrent GUI RPC connections. Both additions are marked `LOCAL PATCH` in the source.
- **`set_run_mode()`, `set_network_mode()` and `set_gpu_mode()` fixed.** All three built the duration
  element as `ET.SubElement(req, duration)`, passing the *number* where a tag name belongs, so every
  one of them died with `TypeError: cannot serialize 0 (type int)` before reaching the socket — the
  whole write path was dead on arrival, which is a fair sign nobody has ever exercised it. Now
  `ET.SubElement(req, Tag.DURATION)`.

  Neither fork fixes this properly: `Igor-Misic/pyboinc` left it alone, and `SpuelMett/pyboinc` (with
  the copy inside the HACS integration) changed it to `str(duration)`, which emits `<0>0</0>`. That
  stops the crash but never sends a duration at all, so BOINC falls back to its default of zero:
  right by accident for a permanent change, and silently permanent when a temporary one was asked
  for. The corrected request matches what `boinctui` builds by hand
  (`src/srvdata.cpp:445`), and was verified against a running BOINC client.

Nothing else is modified.

## Upstream quirks worth knowing, deliberately left alone

- `get_results()` returns the **string `"\n"`** rather than an empty list when there are no tasks.
  Normalised once in `../boinc.py` instead of patching the library.
- `init_rpc_client()` connects but does **not** authenticate, and the query methods do not check
  authorisation: against an unauthorised session they return parsed nonsense rather than raising.
  `../boinc.py` calls `authorize()` and checks its return value before querying.
- `_write()` calls `drain()` before writing instead of after, and the loop in `receive()` is dead
  code because `readuntil` already stops at the separator. Both harmless.
- Nothing in the library distinguishes a host that is not there from one that accepts the connection
  and hangs up, which is what BOINC does to a caller missing from its allowed list. `../boinc.py`
  tells them apart by which stage failed.

## Upstream is dormant

Last commit 2022-10-16. PR #4, from the author of the HACS integration, has been open since
2023-05-22; issue #5 has been unanswered since 2023-09. Publishing a maintained fork to PyPI is
recorded as a future item in the repository `TODO.md` — it is what a future Home Assistant core
integration would need, since core requires a pinned PyPI release.

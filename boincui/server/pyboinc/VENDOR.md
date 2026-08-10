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

Nothing else is modified.

## Upstream quirks worth knowing, deliberately left alone

- `get_results()` returns the **string `"\n"`** rather than an empty list when there are no tasks.
  Normalised once in `../boinc.py` instead of patching the library.
- `init_rpc_client()` connects but does **not** authenticate, and the query methods do not check
  authorisation: against an unauthorised session they return parsed nonsense rather than raising.
  `../boinc.py` calls `authorize()` and checks its return value before querying.
- `_write()` calls `drain()` before writing instead of after, and the loop in `receive()` is dead
  code because `readuntil` already stops at the separator. Both harmless.
- The three `set_*_mode()` methods pass a number where `ET.SubElement` wants a tag name. Only
  affects the write path, which this add-on does not use. Fixed downstream in the HACS integration
  as `str(duration)` if it is ever needed.

## Upstream is dormant

Last commit 2022-10-16. PR #4, from the author of the HACS integration, has been open since
2023-05-22; issue #5 has been unanswered since 2023-09. Publishing a maintained fork to PyPI is
recorded as a future item in the repository `TODO.md` — it is what a future Home Assistant core
integration would need, since core requires a pinned PyPI release.

#!/bin/sh
#
# Put the Space's Hugging Face runtime variables in the page, then serve it.
#
# This is the same move `telepresence`'s `server.mjs` makes, and for the same reason. A
# `sdk: static` Space is served with a `window.huggingface.variables` object spliced into its
# `<head>` — the OAuth client id, the scopes the app was provisioned with, the provider URL — and
# every Hugging Face client library reads the sign-in out of it. A `sdk: docker` Space gets those
# same values as environment variables and no injection at all, so the page has to do it itself.
# Reproducing the object verbatim, rather than substituting one value into a placeholder, is what
# lets `auth.ts` be ordinary `@huggingface/hub` code with nothing Space-shaped about it.
#
# It also keeps the property the placeholder was chosen for: the injection is ours, out of this
# container's own environment, and depends on nothing on Hugging Face's side that can silently
# stop happening.
#
# `OAUTH_CLIENT_SECRET` is in this environment too and is deliberately not in the list below. The
# browser flow is PKCE and needs no secret; the client id authorises nothing and is public.
set -eu

if [ -z "${OAUTH_CLIENT_ID:-}" ]; then
    # Not fatal. The page says so itself and offers `?client_id=`, and a playground that serves
    # and explains beats one that will not start. The likeliest cause is `hf_oauth: true` missing.
    echo "no OAUTH_CLIENT_ID in the environment; nobody will be able to sign in" >&2
fi

mkdir -p /srv

# Python rather than `sed`, because the value being substituted is now JSON: a provider URL is
# full of the characters a `sed` replacement treats as syntax, and one of them silently produces
# a page that parses and signs nobody in.
python3 - /app/index.html /srv/index.html <<'PY'
import json
import os
import re
import sys

# Only what a static Space exposes to the page. Anything absent is left out rather than emitted
# as null, so a reader's `||` fallback fires the way it would on a static Space.
PUBLIC = ("OAUTH_CLIENT_ID", "OAUTH_SCOPES", "OPENID_PROVIDER_URL", "SPACE_HOST", "SPACE_ID")

# **The opening tag on a line of its own, not the first `<head>` in the file.** The page's own
# comments talk about `<head>` — that skeleton being load-bearing is the whole reason it has
# any — and a plain first-match replace puts the bootstrap *inside an HTML comment*, where it
# never runs. The page then looks exactly like a Space with no OAuth app, which is the failure
# those comments are a record of. Anchored, and required to match once.
HEAD = re.compile(r"^([ \t]*)<head>[ \t]*$", re.MULTILINE)

variables = {name: os.environ[name] for name in PUBLIC if os.environ.get(name)}
bootstrap = "<script>window.huggingface=%s;</script>" % json.dumps({"variables": variables})

source, target = sys.argv[1], sys.argv[2]
page = open(source, encoding="utf-8").read()
found = HEAD.search(page)
if found is None:
    sys.exit("no <head> line to inject into; the page cannot sign anybody in")
if HEAD.search(page, found.end()) is not None:
    sys.exit("more than one <head> line; refusing to guess which one serves the page")

indent = found.group(1)
open(target, "w", encoding="utf-8").write(
    page[: found.start()] + indent + "<head>" + bootstrap + page[found.end() :]
)
PY

echo "serving the playground on 7860 (oauth client ${OAUTH_CLIENT_ID:-none})"
exec python3 -m http.server 7860 --directory /srv

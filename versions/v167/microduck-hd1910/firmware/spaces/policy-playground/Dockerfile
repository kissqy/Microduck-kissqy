# A page that needs a server only so it can read its own Hugging Face runtime variables.
#
# **Why Docker rather than a static Space.** A static Space is documented to inject
# `window.huggingface.variables`, and for `microduck-console` it never did — through a rebuild, a
# privacy flip, a recreation, and a page given a real `<head>` to be injected into. Its
# Dockerfile records that afternoon, and this takes the same way out, which is also the one the
# `telepresence` Space takes: `hf_oauth: true` puts the values in the environment and
# `entrypoint.sh` writes that same object into the page itself. That depends on nothing on
# Hugging Face's side that can silently stop happening.
#
# **And no build step here.** The page is built by `npm run build` in `web/` and committed as one
# self-contained `index.html`, so this image copies a file rather than installing a toolchain.
# `scripts/publish-space.sh` publishes the top level of a `spaces/<name>/` directory, which is
# exactly what that produces.
FROM python:3.13-slim

# `python -m http.server` is the whole server: one file, GET only, no upload path, no config.
WORKDIR /app
COPY index.html /app/index.html
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# HF's default for a Docker Space, and `app_port` in the README says the same number.
EXPOSE 7860

ENTRYPOINT ["/app/entrypoint.sh"]

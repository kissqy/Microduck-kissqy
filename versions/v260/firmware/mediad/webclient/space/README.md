---
title: microduck console
emoji: 🦆
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
hf_oauth: true
hf_oauth_expiration_minutes: 1440
short_description: Drive a duck that is not on your network.
tags:
 - microduck
 - webrtc
---

# microduck console

Drives a duck that is not on your network. Sign in with Hugging Face, and the robots your account
owns appear — the same console page the robot serves on its own LAN, reaching it through the
rendezvous service instead of a WebSocket.

**`hf_oauth: true` is load-bearing**: it is what creates the OAuth app whose client id and scopes
this Space receives in its environment, and `entrypoint.sh` writes into the page as it serves it.
Without it the console cannot sign anybody in, and says so.

**Docker rather than static, and that is a scar.** A static Space is documented to inject
`window.huggingface.variables` into the page — and for this Space it never did, through a metadata
change, a privacy flip, a delete-and-recreate, and a page given a real `<head>` for the injector
to work on. So the container writes that same object itself, out of the environment `hf_oauth:
true` provides, which is what `telepresence`'s `server.mjs` does and why its sign-in works from
the Hugging Face page. A page that needs no server got one for exactly that reason.

`openid profile` is all this asks for, and it is read from `OAUTH_SCOPES` rather than written into
the page, because that variable is Hugging Face reporting back what it provisioned this Space's
app with. The token's whole job is proving an identity to the rendezvous service, which resolves
it through `whoami-v2` and reads the username out of the answer. Asking a browser for repository
scopes would be the mistake `remote-access-design.md` §2.4 is about fixing on the robot.

**A sign-in lasts `hf_oauth_expiration_minutes` and no longer.** The page remembers one in
`localStorage` and checks its expiry before offering it to the rendezvous; a token past it counts
as no sign-in, so the console asks for a fresh one rather than reporting that your duck is not
there.

**Do not edit this Space directly.** The page is
[`mediad/webclient/index.html`](https://github.com/pollen-robotics/microduck/blob/main/mediad/webclient/index.html)
in `pollen-robotics/microduck`, and `scripts/publish-console.sh` is what puts it here. It has to
live there because it tracks two things that do: the signalling protocol and the robot's own method
names. `remote-access-design.md` §5.

One page, two transports. Served by a robot, it opens `ws://<robot>:8443`. Served from here — over
https, where a browser will not open a `ws://` at all — it reads the rendezvous service's event
stream and posts back to it, carrying the same envelopes with per-hop ids.

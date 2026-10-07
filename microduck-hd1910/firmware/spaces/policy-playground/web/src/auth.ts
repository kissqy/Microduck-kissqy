/**
 * Signing in with Hugging Face, from the page, with no secret anywhere near it.
 *
 * PKCE: the browser proves it started the flow, so the app needs no client secret and this page
 * can be read by anybody. `OAUTH_CLIENT_SECRET` is in the Space's environment and must never
 * reach here — `entrypoint.sh` publishes only the variables a static Space publishes, and that
 * is not one of them.
 *
 * **The same process as the `telepresence` Space**, whose sign-in works from the Hugging Face
 * page while this one's did not. Both are Docker Spaces, so neither gets the
 * `window.huggingface.variables` object a static Space is served with; both therefore write it
 * themselves out of the environment `hf_oauth: true` provides — `server.mjs` there,
 * `entrypoint.sh` here. What that buys is below: the app id *and the scopes the app was
 * provisioned with* come from one place, and this file is then ordinary `@huggingface/hub` code.
 *
 * `?client_id=` still overrides, which is how a new app is tried before it is written down
 * anywhere.
 */
import { oauthHandleRedirectIfPresent, oauthLoginUrl } from "@huggingface/hub";

/**
 * Where the sign-in is remembered.
 *
 * `localStorage` rather than `sessionStorage`: the Hugging Face redirect can come back in a new
 * tab, and a session store is empty there — which reads as a sign-in that silently did nothing.
 */
const REMEMBERED = "microduck-playground-oauth-v1";

export interface SignedIn {
  token: string;
  username: string;
}

/** What `entrypoint.sh` injected, in the shape a static Space would have been served with. */
function hfVariables(): Record<string, string> {
  const injected = (window as unknown as { huggingface?: { variables?: Record<string, string> } })
    .huggingface?.variables;
  return injected ?? {};
}

function clientId(): string {
  return new URLSearchParams(location.search).get("client_id")
    || hfVariables().OAUTH_CLIENT_ID
    || "";
}

/**
 * The scopes to ask for.
 *
 * Read rather than assumed, because they are not ours to assume: Hugging Face provisions the
 * Space's OAuth app from the README and reports back in `OAUTH_SCOPES` what it provisioned.
 * `openid profile` stays as the fallback for a page served without the injection — a dev server
 * with `?client_id=` — where there is nothing to read.
 */
function scopes(): string {
  return hfVariables().OAUTH_SCOPES || "openid profile";
}

/** The redirect the OAuth app must have registered, character for character. */
const REDIRECT = location.origin + location.pathname;

interface Named {
  userInfo?: { preferred_username?: string; name?: string };
}

/** What the library hands back from a redirect: the expiry is a `Date` at this point. */
type Fresh = Named & { accessToken: string; accessTokenExpiresAt: Date };

/** The same thing after `localStorage`, where `JSON.stringify` turned that `Date` into an ISO string. */
type Stored = Named & { accessToken: string; accessTokenExpiresAt?: string };

function nameOf(who: Named): string {
  return who.userInfo?.preferred_username || who.userInfo?.name || "you";
}

/**
 * Whether a remembered sign-in is still one.
 *
 * **The expiry was remembered and never read.** An access token from `hf_oauth` lives for
 * `hf_oauth_expiration_minutes` — a day, per the README — and this page stored the whole OAuth
 * result in `localStorage`, expiry included, then handed the token to the rendezvous forever
 * after without ever looking at it. A day later the page still said "signed in as …", because a
 * name is all a stored blob has to offer, and the only sign anything was wrong was the
 * rendezvous declining to name a duck. Nothing on the screen said "sign in again", because
 * nothing on the page knew.
 *
 * The SDK the `telepresence` Space is built on has always enforced this (`lib/token-store.ts`),
 * and that is why signing in there kept working. A token past its expiry is treated as absent,
 * so the page asks for a new one instead of explaining a robot's absence.
 */
function stillValid(stored: Stored, now = Date.now()): boolean {
  if (!stored.accessToken) return false;
  // A blob written before this check existed has no expiry to read. Treated as usable rather
  // than dropped: the rendezvous is the one that decides, and a rollout should not sign
  // everybody out.
  if (!stored.accessTokenExpiresAt) return true;
  const expires = new Date(stored.accessTokenExpiresAt).getTime();
  return Number.isFinite(expires) && expires > now;
}

/**
 * Whether this page is running on somebody's own machine.
 *
 * The gate for the `?token=` shortcut below, and the reason it is a gate: a token in a query
 * string ends up in browser history, in a referrer, and in whatever proxy sits between. On
 * localhost there is none of that and the alternative is registering an OAuth app to look at a
 * page. On a published Space it would be a live credential pasted into an address bar, so there
 * it does not exist at all.
 */
function onThisMachine(): boolean {
  return ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
}

/**
 * Consume a redirect if this page load is one, before anything else runs.
 *
 * Called first thing: a page holding a fresh `?code=` has one chance to exchange it, and anything
 * that re-renders or re-navigates first throws it away.
 */
export async function completeSignIn(): Promise<SignedIn | null> {
  // **`?token=` is for a local run and nowhere else.** `hf auth login` already stored one —
  // `cat ~/.cache/huggingface/token` — and pasting it is a great deal less ceremony than
  // registering an OAuth app whose redirect URI is a dev server. Off localhost this branch is
  // not reachable, whatever the URL says.
  const pasted = new URLSearchParams(location.search).get("token");
  if (pasted && onThisMachine()) {
    return { token: pasted, username: "you (a token from the address bar)" };
  }

  let result: Fresh | null = null;
  try {
    result = ((await oauthHandleRedirectIfPresent()) || null) as Fresh | null;
  } catch {
    result = null;
  }
  if (result) {
    localStorage.setItem(REMEMBERED, JSON.stringify(result));
    history.replaceState(null, "", REDIRECT);
    return { token: result.accessToken, username: nameOf(result) };
  }

  const remembered = localStorage.getItem(REMEMBERED);
  if (!remembered) return null;
  let stored: Stored;
  try {
    stored = JSON.parse(remembered) as Stored;
  } catch {
    forgetSignIn();
    return null;
  }
  if (!stillValid(stored)) {
    forgetSignIn();
    return null;
  }
  return { token: stored.accessToken, username: nameOf(stored) };
}

/** Send the visitor to Hugging Face. This page is replaced, so nothing after it runs. */
export async function beginSignIn(): Promise<void> {
  const id = clientId();
  if (!id) {
    throw new Error(
      "This page has no Hugging Face app id, so it cannot sign anybody in. On a Space that " +
        "arrives from `hf_oauth: true` in the README; anywhere else, pass `?client_id=`.",
    );
  }
  location.href = await oauthLoginUrl({
    clientId: id,
    redirectUrl: REDIRECT,
    scopes: scopes(),
  });
}

export function forgetSignIn(): void {
  localStorage.removeItem(REMEMBERED);
}

/** Whether signing in is possible at all here, so the page can say so rather than fail on a press. */
export function canSignIn(): boolean {
  return Boolean(clientId());
}

/** What to tell somebody running this locally with no OAuth app, which is the usual case. */
export function localHint(): string | null {
  if (!onThisMachine() || canSignIn()) return null;
  return "Running locally: add ?token=<your Hugging Face token> to the address bar. " +
    "`cat ~/.cache/huggingface/token` is the one `hf auth login` stored.";
}

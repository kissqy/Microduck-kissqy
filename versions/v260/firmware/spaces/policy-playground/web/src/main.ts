/**
 * The playground: pick a trick, watch your duck do it.
 *
 * **Written for a ten-year-old**, which is a constraint on the whole file and not a coat of paint.
 * Nothing on the page names a method, a transport, a socket or a schema. A trick has a name, a
 * sentence about what it does, and one button. What the four calls are, which lane they take and
 * why a refusal happened lives in *What just happened?* at the bottom, which is where you go when
 * something breaks rather than when you want to see a duck bow.
 *
 * The press has stages, and they are shown on the card that was pressed rather than in a line
 * somewhere else on the page:
 *
 *     getting it → putting it on your duck → waiting for your duck → doing it
 *
 * and the rest of the page is inert while one is in flight. A robot can only do one thing at a
 * time, so a page that accepted a second press would be promising something it cannot keep.
 */
import { beginSignIn, canSignIn, completeSignIn, forgetSignIn, localHint, type SignedIn } from "./auth";
import { howLong, isATrick, needsALength, notATrick, readHub, skillFor, type Policy } from "./hub";
import { listDucks, Session, type Robot } from "./rendezvous";
import "./style.css";

/** How long to hold a trick that has no length of its own. Perpetual means "until told otherwise". */
const HOLD_SECONDS = 3;

/** A download over the duck's own wifi, not a question about state. */
const FETCH_TIMEOUT = 180_000;

/**
 * How long to wait for a duck that is going back to its standing pose.
 *
 * Putting a trick on a duck makes it reload, and a reloading duck refuses to do anything until it
 * is standing again — so the press that installs is the press that gets refused. `homed` on
 * `robot.policies` is the flag to wait on; a duck too old to publish it sends nothing, and then
 * there is nothing to wait for.
 */
const HOME_TIMEOUT = 15_000;

interface State {
  signedIn: SignedIn | null;
  ducks: Robot[];
  chosen: string | null;
  session: Session | null;
  duckName: string | null;
  /**
   * Whether the policy is driving, from `robot.policies`.
   *
   * Not a belief this page keeps: the robot owns it, and anything else can change it — the pad,
   * a relax, either side restarting. A client that remembered its own answer would show a Start
   * button that does nothing every other press, which is the reason `robot.enable` has a `toggle`.
   */
  enabled: boolean | null;
  /** Parked in its seat, from `robot.policies`. `null` is a duck too old to say. */
  sitting: boolean | null;
  /**
   * What the duck has, and which of those this page may take off again.
   *
   * `overridden` on `robot.skills` is the difference: a skill that came from the robot's config
   * is one somebody added and can remove, and a shipped one is part of the release. Offering to
   * delete a shipped skill would be offering something the daemon will refuse.
   */
  onTheDuck: Array<{ name: string; removable: boolean }>;
  policies: Policy[];
  trouble: string | null;
  busy: string | null;
  stage: string | null;
  said: string | null;
  /**
   * Which card the message belongs to, or `null` for the page.
   *
   * **The Gradio page printed every answer in one line at the top, two thousand pixels from the
   * button, and that is why a refusal read as a button that did nothing.** Rebuilding that here
   * took one afternoon: "Getting it…" flipped back to "Teach my duck" and the reason was on
   * screen, above the fold, unread. An answer belongs where the question was asked.
   */
  saidFor: string | null;
  log: string[];
}

const state: State = {
  signedIn: null,
  ducks: [],
  chosen: null,
  session: null,
  duckName: null,
  enabled: null,
  sitting: null,
  onTheDuck: [],
  policies: [],
  trouble: null,
  busy: null,
  stage: null,
  said: null,
  saidFor: null,
  log: [],
};

function note(line: string): void {
  const stamp = new Date().toLocaleTimeString();
  state.log.push(`${stamp}  ${line}`);
  if (state.log.length > 400) state.log.shift();
  const panel = document.querySelector<HTMLPreElement>("#log");
  if (panel) {
    panel.textContent = state.log.join("\n");
    panel.scrollTop = panel.scrollHeight;
  }
}

const sleep = (ms: number): Promise<void> => new Promise((done) => window.setTimeout(done, ms));

// ── talking to the duck ──────────────────────────────────────────────────────

async function connect(): Promise<void> {
  const token = state.signedIn?.token;
  const peerId = state.chosen;
  if (!token || !peerId) return;
  const duck = state.ducks.find((d) => d.peerId === peerId);
  state.busy = "connecting";
  render();
  try {
    const session = new Session(token, peerId, "microduck-policy-playground", note);
    await session.start();
    state.session = session;
    state.duckName = duck?.name ?? "your duck";
    state.said = `${state.duckName} is ready.`;
    state.saidFor = null;
    await readTheDuck();
  } catch (e) {
    state.said = `Could not reach your duck. ${e instanceof Error ? e.message : String(e)}`;
    state.saidFor = null;
    note(String(e));
  } finally {
    state.busy = null;
    render();
  }
}

async function disconnect(): Promise<void> {
  await state.session?.stop();
  state.session = null;
  state.duckName = null;
  state.enabled = null;
  state.sitting = null;
  state.onTheDuck = [];
  state.said = "Let go of your duck.";
  state.saidFor = null;
  render();
}

/** What the duck already knows, which is the shelf at the top of the page. */
async function readTheDuck(): Promise<void> {
  const session = state.session;
  if (!session) return;
  try {
    const policies = (await session.call("robot.policies")) as Record<string, unknown>;
    state.enabled = typeof policies.enabled === "boolean" ? policies.enabled : null;
    state.sitting = typeof policies.sitting === "boolean" ? policies.sitting : null;
    const table = (await session.call("robot.skills")) as Record<string, unknown>;
    const skills = Array.isArray(table.skills) ? (table.skills as Record<string, unknown>[]) : [];
    const builtIn = Array.isArray(table.built_in) ? (table.built_in as string[]) : [];
    state.onTheDuck = [
      ...skills.map((skill) => ({
        name: String(skill.name),
        removable: Boolean(skill.overridden),
      })),
      // The daemon drives these itself — `ground_pick` writes a scripted phase, `sit_toggle` is
      // latched — so they can be asked for and never taken away.
      ...builtIn.map((name) => ({ name, removable: false })),
    ];
  } catch (e) {
    note(`could not read the duck: ${e}`);
  }
}

/**
 * Wait until the duck will accept a trick.
 *
 * `accepted: false` with a reason is a normal answer, not a failure — and "still going to its home
 * pose" is the one reason that clears by itself. Asking `homed` rather than reading the sentence
 * means the wait ends when the duck is ready instead of when a timer says so.
 */
async function waitForHome(): Promise<void> {
  const session = state.session;
  if (!session) return;
  const deadline = Date.now() + HOME_TIMEOUT;
  while (Date.now() < deadline) {
    let homed: unknown;
    try {
      homed = ((await session.call("robot.policies")) as Record<string, unknown>).homed;
    } catch {
      return;
    }
    if (homed === undefined || homed === null) {
      note("this duck does not say whether it is standing yet, so there is nothing to wait for");
      return;
    }
    if (homed) return;
    await sleep(500);
  }
  note(`gave up waiting for the duck to stand after ${HOME_TIMEOUT / 1000}s`);
}

/** `accepted: false` carries the reason; `accepted: true` with one means it was already done. */
function refusal(result: unknown): string | null {
  if (typeof result !== "object" || result === null || !("accepted" in result)) return null;
  const answer = result as { accepted?: unknown; reason?: unknown };
  if (answer.accepted) return null;
  return String(answer.reason ?? "your duck said no, without saying why");
}

/**
 * A refusal, said to somebody who is ten.
 *
 * The daemon writes for whoever is reading a journal: `network error: Teethyfish/microduck-… will
 * not run on this robot: it is for a microduck full_shell, and this is a microduck`. Three
 * true things — a repo id, an error class that is not what happened, and one sentence a child
 * could act on. This keeps the sentence.
 *
 * Nothing is invented and nothing is swallowed: the whole message is in the log, every time.
 */
function inWords(e: unknown, policy: Policy): string {
  const raw = e instanceof Error ? e.message : String(e);
  const mismatch = /it is for an? (.+?), and this is an? (.+?)$/.exec(raw);
  if (mismatch) return `${policy.name} is made for a ${mismatch[1]}, and yours is a ${mismatch[2]}.`;
  // The daemon calls every refusal it raises a "network error", including the ones that are
  // nothing of the kind. Dropping the prefix is the honest half of that; the other half is a
  // change to the daemon.
  return raw.replace(/^network error: /, "").replace(`${policy.repo} `, "");
}

async function putOnDuck(policy: Policy): Promise<void> {
  const session = state.session;
  if (!session) {
    state.said = "Wake your duck up first.";
    state.saidFor = policy.key;
    render();
    return;
  }
  const blocked = notATrick(policy);
  if (blocked) {
    state.said = blocked;
    state.saidFor = policy.key;
    render();
    return;
  }

  note(`pressed: ${policy.name} (${policy.key})`);
  if (state.saidFor === policy.key) state.said = null;
  state.busy = policy.key;
  try {
    state.stage = "Getting it…";
    render();
    const params: Record<string, unknown> = { repo: policy.repo };
    if (policy.file) params.file = policy.file;
    const fetched = (await session.call("policy.fetch", params, FETCH_TIMEOUT)) as Record<string, unknown>;

    state.stage = "Putting it on your duck…";
    render();
    const skill = skillFor(fetched, HOLD_SECONDS);
    const added = await session.call("robot.setSkill", skill);
    const notAdded = refusal(added);
    if (notAdded) throw new Error(notAdded);

    // Accepted is not installed: `setSkill` triggers a reload, and a reload that failed says so
    // here and nowhere else.
    const after = (await session.call("robot.policies")) as Record<string, unknown>;
    if (after.change_error) throw new Error(String(after.change_error));

    await readTheDuck();
    state.said = `It is on your duck. Press it up in “On your duck”.`;
    state.saidFor = policy.key;
  } catch (e) {
    state.said = `That did not work: ${inWords(e, policy)}`;
    state.saidFor = policy.key;
  } finally {
    state.busy = null;
    state.stage = null;
    render();
  }
}

async function doAgain(name: string): Promise<void> {
  const session = state.session;
  if (!session) return;
  state.busy = `again:${name}`;
  state.stage = "Doing it!";
  render();
  try {
    await waitForHome();
    const ran = await session.call("robot.do", { skill: name });
    const notRun = refusal(ran);
    state.said = notRun ? `It would not do it: ${notRun}` : `${name}!`;
    state.saidFor = `again:${name}`;
  } catch (e) {
    state.said = `It would not do it: ${e instanceof Error ? e.message : String(e)}`;
    state.saidFor = `again:${name}`;
  } finally {
    state.busy = null;
    state.stage = null;
    render();
  }
}

async function takeOff(name: string): Promise<void> {
  const session = state.session;
  if (!session) return;
  note(`taking ${name} off the duck`);
  state.busy = `off:${name}`;
  state.stage = "Taking it off…";
  render();
  try {
    const gone = await session.call("robot.removeSkill", { name });
    const refused = refusal(gone);
    state.said = refused ? `Could not take ${name} off: ${refused}` : `${name} is off your duck.`;
    await readTheDuck();
  } catch (e) {
    state.said = `Could not take ${name} off: ${e instanceof Error ? e.message : String(e)}`;
  } finally {
    state.saidFor = "shelf";
    state.busy = null;
    state.stage = null;
    render();
  }
}

/**
 * The three things a duck needs doing to it that are not tricks.
 *
 * `robot.init` stands it up and is never refused, whatever it is lying on. `robot.enable` is the
 * pad's Start, and the page only offers it when the duck says the policy is *not* driving —
 * because that is the one state where pressing it means something, and a button that is usually a
 * no-op is a button nobody trusts.
 *
 * `robot.relax` is deliberately absent. It cuts torque and the duck drops where it stands, which
 * `robotctl` guards with `--yes` and BLE refuses to carry at all. On a page built for a child it
 * would be a button that looks like "have a rest" and is in fact "fall over".
 */
async function duckCommand(
  method: string,
  saying: string,
  params: Record<string, unknown> = {},
): Promise<void> {
  const session = state.session;
  if (!session) return;
  state.busy = `cmd:${method}`;
  state.stage = saying;
  render();
  try {
    const answer = await session.call(method, params);
    const refused = refusal(answer);
    state.said = refused ?? null;
    await readTheDuck();
  } catch (e) {
    state.said = `${saying} did not work: ${e instanceof Error ? e.message : String(e)}`;
  } finally {
    state.saidFor = state.said ? "duck" : null;
    state.busy = null;
    state.stage = null;
    render();
  }
}

async function startPolicy(): Promise<void> {
  const session = state.session;
  if (!session) return;
  state.busy = "cmd:enable";
  state.stage = "Starting…";
  render();
  try {
    // `on: true` rather than the toggle: the page has just read the state and knows it is off, so
    // asking for the state it wants beats asking for "the other one" and racing the pad.
    const answer = await session.call("robot.enable", { on: true, toggle: false });
    const refused = refusal(answer);
    state.said = refused ?? null;
    await readTheDuck();
  } catch (e) {
    state.said = `Could not start it: ${e instanceof Error ? e.message : String(e)}`;
  } finally {
    state.saidFor = state.said ? "duck" : null;
    state.busy = null;
    state.stage = null;
    render();
  }
}

function duckControls(): HTMLElement | null {
  if (!state.session) return null;
  const row = el("div", "controls");
  const busy = state.busy !== null;

  if (state.enabled === false) {
    const start = el("button", "control control-start",
      state.busy === "cmd:enable" ? (state.stage ?? "…") : "Start it");
    start.disabled = busy;
    start.addEventListener("click", () => void startPolicy());
    row.append(start);
    row.append(el("span", "hint", "Your duck is switched off — start it, then stand it up."));
  }

  // **Two calls behind one button, and the duck says which.** A duck on its feet stands with
  // `robot.init`. A duck in its seat is held there by the `sit_toggle` latch the daemon drives —
  // `init` argues with that rather than winning, which is a robot visibly fighting itself. A duck
  // too old to report `sitting` sends `init`, which is what every client did before this existed.
  const seated = state.sitting === true;
  const stand = el("button", "control control-stand",
    state.busy?.startsWith("cmd:") && state.busy !== "cmd:enable" && state.busy !== "cmd:robot.stop"
      ? (state.stage ?? "…")
      : seated ? "Get up" : "Stand up");
  stand.disabled = busy;
  stand.addEventListener("click", () =>
    void (seated
      ? duckCommand("robot.do", "Getting up…", { skill: "sit_toggle" })
      : duckCommand("robot.init", "Standing up…")));
  row.append(stand);

  const stop = el("button", "control control-stop",
    state.busy === "cmd:robot.stop" ? (state.stage ?? "…") : "Stop");
  stop.disabled = busy;
  stop.addEventListener("click", () => void duckCommand("robot.stop", "Stopping…"));
  row.append(stop);

  if (state.saidFor === "duck" && state.said) row.append(el("p", "card-said", state.said));
  return row;
}

// ── the page ─────────────────────────────────────────────────────────────────

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/**
 * The name this policy takes once it is on the duck.
 *
 * `skillFor` builds it from the *fetched* manifest, which this page has not read yet — so this is
 * the same transformation applied to the name the catalogue already has. It agrees for every
 * policy published so far, because both start from the manifest's `name`; where it does not, the
 * card simply does not say "on your duck", which is a missing tick rather than a wrong one.
 */
function skillName(policy: Policy): string {
  return policy.name.replaceAll(" ", "-");
}

/**
 * Two names for the same trick, compared the way a person would.
 *
 * The duck's shipped skills are `kick_left` and `roulade`; a community one installed from here is
 * `polite-bow`; and the catalogue has already turned both separators into spaces to make a card
 * heading. Comparing any two of those literally says they are different tricks, and the tick that
 * says "you already have this" never appears on the three every duck ships with.
 */
const sameTrick = (name: string): string => name.toLowerCase().replace(/[-_\s]+/g, "-");

function alreadyOn(policy: Policy): boolean {
  const wanted = sameTrick(skillName(policy));
  return state.onTheDuck.some((skill) => sameTrick(skill.name) === wanted);
}

function card(policy: Policy): HTMLElement {
  // Either reason not to offer a button: the daemon drives it, or it has no ending. The card says
  // which, in the same place, because to a reader they are the same answer — "not this one".
  const blocked =
    notATrick(policy) ??
    (isATrick(policy) ? null : "This one keeps going rather than finishing, so it is not a trick.");
  const node = el("article", `card${blocked ? " card-blocked" : ""}`);
  // **The clip first, because it is the answer to the question the card exists to ask.** A name
  // and a sentence are a guess at what a trick looks like; five seconds of a duck doing it is not.
  // `preload="metadata"` and no autoplay: thirteen videos playing at once is a page that fights
  // the wifi somebody is also using to reach their robot.
  if (policy.video) {
    const clip = el("video", "card-clip");
    clip.src = policy.video;
    clip.controls = true;
    clip.muted = true;
    clip.loop = true;
    clip.playsInline = true;
    clip.preload = "metadata";
    node.append(clip);
  }
  node.append(el("h3", "card-name", policy.name));
  node.append(el("p", "card-what", policy.description ?? "Nobody wrote down what this one does."));

  const facts = el("p", "card-facts");
  facts.append(el("span", "chip", howLong(policy)));
  if (policy.official) facts.append(el("span", "chip chip-official", "made by Pollen"));
  if (alreadyOn(policy)) facts.append(el("span", "chip chip-live", "✓ on your duck"));

  // Who made it, and a way to go and look. A trick is somebody's work — often somebody a child
  // could plausibly meet — and the repo page is where the training, the manifest and the person
  // are. `target="_blank"` because leaving the page would drop the session with the duck.
  const who = el("a", "chip chip-link", `by ${policy.repo.split("/")[0]}`);
  who.href = `https://huggingface.co/${policy.repo}`;
  who.target = "_blank";
  who.rel = "noopener noreferrer";
  who.title = policy.repo;
  facts.append(who);
  if (policy.forRobot) facts.append(el("span", "chip chip-bad", `for a ${policy.forRobot}`));
  if (needsALength(policy) && !blocked) facts.append(el("span", "chip", `held for ${HOLD_SECONDS}s`));
  node.append(facts);

  if (blocked) {
    node.append(el("p", "card-blocked-why", blocked));
    return node;
  }

  const mine = state.busy === policy.key;
  // A trick already on the duck keeps its button — pressing it again fetches the current file and
  // replaces what is there, which is how somebody picks up a policy that has been retrained. But
  // it stops shouting: the loud yellow one is for tricks the duck does not have yet.
  const on = alreadyOn(policy);
  const button = el(
    "button",
    on ? "go go-again" : "go",
    mine ? (state.stage ?? "…") : on ? "Get it again" : "Put it on my duck",
  );
  button.disabled = !state.session || state.busy !== null;
  if (mine) button.classList.add("go-busy");
  button.addEventListener("click", () => void putOnDuck(policy));
  node.append(button);
  if (state.saidFor === policy.key && state.said) node.append(el("p", "card-said", state.said));
  return node;
}

function header(): HTMLElement {
  const bar = el("header", "bar");
  bar.append(el("h1", "title", "🦆 Duck tricks"));

  const right = el("div", "bar-right");
  if (!state.signedIn) {
    const button = el("button", "primary", "Sign in with Hugging Face");
    button.disabled = !canSignIn();
    button.addEventListener("click", () => void beginSignIn());
    right.append(button);
    const hint = localHint();
    if (hint) right.append(el("span", "chip chip-bad", "no app id — see below"));
    else if (!canSignIn()) right.append(el("span", "chip chip-bad", "no app id on this page"));
  } else if (!state.session) {
    const picker = el("select", "picker");
    if (state.ducks.length === 0) {
      picker.append(new Option("no ducks awake", ""));
      picker.disabled = true;
    }
    for (const duck of state.ducks) {
      picker.append(new Option(duck.busy ? `${duck.name} (busy)` : duck.name, duck.peerId));
    }
    picker.value = state.chosen ?? "";
    picker.addEventListener("change", () => {
      state.chosen = picker.value || null;
    });
    right.append(picker);

    const find = el("button", "", "Look again");
    find.addEventListener("click", () => void findDucks());
    right.append(find);

    const join = el("button", "primary", state.busy === "connecting" ? "Connecting…" : "Wake it up");
    join.disabled = !state.chosen || state.busy !== null;
    join.addEventListener("click", () => void connect());
    right.append(join);
  } else {
    right.append(el("span", "chip chip-live", `${state.duckName} is listening`));
    const leave = el("button", "", "Let go");
    leave.disabled = state.busy !== null;
    leave.addEventListener("click", () => void disconnect());
    right.append(leave);
  }
  bar.append(right);
  return bar;
}

/**
 * What the duck can do right now — the top of the page, in big buttons.
 *
 * **This is what the page is for.** A ten-year-old with a duck and a friend standing next to them
 * wants one press and a duck doing something, and everything else — the Hub, the manifests, the
 * downloading — is what you do once so that this row exists. So it is first, it is large, and the
 * catalogue below is called "get more tricks" rather than being the page itself.
 */
function shelf(): HTMLElement | null {
  if (!state.session) return null;
  const box = el("section", "shelf");
  box.append(el("h2", "shelf-title", "On your duck"));
  if (state.onTheDuck.length === 0) {
    box.append(el("p", "hint", "Nothing yet. Pick a trick below and put it on."));
    return box;
  }

  const row = el("div", "shelf-row");
  for (const { name, removable } of state.onTheDuck) {
    const tile = el("div", "tile");
    const doing = state.busy === `again:${name}`;
    const go = el("button", "tile-go", doing ? (state.stage ?? "…") : name);
    go.disabled = state.busy !== null;
    go.addEventListener("click", () => void doAgain(name));
    tile.append(go);
    // Only what somebody added can be taken off. A shipped skill is part of the release, and a
    // cross beside it would be offering something the daemon refuses.
    if (removable) {
      const off = el("button", "tile-off", "✕");
      off.title = `Take ${name} off your duck`;
      off.disabled = state.busy !== null;
      off.addEventListener("click", () => void takeOff(name));
      tile.append(off);
    }
    row.append(tile);
  }
  box.append(row);
  if ((state.saidFor === "shelf" || state.saidFor?.startsWith("again:")) && state.said) {
    box.append(el("p", "card-said", state.said));
  }
  return box;
}

function render(): void {
  const root = document.querySelector<HTMLDivElement>("#app");
  if (!root) return;
  root.replaceChildren();
  root.append(header());

  if (state.said && state.saidFor === null) root.append(el("p", "said", state.said));

  if (!state.session) {
    root.append(
      el(
        "p",
        "hint",
        state.signedIn
          ? "Pick your duck and wake it up, then choose a trick."
          : (localHint() ??
              "Sign in to find your duck. You will only see robots your own account owns."),
      ),
    );
  }

  const controls = duckControls();
  if (controls) root.append(controls);

  const known = shelf();
  if (known) root.append(known);

  const tricks = el("section", "tricks");
  tricks.append(el("h2", "", "Get more tricks"));
  if (state.trouble) tricks.append(el("p", "hint", state.trouble));
  const grid = el("div", "grid");
  for (const policy of state.policies.filter(isATrick)) grid.append(card(policy));
  tricks.append(grid);
  root.append(tricks);

  // **Listed rather than hidden, and not offered as something to press.** These are the gaits and
  // the postures — the things a duck moves *with* rather than things it can show you. Leaving them
  // in the same grid put "alpha walking" beside "polite bow" with an identical button, which is a
  // page telling a child they are the same kind of thing.
  const rest = state.policies.filter((p) => !isATrick(p));
  if (rest.length) {
    const box = el("details", "rest");
    box.append(el("summary", "", `Part of how your duck moves (${rest.length})`));
    box.append(
      el("p", "hint", "These are not tricks. They are how your duck walks, stands and picks things up."),
    );
    const list = el("div", "grid");
    for (const policy of rest) list.append(card(policy));
    box.append(list);
    root.append(box);
  }

  const details = el("details", "log-box");
  details.append(el("summary", "", "What just happened?"));
  const pre = el("pre", "");
  pre.id = "log";
  pre.textContent = state.log.join("\n");
  details.append(pre);
  root.append(details);
}

async function findDucks(): Promise<void> {
  const token = state.signedIn?.token;
  if (!token) return;
  try {
    const { ducks, others } = await listDucks(token);
    state.ducks = ducks;
    state.chosen = ducks[0]?.peerId ?? null;
    if (ducks.length === 0) {
      state.said = others.length
        ? `No ducks awake. ${others.length} other robot(s) are, but they are not ducks.`
        : "No ducks awake. Turn yours on, and give it a minute to say hello.";
    } else {
      state.said = null;
    }
  } catch (e) {
    state.said = e instanceof Error ? e.message : String(e);
    note(String(e));
  }
  render();
}

async function main(): Promise<void> {
  render();

  state.signedIn = await completeSignIn();
  if (state.signedIn) note(`signed in as ${state.signedIn.username}`);
  render();

  const { policies, trouble } = await readHub();
  state.policies = policies;
  state.trouble = trouble;
  note(`${policies.length} tricks on the Hub`);
  render();

  if (state.signedIn) await findDucks();
}

/**
 * Nothing fails quietly on this page.
 *
 * A thrown error in a click handler goes to the browser console, which nobody has open — and the
 * card just sits there. "I pressed it and nothing happened" is the least debuggable sentence in
 * software, and it is the one this page has already produced once. Every escape becomes a line
 * somebody can read and a line in the log.
 */
window.addEventListener("error", (event) => {
  state.said = `Something went wrong: ${event.message}`;
  note(`uncaught: ${event.message} (${event.filename}:${event.lineno})`);
  render();
});
window.addEventListener("unhandledrejection", (event) => {
  const why = event.reason instanceof Error ? event.reason.message : String(event.reason);
  state.said = `Something went wrong: ${why}`;
  note(`uncaught (in a promise): ${why}`);
  render();
});

void main();

// Signing out is not a button anybody asked for, but a stale token is a 401 nobody can explain.
// `?forget` is the escape hatch, named in the log rather than on the page.
if (new URLSearchParams(location.search).has("forget")) {
  forgetSignIn();
  location.replace(location.pathname);
}

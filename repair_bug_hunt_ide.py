#!/usr/bin/env python3
"""Repair the Bug Hunt problem selector without reloading Vice City."""
from pathlib import Path
import re
import shutil
import subprocess
import sys

PROJECT = Path.home() / "Games" / "reVCDOS"
HTML_PATH = PROJECT / "dist" / "index.html"
MARKER = "BH-INPLACE-PROBLEM-SWITCHER-REPAIR"


def stop(message):
    print(f"STOP: {message}", file=sys.stderr)
    raise SystemExit(1)

if not HTML_PATH.is_file():
    stop(f"Could not find {HTML_PATH}. Edit PROJECT in this script if your repo is elsewhere.")

html = HTML_PATH.read_text(encoding="utf-8")

# Remove a prior copy of this repair script, if the command is run twice.
script_tag_re = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.I | re.S)
for match in reversed(list(script_tag_re.finditer(html))):
    if MARKER in match.group(0):
        html = html[:match.start()] + html[match.end():]

# Find the selector whose options correspond to the two bug IDs.
select_candidates = []
for match in re.finditer(r"<select\b([^>]*)>(.*?)</select\s*>", html, re.I | re.S):
    attrs, body = match.group(1), match.group(2)
    if "inverted-steering" in body and "car-entry-disabled" in body:
        id_match = re.search(r"\bid\s*=\s*(['\"])(.*?)\1", attrs, re.I)
        select_candidates.append((match, id_match.group(2) if id_match else ""))

if not select_candidates:
    stop("Could not locate a dropdown containing both challenge options. No file was changed.")

# Prefer the selector created by the earlier IDE patch.
select_match, select_id = next(
    (candidate for candidate in select_candidates if candidate[1] == "bh-problem-select"),
    select_candidates[0],
)
if not select_id:
    stop("The challenge dropdown has no id; no file was changed.")

if 'id="bug-hunt-ide"' not in html or 'id="bh-source"' not in html:
    stop("Could not locate the IDE panel and source textarea. No file was changed.")

# Save a versioned backup before writing anything.
backup = HTML_PATH.with_name("index.html.before-in-place-problem-switcher.backup")
index = 2
while backup.exists():
    backup = HTML_PATH.with_name(f"index.html.before-in-place-problem-switcher-{index}.backup")
    index += 1
shutil.copy2(HTML_PATH, backup)

controller = r'''<script>
// BH-INPLACE-PROBLEM-SWITCHER-REPAIR
(function () {
    const root = document.getElementById("bug-hunt-ide");
    const select = document.getElementById("__SELECT_ID__");
    if (!root || !select) {
        console.error("[Bug Hunt] Problem selector or IDE panel not found.");
        return;
    }

    const starter = {
        "inverted-steering": `function getSteeringDirection(direction) {
    const normalizedDirection = String(direction).toLowerCase();
    if (normalizedDirection === "left") return "right"; // BUG
    if (normalizedDirection === "right") return "left"; // BUG
    return normalizedDirection;
}`,
        "car-entry-disabled": `function shouldBlockVehicleEntry(key) {
    const normalizedKey = String(key).toLowerCase();
    return normalizedKey === "f" || normalizedKey === "enter"; // BUG
}`
    };

    const definitions = {
        "inverted-steering": {
            title: "Problem 1 — Inverted Steering",
            description: "Left and right steering behave in the opposite direction. Find the faulty direction mapping, fix it, run the tests, and submit your solution."
        },
        "car-entry-disabled": {
            title: "Problem 2 — Vehicle Entry Disabled",
            description: "The player cannot enter a vehicle. Repair the function so pressing F or Enter is not blocked. Run the tests, then submit your fix."
        }
    };

    const textarea = document.getElementById("bh-source");
    const cmWrapper = root.querySelector(".CodeMirror");
    const cm = cmWrapper && cmWrapper.CodeMirror ? cmWrapper.CodeMirror : null;
    function readSource() {
        return cm ? cm.getValue() : (textarea ? textarea.value : "");
    }
    function writeSource(value) {
        if (cm) {
            cm.setValue(value);
            cm.refresh();
        } else if (textarea) {
            textarea.value = value;
        }
    }

    function safeGet(key) {
        try { return localStorage.getItem(key); } catch (_) { return null; }
    }
    function safeSet(key, value) {
        try { localStorage.setItem(key, value); } catch (_) {}
    }

    const valid = value => Object.prototype.hasOwnProperty.call(definitions, value);
    const selectedValue = valid(select.value) ? select.value : null;
    const savedSelection = safeGet("bughunt.activeProblem");
    const params = new URLSearchParams(window.location.search);
    const urlBugs = (params.get("bug") || "").split(",").filter(Boolean);
    const singleUrlProblem = urlBugs.length === 1 && valid(urlBugs[0]) ? urlBugs[0] : null;
    let activeProblem = singleUrlProblem ||
        (valid(savedSelection) ? savedSelection : null) ||
        selectedValue ||
        (urlBugs.includes("car-entry-disabled") ? "car-entry-disabled" : "inverted-steering");
    select.value = activeProblem;
    safeSet("bughunt.activeProblem", activeProblem);
    window.__BH_ACTIVE_PROBLEM = activeProblem;

    const drafts = {};
    drafts[activeProblem] = readSource();
    safeSet("bughunt.problem.draft." + activeProblem, drafts[activeProblem]);

    // Locate the existing challenge card's text nodes so it updates instead of duplicating.
    const leaves = () => Array.from(root.querySelectorAll("*"))
        .filter(node => node.children.length === 0 && node.tagName !== "OPTION");
    let titleNode = leaves().find(node => /^(Challenge\s*0?1\s*[—-]\s*Car Entry|Problem\s*[12]\s*[—-])/i.test(node.textContent.trim()));
    let descriptionNode = leaves().find(node => {
        const t = node.textContent.trim();
        return t.startsWith("The player cannot enter a vehicle") ||
               t.startsWith("Left and right steering behave in the opposite direction.");
    });
    let statusNode = leaves().find(node => /^(Waiting for your fix\.|Tests passed|Tests failed|Test error:)/i.test(node.textContent.trim()));

    function setStatus(message) {
        if (!statusNode || !statusNode.isConnected) {
            statusNode = leaves().find(node => /^(Waiting for your fix\.|Tests passed|Tests failed|Test error:)/i.test(node.textContent.trim()));
        }
        if (statusNode) statusNode.textContent = message;
    }

    function renderProblem() {
        const item = definitions[activeProblem];
        if (titleNode && titleNode.isConnected) titleNode.textContent = item.title;
        if (descriptionNode && descriptionNode.isConnected) descriptionNode.textContent = item.description;
        setStatus("Waiting for your fix.");
        window.__BH_ACTIVE_PROBLEM = activeProblem;
        safeSet("bughunt.activeProblem", activeProblem);
    }

    function persistDraft() {
        drafts[activeProblem] = readSource();
        safeSet("bughunt.problem.draft." + activeProblem, drafts[activeProblem]);
    }
    if (cm) cm.on("change", persistDraft);
    else if (textarea) textarea.addEventListener("input", persistDraft);

    // Rebuild the existing test iframe without reading parent-window properties from its opaque origin.
    const runner = Array.from(document.querySelectorAll("iframe")).find(frame =>
        (frame.getAttribute("srcdoc") || frame.srcdoc || "").includes("bh-run")
    );
    if (runner) {
        runner.srcdoc = '<!doctype html><meta charset="utf-8"><script>' +
        'window.addEventListener("message",function(e){var m=e.data;if(!m||m.type!=="bh-run")return;var steering=/\\bgetSteeringDirection\\s*\\(/.test(m.source);var problem=steering?"inverted-steering":"car-entry-disabled";try{var suffix=steering?"\\n;return [getSteeringDirection(\\"left\\"),getSteeringDirection(\\"right\\")];":"\\n;return [shouldBlockVehicleEntry(\\"f\\"),shouldBlockVehicleEntry(\\"enter\\")];";var r=new Function(m.source+suffix)();var pass=steering?(r[0]==="left"&&r[1]==="right"):(r[0]===false&&r[1]===false);parent.postMessage({type:"bh-result",problem:problem,pass:pass,values:r},"*");}catch(err){parent.postMessage({type:"bh-result",problem:problem,error:String(err)},"*");}});' +
        '<\/script>';
    } else {
        console.warn("[Bug Hunt] Test runner iframe not found; UI switching will still work.");
    }

    // Handle Problem 1 results separately, before the old car-entry result listener.
    let steeringSubmitPending = false;
    const submitButton = Array.from(root.querySelectorAll("button"))
        .find(button => /submit fix/i.test(button.textContent));
    if (submitButton) {
        submitButton.addEventListener("click", function () {
            steeringSubmitPending = activeProblem === "inverted-steering";
        }, true);
    }

    window.addEventListener("message", function (event) {
        const result = event.data;
        if (!result || result.type !== "bh-result" || result.problem !== "inverted-steering") return;
        event.stopImmediatePropagation();

        if (result.error) {
            setStatus("Test error: " + result.error);
            steeringSubmitPending = false;
            return;
        }
        if (!result.pass) {
            setStatus("Tests failed. Check the left/right mapping and try again.");
            steeringSubmitPending = false;
            return;
        }

        setStatus(steeringSubmitPending ? "Fix accepted! Steering tests passed." : "Tests passed. Submit Fix to claim points.");
        if (steeringSubmitPending && safeGet("bughunt.inverted-steering.awarded") !== "1") {
            const points = Number(safeGet("bughunt.points") || 0) + 100;
            safeSet("bughunt.points", String(points));
            safeSet("bughunt.inverted-steering.awarded", "1");
            const pointNode = leaves().find(node => /^\d+$/.test(node.textContent.trim()) && /Local points/i.test(node.parentElement ? node.parentElement.textContent : ""));
            if (pointNode) pointNode.textContent = String(points);
            window.__BUGHUNT_INVERTED_STEERING_FIXED = true;
        }
        steeringSubmitPending = false;
    }, true);

    // Critical: this capture-phase listener prevents the older selector's page-navigation handler.
    // It switches problem, source, description and tests without reloading Vice City.
    select.addEventListener("change", function (event) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const nextProblem = select.value;
        if (!valid(nextProblem) || nextProblem === activeProblem) return;

        persistDraft();
        activeProblem = nextProblem;
        window.__BH_ACTIVE_PROBLEM = activeProblem;
        safeSet("bughunt.activeProblem", activeProblem);

        const saved = drafts[activeProblem] || safeGet("bughunt.problem.draft." + activeProblem);
        writeSource(saved || starter[activeProblem]);
        drafts[activeProblem] = readSource();
        renderProblem();
        safeSet("bughunt.problem.draft." + activeProblem, drafts[activeProblem]);
        console.log("[Bug Hunt] Switched IDE challenge in place:", definitions[activeProblem].title);
    }, true);

    renderProblem();
    console.log("[Bug Hunt] In-place problem selector ready. Vice City will not reload when switching.");
})();
</script>'''.replace("__SELECT_ID__", select_id)

# Insert the repair after all existing IDE scripts so it can override the previous selector behavior.
if "</body>" not in html:
    stop("Could not find </body>. No file was changed.")
html = html.replace("</body>", "\n" + controller + "\n</body>", 1)

# Validate the injected script before saving the edited HTML.
scripts = re.findall(r"<script\b([^>]*)>(.*?)</script\s*>", html, re.I | re.S)
repair_scripts = [body for _, body in scripts if MARKER in body]
if len(repair_scripts) != 1:
    stop("Could not validate the new repair script. Original HTML remains unchanged.")

check_path = Path("/tmp/bh-in-place-problem-switcher.js")
check_path.write_text(repair_scripts[0], encoding="utf-8")
result = subprocess.run(["node", "--check", str(check_path)])
if result.returncode:
    stop("JavaScript syntax validation failed. Original HTML remains unchanged.")

HTML_PATH.write_text(html, encoding="utf-8")
print("Installed the in-place problem switcher; JavaScript syntax check passed.")
print("Selecting a problem now changes its statement, starter code, and tests without navigating or reloading Vice City.")
print(f"Backup: {backup}")
print("Note: The game's underlying WASM control configuration remains the one active when the game was initially loaded.")

# Recording guide — TradePilot AI / TrustLoop demo video

Target: **2:51**, English UI, 1920×1080, 30 fps, **no system audio / no microphone** (narration is added in post).

---

## 0. Before you press record

1. **Narration file** (play it in headphones, not through speakers — otherwise the microphone or system audio
   capture will pick it up):
   `C:\Users\17663\Documents\deepseek-harness\default-workspace\tradepilot_narration\narration_synced.mp3`
   It is 2:45.5 long and every line already sits at its cue time.
2. **Browser**: Chrome → `Ctrl+Shift+N` (incognito) → open <https://tradepilot-trustloop.streamlit.app>
   - Wait until the app finishes warming (first load can take ~30 s).
   - Press **F11** (fullscreen).
   - Sidebar language must be **English**.
   - Click **Reset current demo** once, so the ladder starts at 0/3.
3. **Collapse the sidebar** for the first six shots: click the `«` at the top-right of the sidebar.
   (It hides the "LLM: off (rule-based planner)" line, which reads badly on camera.)
4. **Recording tool** (either works):
   - Windows Game Bar: `Win+Alt+R` starts/stops, output in `Videos\Captures`.
   - 剪映 → 录制 → 屏幕录制 (set 1080p / 30 fps, microphone **off**, system audio **off**).
5. Do one 20-second dry run to check the framing, then delete it.

---

## 1. The shot list

Press record, then start the narration file at the same moment.
The right column is what the viewer should be looking at when that line is spoken.

| Time | Narration (what you hear) | What YOU do |
|---|---|---|
| **0:00** | "First-time cross-border trade runs on trust nobody can verify…" | **Do nothing.** Hero + badges on screen. Keep the mouse still. |
| **0:13** | "Five hundred tonnes of rebar…" | Click **Review deal & build ladder** (red button, top right). |
| 0:15–0:34 | "…the agent rejects unsecured credit and proposes a ladder instead…" | Wait for the spinner. When the Trust Ladder appears (three cards, 1 READY / 2 LOCKED / 3 LOCKED), let it sit. |
| **0:34** | "Every finding links back to a quoted line of the contract…" | Scroll down one screen so **Deal & risk evidence** / **Agent plan** / **Currency & FX** fill the frame. |
| **0:38** | "No liquidated damages clause…" | Click the first **`>` HIGH · RISK** row to expand it. |
| **0:46** | "No delivery schedule…" | Click the second row **`>` HIGH · COMPLETENESS** to expand it too. |
| 0:54–1:06 | "…the planner only chooses the reasoning and the wording…" | Stay. The two expanded evidence blocks + the Agent plan rationale are on screen. |
| **1:06** | "The contract is in CNY…" | Move the mouse onto the **Currency & FX** card (CNY 1,825,000.00 → USD, source, rate, observed timestamp). Small hover, no clicking. |
| **1:23** | "Here is the line this whole project is built around…" | Click the red bar **Approve stage 1 & simulate PayPal**. |
| 1:25–1:44 | "…only then does the agent request invoice creation and sending…" | Wait for the rerun. Stage 1 turns **PAID**, stage 2 turns **READY**, and **Payment evidence** shows `TP-DEMO-0001 · USD 500.00 · PAID` with a transaction id. |
| **1:44** | "Two AG Grid tables hold the whole run…" | Scroll down to **Evidence console** (fast: two big wheel flicks). Land so the exposure bar + **Milestone evidence** grid are visible. |
| 1:50–2:00 | "…sortable, filterable, exportable…" | Point at the milestone grid, then scroll a little so the **Audit chain events** grid is also visible. |
| **2:00** | (no narration — you have ~3 s of silence) | Scroll back up to the top, click **Approve stage 2**, wait ~3 s, click **Approve stage 3**. The Passport is issued automatically. |
| **2:03** | "Every approval, settlement, FX snapshot and agent decision becomes…" | Scroll to the **Trust Passport** card (top area). Click **Download Trust Passport JSON** once (the download bar may appear briefly — fine). |
| **2:10** | "…a configured issuer signs it…" | Open the sidebar (`»` on the left edge). Paste the passport id (`TP-…`) into **Verify Passport ID**, click **Open public verification**. |
| **2:14** | "This is what a counterparty… can check without trusting us…" | Let the public verification page show **`VALID: the stored Passport and complete audit chain agree.`** Hold on it. |
| **2:26** | "PayPal moves the money, but that is not what makes this agentic commerce…" | Go back to the Deal Room (the **Open the Deal Room** button) and scroll to the Trust Ladder — all three stages **PAID**. |
| **2:45.5** | narration ends | Hold the final frame for ~5 s (end card is added in post), then stop recording. |

---

## 2. Rules that matter

- **Do not show any API key.** Don't open the "Bring your own model" panel, don't type a key.
- If you miss a click: keep recording, fix it, and **keep going**. Small recoveries are easier to cut than
  restarting the whole take.
- If the app throws an error or the page looks stale: press `Ctrl+R`, wait, click **Reset current demo**, and
  start the take again from 0:00.
- Speak nothing. The narration is already recorded.
- Aim for a **2:50–2:55** take. Anything under 3:00 is fine; I will trim.

---

## 3. Hand-off

Drop the file anywhere convenient and tell me the path (e.g. `C:\Users\17663\Videos\Captures\...mp4`).
I will:

1. cut and align it to `narration_synced.mp3`,
2. burn English subtitles (two lines max per caption, bottom-centre),
3. add a 5-second end card: `TradePilot AI — TrustLoop` · demo URL · repository URL,
4. export 1920×1080 H.264 under 2:55, and give it back to you for the YouTube upload.

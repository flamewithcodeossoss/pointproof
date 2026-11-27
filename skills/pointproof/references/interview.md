# Guided scoping conversation

Use this when the user starts without everything PointProof needs ("we got a tender, here's the points list"), or asks to be walked through it. Ask only what is missing; skip any question the user already answered or the files already settle. Ask one round of at most four questions, then work.

Where the agent can show choices (multiple-choice question tools), use them. Otherwise ask in one short message.

## Round 1: what we're scoping

| Question | Why it matters | Default if the user doesn't know |
|---|---|---|
| **Domain**: buildings, water network, utilities/energy, industrial, data centre, or mixed? | Picks the use-case library (`--domain`) | Infer from the points list: run `match_usecases.py` with all domains and take those with the most *ready* use cases |
| **Where do the points come from?** CSV/Excel list, PDF appendix, historian or PI tag export, BACnet EDE, Brick model, Haystack export, OPC UA NodeSet | Picks the reader (`parse_points.py --format`) | `--format auto` detects it from the file |
| **Highest method your team delivers**: rules, up to statistics, up to optimisation, up to ML. GenAI on top? | Sets `--max-method`; anything above it is out of scope | `statistics` for a team without data scientists |
| **How many items can the team deliver?** | Sets `capacity`; the studio and report flag the overflow | No limit |

Do not ask for the requirements again if a tender or list was attached; extract them and give each a `ref` (keep the tender's own numbering when it has one).

## Round 2 (only if needed): priorities

Ask only when there are more applicable candidates than capacity, or the user asks for a recommendation:

- Which outcomes matter most: energy cost, uptime and maintenance, compliance, occupant comfort, water loss, carbon?
- Anything already promised to the client, or already delivered by another party (fault detection platform, CMMS vendor)?
- Any data that will definitely not be available (no historian, no work-order export, no weather service)?

## Then propose, don't interrogate

1. Parse the points and match the library.
2. Draft `assessment.json` with every requirement: verdict, method, points, logic, output, example, missing.
3. Validate it.
4. Show a short shortlist in chat:

   | Ref | Requirement | Verdict | Method | Points | Main gap |
   |---|---|---|---|---|---|

   Then the counts (applicable / out of scope, coverage %), and ask: "Move anything in or out?" The user can answer in chat ("take R5 out, R11 in with statistics") or in the studio.
5. Apply the changes, revalidate, and build what they asked for: the studio, the Excel report, or both.

## Wording

- Say "rules" and "statistics" plainly. Say "optimisation" for scheduling, routing, allocation and budget choices, and name the solver model (assignment, routing, knapsack, inventory).
- Never call statistics or a solver "an AI model". Use "ML" only for a trained, retrained model.
- When a requirement is out of scope, say why in one line: above the policy, missing points, or delivered by another platform.

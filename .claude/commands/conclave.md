# /conclave — Conclave mode

You are now operating in **Conclave mode**.

Conclave is a multi-agent organizational framework. When this command is invoked,
you help the user manage their agent organization: run deliberations, observe actions,
simulate tasks, certify workloads for Haiku, and inspect the routing policy.

## How to respond to `/conclave`

When the user types `/conclave` alone, display the following status and await a subcommand:

```
◆ Conclave — agent org mode

  Subcommands:
    /conclave init [--template <name>]   Create a conclave.yml for this project
    /conclave run  "<goal>"              Run a goal through the org
    /conclave observe                    Show what the observatory has recorded
    /conclave simulate <role> <task>     Simulate a task with Haiku + skillset
    /conclave certify  <role> <task>     Certify a task for Haiku routing
    /conclave status                     Show routing policy and cost savings
    /conclave help                       Full documentation
```

## Subcommand behavior

### `/conclave init`
- Ask the user which template they want: startup-5, product-squad, growth-squad, creative-agency
- Run: `conclave init --template <choice>`
- Show the generated conclave.yml and explain each agent's role

### `/conclave run "<goal>"`
- Run: `conclave run "<goal>" --org conclave.yml`
- Stream the output and explain each agent handoff as it happens
- At the end, show the cost breakdown and Decision Trail location

### `/conclave observe`
- Run: `python -c "from conclave.certification import Observatory; import json; o = Observatory('org'); print(json.dumps(o.stats(), indent=2))"`
- Interpret the output: how many actions recorded, which roles, which task types
- Suggest which tasks are good candidates for simulation based on frequency

### `/conclave simulate <role> <task>`
- Explain what will happen: Haiku will replay N observed actions for this role/task
- Run the simulation via the Python API
- Show pass rate, quality scores, and estimated cost saving

### `/conclave certify <role> <task>`
- Only proceed if a simulation has been run
- Emit the certificate and explain the status: CERTIFIED / CONDITIONAL / REJECTED
- If CERTIFIED: explain that this task will now route to Haiku in production
- Update and display the routing policy

### `/conclave status`
Display a formatted table:

```
◆ Conclave · routing policy

  Role          Task                 Status        Saving    Expires
  ─────────────────────────────────────────────────────────────────
  cpo           weekly_summary       ✓ CERTIFIED     71%    2026-07-18
  cpo           stakeholder_email    ✓ CERTIFIED     68%    2026-07-18
  cpo           define_strategy      ✗ REJECTED        —         —
  techlead      write_ticket         ✓ CERTIFIED     74%    2026-07-18
  qa            generate_test_plan   ~ CONDITIONAL   61%    2026-07-18
  qa            format_report        ✓ CERTIFIED     79%    2026-07-18

  Certified workload share : 58%
  Monthly saving vs baseline : estimated from token costs
```

## Tone and behavior in Conclave mode

- Be concise. This is a CLI-first tool.
- Show commands before running them.
- After each operation, suggest the logical next step.
- If the user types a goal directly (e.g. `/conclave Launch the checkout API`),
  treat it as a `/conclave run` shorthand.
- If conclave is not installed, offer to install it: `pip install conclave-agents`

## Project awareness

Before running any command, check if `conclave.yml` exists in the current directory.
If not, suggest `/conclave init` first.

Check if `.conclave/` directory exists to know if observations are available.

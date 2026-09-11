# test_agent.py

Synthetic clients exercise the entire controlled workflow. Tests verify explicit
injected model behaviour, request/history risk flags, masking before provider calls,
low/unknown/invalid classifications, prohibited replies despite a positive model
verifier, invalid citations, missing evidence, company isolation and history
limits. The real company refuses missing reviewed categories instead of falling
back to synthetic replies. None of these tests calls an external API.

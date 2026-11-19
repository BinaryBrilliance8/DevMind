# Security and release status

DevMind is a research platform for executing proposed code in isolated containers.
It is not certified for hostile multi-tenant execution. See docs/OPERATIONS.md for
trust boundaries, privileges and known limitations.

Never commit `.env`, operator tokens, model keys, private project registries or live
databases. Do not publish proprietary source-bearing trajectories without permission.
Only workers should have access to the Docker daemon; that access is host-privileged.

There is no published security contact or repository URL yet. Until the repository
owner configures private vulnerability reporting, report issues directly to the owner
and omit credentials or exploitable private-system details from public issues.

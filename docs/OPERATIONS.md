# Security, deployment and recovery

## Trust model

Trusted actors are the operator, database administrator, execution-host administrator
and maintainers of the registered clone metadata and prebuilt images. Issue text,
repository source, model actions, command output and candidate patches are untrusted.
The model service and dependency/image suppliers are external trust dependencies.

The browser token is a single operator identity with access to all registered projects
and runs. It is not tenant isolation. API and worker service examples use separate OS
users and PostgreSQL; only workers receive Docker access. A conventional Docker daemon
is a powerful host capability even when execution containers never see its socket.
Use dedicated patched execution hosts; evaluate rootless Docker or stronger isolation.

## Implemented controls

- Strict task/action schemas and operator-owned repository/image/test policies.
- Constant-time bearer comparison, private API cache policy, same-origin assets,
  Content Security Policy, no external browser scripts/fonts and no source HTML injection.
- Body size, rate, queue capacity, action, context, token, process output and time bounds.
- Fenced ownership on events, terminal writes and cancellation; independent human review.
- Controller-owned immutable baseline and independent verification environment.
- Container CPU 1 core, RAM/swap ceiling 1 GiB, PID ceiling 128, workspace tmpfs 384 MiB,
  temporary tmpfs 128 MiB; no network, no host mounts, read-only base image, non-root UID.
- ACI source file/count limits and path/symlink validation; bounded process groups.
- No model credentials in the execution image or container environment.
- No automatic push/merge, cloud publishing or model training.

These controls do not constitute an adversarial sandbox audit. Containers share a
kernel; hostile code may exploit kernel/runtime vulnerabilities or interfere with
same-UID container processes. Prompt instructions are not a security guarantee.
Use microVM/gVisor-class isolation and independent security testing before hostile
multi-tenant workloads. Stronger isolation is a deployment extension, not included
as a falsely working switch.

## Data handling

Tool events may contain proprietary source or secrets present in source. There is no
complete secret scanner or automatic redaction guarantee. The operator must ensure
that the selected provider is permitted to receive the repository contents. Do not
register secret-bearing code without reviewing provider retention and access policy.

The service process uses umask 077. Protect the database directory, PostgreSQL
credentials, WAL/backups and any exported traces. Trajectory export requires explicit
consent and an approved run. It still requires license, privacy and per-action quality
review before training. No telemetry or hosted tracking service is enabled by default.

## Deploying

1. Provision dedicated worker hosts, a private PostgreSQL service and trusted clones.
2. Install the locked core dependencies and the package under `/opt/devmind`.
3. Place project configuration and secret environments under `/etc/devmind`, mode 0600
   where credentials are present. Register the exact same project aliases on API/workers.
4. Run `devmind init` once with the database administrative access needed to create
   schema; use restricted runtime credentials thereafter, after reviewing required SQL.
5. Build execution images with pinned dependencies. Replace mutable image tags with
   verified digests for a release. Record image and checkpoint provenance.
6. Configure `deploy/devmind-api.service` and `devmind-worker.service` for the host.
   These examples assume PostgreSQL and do not grant shared SQLite-file access.
7. Bind API to loopback behind an authenticated TLS reverse proxy before remote access.
   Configure request deadlines, connection limits and centralized rate limiting there.
8. Run the integration and recovery gates before allowing real external workloads.

The supplied Compose file provisions a development PostgreSQL instance bound to
loopback. It is not an HA database topology. The systemd units and CI workflow were
written but not launched on a remote deployment host during local validation.

## Observability

Logs include run ID, event kind and exception class. Source-bearing detail lives in
the private event table. Normal results include duration, steps, token count, commit,
image, prompt version and snapshot hash. Monitor queue depth/age, active leases,
interrupted/failed attempts, worker exits, DB lock contention, Docker memory/disk,
container residue and provider error rates.

`/health` proves API process liveness. `/ready` checks database schema and console
assets; `/api/readiness` and `devmind doctor` additionally probe the Docker daemon,
execution images, registered Git HEADs and model catalog. The catalog probe does
not prove inference; use `python research/check_model.py` for that check.
Run `doctor` on the worker host: the isolated API container deliberately has no
repository mounts or Docker socket. `/api/system` remains a configuration summary. There is no bundled
Prometheus exporter, full distributed trace backend or automatic paging service.

## Recovery procedures

| Failure | Response |
|---|---|
| Worker death | Next polling claim marks expired attempts interrupted; inspect and resubmit with a new key |
| Lost DB connectivity | Worker loses lease authority; restore DB, inspect attempt state before resubmission |
| Model failure | Confirm URL/model/key privately; transient failures retry with bounds; inspect terminal reason |
| Docker failure | Restore daemon/image availability; never bypass isolation by running repository commands on host |
| Cancellation | State write fences results immediately; watchdog requests container disposal; in-flight inference can finish later |
| Orphan container | Inspect `docker ps -a --filter label=devmind.execution=true`; remove only confirmed orphan IDs |
| Disk pressure | Pause admission, preserve required evidence, then apply a reviewed retention policy |
| Suspected host compromise | Stop/quarantine worker host, preserve audit records, revoke credentials and rebuild |

Execution containers have a lifespan bounded by the remaining run budget and
Docker `--rm` removal. A watchdog polls at most one second apart, fences a run on
deadline/shutdown and requests container removal on cancellation or lost ownership.
Normal exit also disposes containers. Daemon failure or a host crash can still delay
cleanup; inspect labelled containers after recovery. In-flight model calls can finish
after terminal state, but cannot publish a result. There is no retention deletion job. PostgreSQL backups
and point-in-time recovery must be provisioned by the deployment operator. SQLite
local backups should use its backup API rather than copying only an active DB file.

## Release gates

Passing local unit tests is one gate. Production release additionally requires:
real Docker and PostgreSQL integration; real-model issue runs; official benchmark
reproduction; image/dependency scans and SBOM; tenant/auth requirements review;
isolation assessment; load/p99 measurement; crash/lease/DB-failure drills;
backup restoration; data retention controls; and model/checkpoint licensing review.
No 99.99% availability, massive-scale capacity, GPU efficiency or official resolution
rate is asserted before those measurements exist.


## Complete container deployment

`deploy/compose.full.yaml` adds a schema-initialization job, API and worker to PostgreSQL.
Copy `deploy/env.example` to `deploy/.env`, set private values, and set registered
checkout paths to `/repositories/<clone>` inside the worker. The host clone parent
is mounted read-only there. Determine the real socket group on the Linux host with
`stat -c '%g' /var/run/docker.sock`; use that as `DEVMIND_DOCKER_GID`.
The worker's Docker access is privileged host access; the API never receives it.
Build the executor on the same Docker daemon used by workers, then run:

```bash
docker build -f deploy/Dockerfile.executor -t devmind-executor:1 .
docker compose --env-file deploy/.env -f deploy/compose.full.yaml up -d --build
docker compose --env-file deploy/.env -f deploy/compose.full.yaml run --rm worker doctor
```

This topology uses an external HTTPS inference endpoint. For the locally validated
loopback model service, run the native API/worker commands in the README instead.
No automatic external publication is performed. The stack definition is supplied;
its image builds and startup remain unverified in this sandbox.

## Configuration and schema lifecycle

Positive integer environment settings: `DEVMIND_STEPS`, `DEVMIND_SECONDS`,
`DEVMIND_COMMAND_SECONDS`, `DEVMIND_TOKEN_LIMIT`, `DEVMIND_CONTEXT_CHARS`,
`DEVMIND_LEASE_SECONDS`, `DEVMIND_CAPACITY`. Defaults are in `config.py`.
`devmind init` transactionally installs schema version 1 or adopts the prior baseline
only when expected column names match. Unknown versions or incompatible columns
fail visibly. Startup/readiness require the recorded version. This is a baseline
migration, not a promise to infer arbitrary future data migrations. Back up before
upgrades; future versions must ship explicit migration logic and restore tests.

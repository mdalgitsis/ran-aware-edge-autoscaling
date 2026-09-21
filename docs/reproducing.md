# The papers, and what you can reproduce here

## Related publications

The offline studies in [`studies/`](../studies) are the evaluation behind:

> M. Dalgitsis, G. M. Kibalya, M. A. Serrano, J. Serra and A. Antonopoulos,
> "**Exploiting 6G RAN and Core Network Information for Intelligent Edge-Cloud
> Service Orchestration**," *2025 Joint European Conference on Networks and
> Communications & 6G Summit (EuCNC/6G Summit)*, Poznan, Poland, 2025,
> pp. 369–374.
> doi: [10.1109/EuCNC/6GSummit63408.2025.11037032](https://doi.org/10.1109/EuCNC/6GSummit63408.2025.11037032)

The closed loop itself is one of the use cases in:

> M. Dalgitsis, E. Datsika, C. Santana Casillas and A. Antonopoulos,
> "**6G-Core-in-the-Loop: Enabling Service and Network Orchestration in a
> Cloud-Native Ecosystem**," *IEEE Communications Standards Magazine*, vol. 10,
> no. 2, pp. 72–79, June 2026.
> doi: [10.1109/MCOMSTD.2026.3657234](https://doi.org/10.1109/MCOMSTD.2026.3657234)

The paper proposes **NASO** (Network-aware Service Orchestration), a framework
with three mechanisms. The title's "RAN and Core" is not two systems — it is
two *signals*, consumed by the same orchestrator:

| Mechanism | Signal | Source | Here |
| --- | --- | --- | --- |
| **HSIA** — Instance Autoscaler | active user sessions | **Core network.** §IV notes this cannot be read from a single network API; it is derived by combining the SMF's active-session data with the application backend. | `deploy` / `undeploy` |
| **HSRA** — Resource Autoscaler | aggregated radio traffic from base stations | **RAN** | `scale`, `R = ⌈T / T_opt⌉` (Eq. 1) |
| **HSECM** — Edge-Cloud Migration | edge CPU capacity | orchestrator | **not implemented here** |

That distinction is why the exported metrics carry different prefixes:
`cn_active_users_*` is core data, `ran_data_rate_*` is radio data. Collapsing
them into one "RAN metrics" bucket would lose the point of the paper.

## Decoding the names

The papers' shorthand carries into the code:

| Paper | Here |
| --- | --- |
| **NASO** — Network-aware Service Orchestration | The proposed framework, and the label for its strategy in the comparison plots. |
| **Full-Deployment** | The energy baseline: deploy every application in every region regardless of demand. |
| **Random-SM** | Service migration to a randomly chosen destination. |
| **CPU-based-High/Low-SM** | Migration chosen on CPU headroom — what a conventional scheduler does. |
| **UASM** | Users Affected by Service Migration, as a percentage. |

## Running the studies

```bash
pip install -r requirements-plot.txt

python -m studies.migration_impact --output-dir out
python studies/energy_efficiency.py
```

**Migration impact** — how many users a relocation disrupts, per strategy:

```
Random-SM            mean UASM @100Mbps:  43.2%
CPU-based-High-SM    mean UASM @100Mbps:  40.5%
CPU-based-Low-SM     mean UASM @100Mbps:  46.8%
NASO                 mean UASM @100Mbps:  33.6%
```

CPU-based placement is blind to where the traffic actually is, so it relocates
services in ways that break more sessions than necessary.

These are means across all user counts at 100 Mb/s per replica, which is not
the paper's headline figure — that one is ~17–18% for NASO at **500** Mb/s per
replica, against >80% for Random-SM and CPU-based-Low-SM in the most
constrained cases. Higher per-replica capacity needs fewer replicas, so fewer
migrations, so less user impact; the study sweeps both scenarios.

**Energy efficiency** — deploying everywhere versus deploying where demand is.
Reduction grows with the number of applications and is largely independent of
the number of regions:

```
  regions \ apps     1      5     10     20     40     50
     2            -0.1%   1.2%   5.6%  21.2%  41.9%  50.4%
    50            -0.1%   0.8%   5.2%  21.1%  44.1%  51.8%
```

With one application there is nothing to gain — it has to run somewhere. The
saving is in *not* running the other 49 everywhere.

Both studies are seeded, so a given seed reproduces a given figure.

## What is reproducible, and what is not

**The studies reproduce.** The simulation models are unchanged from the
versions used for the paper; only the output paths and the blocking `show()`
calls were made configurable so they run headless.

**Two of the three mechanisms are implemented.** `autoscaler/` covers HSIA and
HSRA — lines 3–16 of Algorithm 1. HSECM, the CPU-capacity-driven offload to
the cloud in lines 17–26, is not implemented here at all: nothing in this
repository decides that an edge node is over capacity or chooses what to move.

**The live loop is an independent implementation.** In the original deployment
the scaling algorithm was realised inside a commercial orchestration platform,
which is proprietary and not included. [`autoscaler/`](../autoscaler) implements
the same published algorithm against Prometheus and the Kubernetes API, with
the decision isolated in [`policy.py`](../autoscaler/policy.py) so it can be
read against the paper directly.

It is therefore a faithful implementation of the *algorithm*, not a
reproduction of the original *deployment*, and numbers measured against it will
not match a platform this repository does not contain.

## Reading the demo honestly

`python -m autoscaler.demo` shows the loop deploy, scale with the traffic ramp,
scale back and undeploy. Two things in that output are worth not glossing over:

- **Replicas oscillate at peak load** — 7, then 6, then 7 again. Demand sitting
  near a replica boundary crosses it repeatedly. `DEADBAND` suppresses this and
  defaults to 0, because 0 is what the paper evaluated.
- **The loop reacts, it does not predict.** Scale-out begins after traffic has
  already risen. Radio metrics buy you a head start over CPU — the users are
  visible before their load reaches the application — but it is a head start,
  not foresight.

## Funding

The work was supported in part by the Horizon Europe SNS JU **UNITY-6G**
project (European Commission, ID 101192650) and the **6G-OASIS** project
(TSI-063000-2021-24) under the UNICO5G-RPTR programme. The paper is joint work
with colleagues at Nearby Computing and the Centre Tecnològic de
Telecomunicacions de Catalunya (CTTC).

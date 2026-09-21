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

The EuCNC title names both halves — **RAN and Core**. This repository is the
RAN half: scaling and placing edge services on radio information. The core half,
reconfiguring 5G slice bitrate ceilings on acceptance ratio, is in
[slice-ambr-closed-loop](https://github.com/mdalgitsis/slice-ambr-closed-loop).

## Decoding the names

The papers' shorthand carries into the code:

| Paper | Here |
| --- | --- |
| **NASO** — network-aware service orchestration | The proposed approach: use what the network already knows about users and traffic. |
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

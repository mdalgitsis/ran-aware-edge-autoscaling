# Deployment

## Prerequisites

- A Kubernetes cluster
- Prometheus, plus the Prometheus Operator if you want the `ServiceMonitor`s

## Try it without a cluster first

```bash
pip install -r requirements.txt
python -m autoscaler.demo
```

Runs the telemetry source and the policy in-process with an in-memory stand-in
for the Deployment. Nothing is provisioned and nothing is scaled; it exists to
show the behaviour in about ten seconds.

## Telemetry source

```bash
helm install ran-telemetry charts/ue-simulator \
  --set topology="edge1=A,B,C;edge2=D,E"
```

In a real deployment this is where your actual RAN metrics come from instead —
a network exposure function, an RIC, or a vendor exporter. The autoscaler only
needs two series carrying an edge-node label, so pointing it at real telemetry
is a matter of `usersQuery` and `trafficQuery`.

## Autoscaler

```bash
helm install ran-autoscaler charts/autoscaler \
  --set prometheus.url=http://prometheus.monitoring.svc.cluster.local:9090 \
  --set workload.deploymentTemplate="edge-app-{edge_node}" \
  --set sla.optimalTrafficMbps=50
```

`deploymentTemplate` names the Deployment it manages per edge node;
`{edge_node}` is substituted from the metric label. The chart creates a Role
scoped to `get/list/watch` on Deployments and `get/update/patch` on
`deployments/scale` — deliberately no `delete`.

**Start with `--set loop.dryRun=true`.** The loop then decides and exports
everything but writes nothing, so you can watch
`ran_autoscaler_desired_replicas` against `ran_autoscaler_current_replicas` and
confirm the SLA is right before it touches a workload.

### Choosing `optimalTrafficMbps`

This is an SLA input — the traffic one replica is *specified* to serve — not a
measurement. Setting it too low over-provisions on every ramp; too high and
scale-out arrives after users are already degraded.

### Flapping

`sla.deadband` defaults to 0, which is the published algorithm. In production,
raise it to 1: demand hovering at a replica boundary otherwise scales back and
forth every reconcile.

## Dashboard

[`grafana/dashboard.json`](../grafana/dashboard.json) imports as-is. Panels
reference a `DS_PROMETHEUS` datasource variable, so the same file works on any
Grafana rather than carrying one instance's datasource UID.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `Holding: query ... failed` each tick | Prometheus unreachable. Intentional: the loop does nothing rather than reading a failed scrape as zero users. Check `prometheus.url`. |
| Nothing scales, no errors | The queries return no samples carrying `edge_node`. Check `usersQuery`/`trafficQuery` and `edgeLabel`. |
| Replicas oscillate by one | Demand sitting on a replica boundary. Raise `sla.deadband`. |
| `403` on the scale subresource | `workload.namespace` differs from the release namespace; the Role is created in the former. |
| Metrics missing from Prometheus | `serviceMonitor.labels.release` must match your Prometheus selector. |

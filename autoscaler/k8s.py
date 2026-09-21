# Copyright 2026 Nearby Computing S.L.
"""Apply decisions to Deployments.

"Deployed" is expressed as a non-zero replica count. Undeploying scales to
zero rather than deleting the Deployment: it frees the pods, which is the part
that matters for edge resources, while leaving the object in place so the next
deploy is a scale rather than a re-apply of a manifest this loop does not own.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class WorkloadState:
    exists: bool
    replicas: int


class DeploymentScaler:
    """Thin wrapper over the apps/v1 Deployment scale subresource."""

    def __init__(self, namespace: str, dry_run: bool = False):
        self.namespace = namespace
        self.dry_run = dry_run
        self._api = None

    @property
    def api(self):
        if self._api is None:
            from kubernetes import client
            from kubernetes import config as kube_config

            try:
                kube_config.load_incluster_config()
                log.info("Using in-cluster Kubernetes configuration")
            except Exception:
                kube_config.load_kube_config()
                log.info("Using local kubeconfig")
            self._api = client.AppsV1Api()
        return self._api

    def get(self, name: str) -> WorkloadState:
        from kubernetes.client.rest import ApiException

        try:
            deployment = self.api.read_namespaced_deployment(
                name=name, namespace=self.namespace
            )
        except ApiException as exc:
            if exc.status == 404:
                return WorkloadState(exists=False, replicas=0)
            raise
        return WorkloadState(
            exists=True, replicas=deployment.spec.replicas or 0
        )

    def scale(self, name: str, replicas: int) -> None:
        if self.dry_run:
            log.info("[dry-run] would scale %s to %s replica(s)", name, replicas)
            return
        self.api.patch_namespaced_deployment_scale(
            name=name,
            namespace=self.namespace,
            body={"spec": {"replicas": replicas}},
        )
        log.info("Scaled %s to %s replica(s)", name, replicas)

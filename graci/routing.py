"""Deterministic Phase 3B role resolution from the resource registry."""

from dataclasses import dataclass

from .registry import (
    GLM_MODEL_ID, LOCAL_PROVIDER_ID, PRIMARY_ENDPOINT_ID, PRIMARY_NODE_ID,
    QWEN_MODEL_ID, ModelRole, Registry, evaluate_eligibility,
)


class RoleResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class RoleBinding:
    role: ModelRole
    provider: str
    node_id: str
    endpoint_id: str
    endpoint: str
    model: str

    def evidence(self) -> dict[str, str]:
        return {"role": self.role.value, "provider": self.provider,
                "node": self.node_id, "endpoint_id": self.endpoint_id,
                "endpoint": self.endpoint, "model": self.model}


_ROLE_MODELS = {
    ModelRole.IMPLEMENTER: QWEN_MODEL_ID,
    ModelRole.REVIEWER: GLM_MODEL_ID,
    ModelRole.VERIFIER: GLM_MODEL_ID,
}


class Phase3BRoleRouter:
    """Resolve only authorized primary-node Phase 3B role bindings."""

    def __init__(self, registry: Registry):
        self.registry = registry

    def resolve(self, role: ModelRole | str) -> RoleBinding:
        try:
            requested = role if isinstance(role, ModelRole) else ModelRole(role)
        except ValueError as exc:
            raise RoleResolutionError(f"unsupported role: {role!r}") from exc
        model_id = _ROLE_MODELS.get(requested)
        if model_id is None:
            raise RoleResolutionError(f"role is not routable in Phase 3B: {requested.value}")
        result = evaluate_eligibility(
            self.registry, PRIMARY_NODE_ID, PRIMARY_ENDPOINT_ID, model_id,
            required_role=requested, policy_state="phase3b")
        if not result.eligible:
            raise RoleResolutionError(
                f"role {requested.value} is unavailable: {result.reason_code.value}: "
                f"{result.explanation}")
        endpoint = self.registry.endpoints[PRIMARY_ENDPOINT_ID]
        return RoleBinding(requested, LOCAL_PROVIDER_ID, PRIMARY_NODE_ID,
                           PRIMARY_ENDPOINT_ID, endpoint.base_url, model_id)

"""Policy routing logic for inference requests."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List

from .config import GatewaySettings
from .models import Policy, PolicyDecision


@dataclass
class PolicyRouter:
    settings: GatewaySettings

    def choose(self, policies: Iterable[Policy]) -> PolicyDecision:
        policies_list = list(policies)
        if not policies_list:
            raise ValueError("No policies available for routing")

        active = [p for p in policies_list if p.status == "active"]
        shadow = [p for p in policies_list if p.status == "shadow"]

        if active:
            selected = active[0]
        else:
            selected = policies_list[0]

        reason = "active"
        shadow_candidates: List[Policy] = []

        if shadow and random.random() < self.settings.shadow_sampling_rate:
            candidate = random.choice(shadow)
            shadow_candidates.append(candidate)
            reason = "shadow_sampled"

        return PolicyDecision(selected=selected, shadow_candidates=shadow_candidates, reason=reason)


__all__ = ["PolicyRouter"]
